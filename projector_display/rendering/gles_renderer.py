"""
OpenGL ES 2.0 GPU-accelerated renderer.

Replaces the software-rendered pygame backend with GPU-accelerated drawing.
Uses pygame for window creation and event handling, OpenGL ES 2.0 for rendering.

Requires: PyOpenGL>=3.1.6
"""

# CRITICAL: Disable ALL PyOpenGL overhead flags BEFORE importing any GL functions.
# PyOpenGL's default wraps every GL call with glGetError(), which forces a GPU
# pipeline flush on the Pi 4's V3D driver — adds ~0.5-1ms per call.
# With ~300 GL calls/frame this turns 2ms frames into 300ms frames.
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False
OpenGL.ERROR_ON_COPY = False
OpenGL.CONTEXT_CHECKING = False

import ctypes
import os
import math
import logging
from collections import OrderedDict
from typing import Any, Tuple, List, Optional

import numpy as np
import pygame

from OpenGL.GL import (
    glViewport, glClearColor, glClear, glEnable, glBlendFunc,
    glUseProgram, glGetUniformLocation, glGetAttribLocation,
    glUniform4f, glUniformMatrix4fv,
    glGenBuffers, glBindBuffer, glBufferData,
    glVertexAttribPointer, glEnableVertexAttribArray,
    glDrawArrays, glLineWidth, glGetFloatv,
    glGenTextures, glDeleteTextures, glBindTexture, glTexImage2D, glTexParameteri,
    glActiveTexture, glUniform1i,
    glCreateShader, glShaderSource, glCompileShader, glGetShaderiv,
    glGetShaderInfoLog, glCreateProgram, glAttachShader, glLinkProgram,
    glGetProgramiv, glGetProgramInfoLog, glDeleteShader,
    GL_COLOR_BUFFER_BIT, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_TRIANGLES, GL_TRIANGLE_FAN, GL_LINES, GL_LINE_STRIP, GL_LINE_LOOP,
    GL_FLOAT, GL_FALSE, GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    GL_COMPILE_STATUS, GL_LINK_STATUS, GL_TRUE,
    GL_ALIASED_LINE_WIDTH_RANGE,
)
from OpenGL.GL import glFinish

from projector_display.rendering.renderer import (
    _get_sdl_version, _get_display_position_xrandr,
)

logger = logging.getLogger(__name__)

# --- Direct ctypes GL bindings for hot-path functions ---
# PyOpenGL's pure Python wrappers add ~130µs per GL call (profiled on Pi 4).
# Direct ctypes calls reduce this to ~5-10µs — a 15-25x speedup per call.
# Non-hot-path functions (shader compile, texture upload) still use PyOpenGL.

import ctypes as _ctypes
import ctypes.util as _ctypes_util

def _load_gles_lib():
    """Load the GLES2/GL shared library for direct ctypes access."""
    for name in ("GLESv2", "GL"):
        path = _ctypes_util.find_library(name)
        if path:
            try:
                return _ctypes.CDLL(path)
            except OSError:
                continue
    # Fallback: try common aarch64 paths
    for path in ("/usr/lib/aarch64-linux-gnu/libGLESv2.so.2",
                 "/usr/lib/aarch64-linux-gnu/libGLESv2.so",
                 "/usr/lib/aarch64-linux-gnu/libGL.so.1"):
        try:
            return _ctypes.CDLL(path)
        except OSError:
            continue
    return None

_gl_lib = _load_gles_lib()
if _gl_lib is None:
    logger.warning("Could not load GLES2/GL library for ctypes — using PyOpenGL wrappers")

# Type aliases
_c_f = _ctypes.c_float
_c_i = _ctypes.c_int
_c_ui = _ctypes.c_uint
_c_ub = _ctypes.c_ubyte
_c_vp = _ctypes.c_void_p
_c_ss = _ctypes.c_ssize_t

if _gl_lib:
    _gl_ClearColor = _gl_lib.glClearColor
    _gl_ClearColor.argtypes = [_c_f, _c_f, _c_f, _c_f]
    _gl_ClearColor.restype = None

    _gl_Clear = _gl_lib.glClear
    _gl_Clear.argtypes = [_c_ui]
    _gl_Clear.restype = None

    _gl_UseProgram = _gl_lib.glUseProgram
    _gl_UseProgram.argtypes = [_c_ui]
    _gl_UseProgram.restype = None

    _gl_Uniform4f = _gl_lib.glUniform4f
    _gl_Uniform4f.argtypes = [_c_i, _c_f, _c_f, _c_f, _c_f]
    _gl_Uniform4f.restype = None

    _gl_Uniform1i = _gl_lib.glUniform1i
    _gl_Uniform1i.argtypes = [_c_i, _c_i]
    _gl_Uniform1i.restype = None

    _gl_BufferData = _gl_lib.glBufferData
    _gl_BufferData.argtypes = [_c_ui, _c_ss, _c_vp, _c_ui]
    _gl_BufferData.restype = None

    _gl_VertexAttribPointer = _gl_lib.glVertexAttribPointer
    _gl_VertexAttribPointer.argtypes = [_c_ui, _c_i, _c_ui, _c_ub, _c_i, _c_vp]
    _gl_VertexAttribPointer.restype = None

    _gl_EnableVertexAttribArray = _gl_lib.glEnableVertexAttribArray
    _gl_EnableVertexAttribArray.argtypes = [_c_ui]
    _gl_EnableVertexAttribArray.restype = None

    _gl_DrawArrays = _gl_lib.glDrawArrays
    _gl_DrawArrays.argtypes = [_c_ui, _c_i, _c_i]
    _gl_DrawArrays.restype = None

    _gl_LineWidth = _gl_lib.glLineWidth
    _gl_LineWidth.argtypes = [_c_f]
    _gl_LineWidth.restype = None

    _gl_BindTexture = _gl_lib.glBindTexture
    _gl_BindTexture.argtypes = [_c_ui, _c_ui]
    _gl_BindTexture.restype = None

    _gl_ActiveTexture = _gl_lib.glActiveTexture
    _gl_ActiveTexture.argtypes = [_c_ui]
    _gl_ActiveTexture.restype = None

_INV_255 = 1.0 / 255.0

# --- Shader sources ---

_SOLID_VERT = """
attribute vec2 a_position;
uniform mat4 u_projection;
void main() {
    gl_Position = u_projection * vec4(a_position, 0.0, 1.0);
}
"""

_SOLID_FRAG = """
precision mediump float;
uniform vec4 u_color;
void main() {
    gl_FragColor = u_color;
}
"""

_TEXTURED_VERT = """
attribute vec2 a_position;
attribute vec2 a_texcoord;
uniform mat4 u_projection;
varying vec2 v_texcoord;
void main() {
    gl_Position = u_projection * vec4(a_position, 0.0, 1.0);
    v_texcoord = a_texcoord;
}
"""

_TEXTURED_FRAG = """
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D u_texture;
void main() {
    gl_FragColor = texture2D(u_texture, v_texcoord);
}
"""

# Text cache capacity
_TEXT_CACHE_MAX = 256

# Void pointer for glVertexAttribPointer offset=0
_NULL = ctypes.c_void_p(0)
# Offset 8 bytes (2 floats) for texcoord attribute in interleaved layout
_OFFSET_8 = ctypes.c_void_p(8)


def _compile_shader(source: str, shader_type: int) -> int:
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    if glGetShaderiv(shader, GL_COMPILE_STATUS) != GL_TRUE:
        info = glGetShaderInfoLog(shader).decode()
        raise RuntimeError(f"Shader compile error: {info}")
    return shader


def _link_program(vert_src: str, frag_src: str) -> int:
    vs = _compile_shader(vert_src, GL_VERTEX_SHADER)
    fs = _compile_shader(frag_src, GL_FRAGMENT_SHADER)
    prog = glCreateProgram()
    glAttachShader(prog, vs)
    glAttachShader(prog, fs)
    glLinkProgram(prog)
    if glGetProgramiv(prog, GL_LINK_STATUS) != GL_TRUE:
        info = glGetProgramInfoLog(prog).decode()
        raise RuntimeError(f"Program link error: {info}")
    glDeleteShader(vs)
    glDeleteShader(fs)
    return prog


def _ortho_matrix(width: float, height: float) -> np.ndarray:
    """Create orthographic projection: origin top-left, +Y down."""
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / width
    m[1, 1] = -2.0 / height  # flip Y
    m[2, 2] = -1.0
    m[3, 3] = 1.0
    m[0, 3] = -1.0
    m[1, 3] = 1.0
    return m


def _precompute_unit_circle(segments: int) -> np.ndarray:
    """Return (segments+1, 2) array of (cos, sin) for a unit circle."""
    angles = np.linspace(0, 2.0 * math.pi, segments + 1, dtype=np.float32)
    return np.column_stack((np.cos(angles), np.sin(angles)))


# Pre-computed unit circles for common segment counts
_UNIT_CIRCLE_16 = _precompute_unit_circle(16)
_UNIT_CIRCLE_32 = _precompute_unit_circle(32)
_UNIT_CIRCLE_64 = _precompute_unit_circle(64)


class GLESRenderer:
    """GPU-accelerated renderer using OpenGL ES 2.0 via pygame window."""

    def __init__(self, fullscreen: bool = False):
        self.width: int = 0
        self.height: int = 0
        self.clock: Optional[pygame.time.Clock] = None
        self._fullscreen = fullscreen

        # GL resources (set in init)
        self._solid_prog: int = 0
        self._tex_prog: int = 0
        self._vbo: int = 0
        self._proj_matrix: Optional[np.ndarray] = None

        # Solid program locations
        self._s_a_position: int = -1
        self._s_u_projection: int = -1
        self._s_u_color: int = -1

        # Textured program locations
        self._t_a_position: int = -1
        self._t_a_texcoord: int = -1
        self._t_u_projection: int = -1
        self._t_u_texture: int = -1

        # State tracking to skip redundant GL calls
        self._current_prog: int = 0
        self._current_line_width: float = 1.0

        # Font cache (pygame.font objects)
        self._fonts: dict = {}

        # Text texture cache: key -> (tex_id, width, height)
        self._text_cache: OrderedDict = OrderedDict()

        # Tracked GL textures for cleanup
        self._owned_textures: list = []

    def init(self, screen_index: int = 0) -> None:
        """Initialize pygame window with OpenGL context and compile shaders."""
        os.environ.setdefault("DISPLAY", ":0")

        pygame.init()

        sdl_version = _get_sdl_version()
        logger.info(f"SDL version {sdl_version[0]}.{sdl_version[1]}.{sdl_version[2]} detected")

        # Request OpenGL ES 2.0 context
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 2)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 0)
        pygame.display.gl_set_attribute(
            pygame.GL_CONTEXT_PROFILE_MASK,
            pygame.GL_CONTEXT_PROFILE_ES,
        )

        # Determine display size and position
        if sdl_version[0] >= 2:
            num_displays = pygame.display.get_num_displays()
            if screen_index >= num_displays:
                logger.warning(
                    f"screen_index {screen_index} not available "
                    f"(have {num_displays}), using 0"
                )
                screen_index = 0

            desktop_sizes = pygame.display.get_desktop_sizes()
            target_width, target_height = desktop_sizes[screen_index]
            logger.info(f"Target display {screen_index}: {target_width}x{target_height}")

            display_x, display_y = _get_display_position_xrandr(screen_index)
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{display_x},{display_y}"
        else:
            os.environ["SDL_VIDEO_FULLSCREEN_DISPLAY"] = str(screen_index)
            info = pygame.display.Info()
            target_width, target_height = info.current_w, info.current_h

        # Window flags
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if self._fullscreen:
            flags |= pygame.FULLSCREEN
        else:
            flags |= pygame.NOFRAME

        pygame.display.set_mode((target_width, target_height), flags)
        pygame.display.set_caption("Projector Display Server")
        pygame.mouse.set_visible(False)

        self.width = target_width
        self.height = target_height
        self.clock = pygame.time.Clock()

        # Log GL info
        from OpenGL.GL import glGetString, GL_VENDOR, GL_RENDERER, GL_VERSION
        vendor = glGetString(GL_VENDOR)
        renderer_str = glGetString(GL_RENDERER)
        version = glGetString(GL_VERSION)
        logger.info(f"GL vendor: {vendor}")
        logger.info(f"GL renderer: {renderer_str}")
        logger.info(f"GL version: {version}")

        # Log supported line width range
        lw_range = glGetFloatv(GL_ALIASED_LINE_WIDTH_RANGE)
        logger.info(f"GL line width range: {lw_range[0]:.1f} - {lw_range[1]:.1f}")

        # Setup GL state
        glViewport(0, 0, self.width, self.height)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Compile shader programs
        self._solid_prog = _link_program(_SOLID_VERT, _SOLID_FRAG)
        self._tex_prog = _link_program(_TEXTURED_VERT, _TEXTURED_FRAG)

        # Cache uniform/attribute locations — solid
        self._s_a_position = glGetAttribLocation(self._solid_prog, "a_position")
        self._s_u_projection = glGetUniformLocation(self._solid_prog, "u_projection")
        self._s_u_color = glGetUniformLocation(self._solid_prog, "u_color")

        # Cache uniform/attribute locations — textured
        self._t_a_position = glGetAttribLocation(self._tex_prog, "a_position")
        self._t_a_texcoord = glGetAttribLocation(self._tex_prog, "a_texcoord")
        self._t_u_projection = glGetUniformLocation(self._tex_prog, "u_projection")
        self._t_u_texture = glGetUniformLocation(self._tex_prog, "u_texture")

        # Create VBO — bind once, keep bound for the lifetime of the renderer.
        # Each draw call uses glBufferData to orphan + upload (avoids GPU stalls).
        self._vbo = int(glGenBuffers(1))
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        # Enable vertex attrib 0 permanently (position — used by both programs)
        glEnableVertexAttribArray(0)

        # Build projection matrix
        self._proj_matrix = _ortho_matrix(self.width, self.height)

        # Upload projection matrix to both programs once — it never changes
        glUseProgram(self._solid_prog)
        glUniformMatrix4fv(self._s_u_projection, 1, GL_TRUE, self._proj_matrix)
        glUseProgram(self._tex_prog)
        glUniformMatrix4fv(self._t_u_projection, 1, GL_TRUE, self._proj_matrix)
        self._current_prog = self._tex_prog

        # Check for OpenGL_accelerate (C extension that speeds up PyOpenGL 2-10x)
        try:
            import OpenGL_accelerate
            logger.info(f"OpenGL_accelerate: v{OpenGL_accelerate.__version__}")
        except ImportError:
            logger.warning(
                "OpenGL_accelerate NOT installed — PyOpenGL uses slow Python "
                "wrappers. Consider: pip install PyOpenGL-accelerate"
            )

        # Log PyOpenGL configuration
        logger.info(
            f"PyOpenGL flags: ERROR_CHECKING={OpenGL.ERROR_CHECKING}, "
            f"ERROR_LOGGING={OpenGL.ERROR_LOGGING}, "
            f"CONTEXT_CHECKING={OpenGL.CONTEXT_CHECKING}"
        )

        # --- Micro-benchmarks ---
        import time as _time

        # Bench 1: glClear only (GPU-side cost)
        _bench_n = 200
        glFinish()  # drain pipeline first
        _t0 = _time.perf_counter()
        for _ in range(_bench_n):
            glClear(GL_COLOR_BUFFER_BIT)
        glFinish()
        _t1 = _time.perf_counter()
        _per_call_us = (_t1 - _t0) / _bench_n * 1e6
        logger.info(
            f"GL bench [glClear]: {_bench_n} calls in {(_t1-_t0)*1000:.1f}ms "
            f"({_per_call_us:.0f}µs/call)"
        )

        # Bench 2: Full draw pattern (uniform + buffer orphan + attrib + draw)
        self._use_solid()
        _bench_verts = np.array(
            [[100, 100], [200, 100], [200, 200], [100, 200]],
            dtype=np.float32,
        )
        # Warm up
        for _ in range(10):
            glUniform4f(self._s_u_color, 1.0, 0.0, 0.0, 1.0)
            glBufferData(GL_ARRAY_BUFFER, _bench_verts.nbytes,
                         _bench_verts, GL_DYNAMIC_DRAW)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        glFinish()

        _t0 = _time.perf_counter()
        for _ in range(_bench_n):
            glUniform4f(self._s_u_color, 1.0, 0.0, 0.0, 1.0)
            glBufferData(GL_ARRAY_BUFFER, _bench_verts.nbytes,
                         _bench_verts, GL_DYNAMIC_DRAW)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        glFinish()
        _t1 = _time.perf_counter()
        _per_draw_us = (_t1 - _t0) / _bench_n * 1e6
        logger.info(
            f"GL bench [draw quad]: {_bench_n} quads in {(_t1-_t0)*1000:.1f}ms "
            f"({_per_draw_us:.0f}µs/draw)"
        )

        if _per_draw_us > 500:
            logger.warning(
                f"GL draw calls are slow ({_per_draw_us:.0f}µs/draw). "
                "If >1000µs, PyOpenGL overhead is the bottleneck."
            )

        # Bench 3: Direct ctypes draw (bypassing PyOpenGL wrappers)
        if _gl_lib:
            _gl_UseProgram(self._solid_prog)
            self._current_prog = self._solid_prog
            # Warm up ctypes path
            for _ in range(10):
                _gl_Uniform4f(self._s_u_color, 1.0, 0.0, 0.0, 1.0)
                _gl_BufferData(GL_ARRAY_BUFFER, _bench_verts.nbytes,
                               _bench_verts.ctypes.data, GL_DYNAMIC_DRAW)
                _gl_VertexAttribPointer(0, 2, GL_FLOAT, 0, 0, None)
                _gl_DrawArrays(GL_TRIANGLE_FAN, 0, 4)
            glFinish()

            _t0 = _time.perf_counter()
            _bench_data_ptr = _bench_verts.ctypes.data
            for _ in range(_bench_n):
                _gl_Uniform4f(self._s_u_color, 1.0, 0.0, 0.0, 1.0)
                _gl_BufferData(GL_ARRAY_BUFFER, _bench_verts.nbytes,
                               _bench_data_ptr, GL_DYNAMIC_DRAW)
                _gl_VertexAttribPointer(0, 2, GL_FLOAT, 0, 0, None)
                _gl_DrawArrays(GL_TRIANGLE_FAN, 0, 4)
            glFinish()
            _t1 = _time.perf_counter()
            _per_ctypes_us = (_t1 - _t0) / _bench_n * 1e6
            _speedup = _per_draw_us / max(_per_ctypes_us, 1)
            logger.info(
                f"GL bench [ctypes draw]: {_bench_n} quads in "
                f"{(_t1-_t0)*1000:.1f}ms ({_per_ctypes_us:.0f}µs/draw) — "
                f"speedup vs PyOpenGL: {_speedup:.1f}x"
            )

        logger.info(f"GLESRenderer initialized: {self.width}x{self.height}")

    # ------ internal helpers ------

    def get_size(self) -> Tuple[int, int]:
        return (self.width, self.height)

    def _use_solid(self) -> None:
        """Switch to solid color shader program (skips if already active)."""
        if self._current_prog != self._solid_prog:
            _gl_UseProgram(self._solid_prog)
            self._current_prog = self._solid_prog

    def _use_textured(self) -> None:
        """Switch to textured shader program (skips if already active)."""
        if self._current_prog != self._tex_prog:
            _gl_UseProgram(self._tex_prog)
            self._current_prog = self._tex_prog

    def _upload(self, data: np.ndarray) -> int:
        """Upload vertex data to VBO via buffer orphaning (direct ctypes).

        Uses glBufferData (not glBufferSubData) to orphan the old buffer.
        This lets the GPU keep reading from the old allocation while we upload
        new data, avoiding implicit synchronization stalls.
        """
        byte_size = data.nbytes
        _gl_BufferData(GL_ARRAY_BUFFER, byte_size, data.ctypes.data, GL_DYNAMIC_DRAW)
        return byte_size

    def _draw_solid(self, vertices: np.ndarray, mode: int,
                    color, alpha: int = 255) -> None:
        """Upload vertices and draw with the solid color shader (direct ctypes)."""
        n = len(vertices)
        if n == 0:
            return

        self._use_solid()
        _gl_Uniform4f(self._s_u_color,
                      color[0] * _INV_255, color[1] * _INV_255,
                      color[2] * _INV_255, alpha * _INV_255)

        if not vertices.flags['C_CONTIGUOUS'] or vertices.dtype != np.float32:
            vertices = np.ascontiguousarray(vertices, dtype=np.float32)

        _gl_BufferData(GL_ARRAY_BUFFER, vertices.nbytes,
                       vertices.ctypes.data, GL_DYNAMIC_DRAW)
        _gl_VertexAttribPointer(self._s_a_position, 2, GL_FLOAT, 0, 0, None)
        _gl_DrawArrays(mode, 0, n)

    def _draw_textured_quad(self, tex_id: int, x: float, y: float,
                            w: float, h: float) -> None:
        """Draw a textured quad at (x, y) with size (w, h). Direct ctypes."""
        x2, y2 = x + w, y + h
        # interleaved: position(2) + texcoord(2), 6 vertices (2 triangles)
        verts = np.array([
            x,  y,  0.0, 0.0,
            x2, y,  1.0, 0.0,
            x,  y2, 0.0, 1.0,
            x2, y,  1.0, 0.0,
            x2, y2, 1.0, 1.0,
            x,  y2, 0.0, 1.0,
        ], dtype=np.float32)

        self._use_textured()

        _gl_ActiveTexture(GL_TEXTURE0)
        _gl_BindTexture(GL_TEXTURE_2D, tex_id)
        _gl_Uniform1i(self._t_u_texture, 0)

        _gl_BufferData(GL_ARRAY_BUFFER, verts.nbytes,
                       verts.ctypes.data, GL_DYNAMIC_DRAW)

        stride = 16  # 4 floats × 4 bytes
        _gl_VertexAttribPointer(self._t_a_position, 2, GL_FLOAT, 0,
                                stride, None)
        _gl_EnableVertexAttribArray(self._t_a_texcoord)
        _gl_VertexAttribPointer(self._t_a_texcoord, 2, GL_FLOAT, 0,
                                stride, _OFFSET_8)

        _gl_DrawArrays(GL_TRIANGLES, 0, 6)

    def _upload_texture(self, rgba_bytes: bytes, width: int, height: int) -> int:
        """Upload RGBA pixel data to a new GL texture. Returns texture ID."""
        tex_id = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, rgba_bytes)
        return tex_id

    @staticmethod
    def _circle_vertices(cx: float, cy: float, radius: float,
                         segments: int) -> np.ndarray:
        """Generate triangle fan vertices for a filled circle using pre-computed tables."""
        if segments == 16:
            unit = _UNIT_CIRCLE_16
        elif segments == 32:
            unit = _UNIT_CIRCLE_32
        elif segments == 64:
            unit = _UNIT_CIRCLE_64
        else:
            unit = _precompute_unit_circle(segments)

        # center + ring points (segments+1 includes closing vertex)
        n = len(unit)  # segments + 1
        verts = np.empty((n + 1, 2), dtype=np.float32)
        verts[0] = (cx, cy)
        verts[1:, 0] = cx + radius * unit[:, 0]
        verts[1:, 1] = cy + radius * unit[:, 1]
        return verts

    @staticmethod
    def _circle_outline_vertices(cx: float, cy: float, radius: float,
                                 segments: int) -> np.ndarray:
        """Generate line loop vertices for a circle outline using pre-computed tables."""
        if segments == 16:
            unit = _UNIT_CIRCLE_16
        elif segments == 32:
            unit = _UNIT_CIRCLE_32
        elif segments == 64:
            unit = _UNIT_CIRCLE_64
        else:
            unit = _precompute_unit_circle(segments)

        # Use segments points (not the closing vertex — GL_LINE_LOOP closes automatically)
        verts = np.empty((segments, 2), dtype=np.float32)
        verts[:, 0] = cx + radius * unit[:segments, 0]
        verts[:, 1] = cy + radius * unit[:segments, 1]
        return verts

    @staticmethod
    def _adaptive_segments(radius: float) -> int:
        """Choose segment count based on radius."""
        if radius < 10:
            return 16
        elif radius < 50:
            return 32
        else:
            return 64

    # ------ Renderer protocol methods ------

    def clear(self, color: Tuple[int, int, int]) -> None:
        _gl_ClearColor(color[0] * _INV_255, color[1] * _INV_255,
                        color[2] * _INV_255, 1.0)
        _gl_Clear(GL_COLOR_BUFFER_BIT)

    def draw_circle(self, center: Tuple[int, int], radius: int,
                    color: Tuple[int, int, int], alpha: int = 255,
                    border: int = 0) -> None:
        if alpha == 0:
            return
        segs = self._adaptive_segments(radius)
        if border == 0:
            verts = self._circle_vertices(center[0], center[1], radius, segs)
            self._draw_solid(verts, GL_TRIANGLE_FAN, color, alpha)
        else:
            verts = self._circle_outline_vertices(center[0], center[1], radius, segs)
            if border != self._current_line_width:
                _gl_LineWidth(float(border))
                self._current_line_width = border
            self._draw_solid(verts, GL_LINE_LOOP, color, alpha)

    def draw_polygon(self, points: List[Tuple[int, int]],
                     color: Tuple[int, int, int], alpha: int = 255,
                     border: int = 0) -> None:
        if len(points) < 3 or alpha == 0:
            return
        verts = np.array(points, dtype=np.float32)
        if border == 0:
            self._draw_solid(verts, GL_TRIANGLE_FAN, color, alpha)
        else:
            if border != self._current_line_width:
                _gl_LineWidth(float(border))
                self._current_line_width = border
            self._draw_solid(verts, GL_LINE_LOOP, color, alpha)

    def draw_line(self, start: Tuple[int, int], end: Tuple[int, int],
                  color: Tuple[int, int, int], alpha: int = 255,
                  width: int = 1) -> None:
        if alpha == 0:
            return
        verts = np.array([start, end], dtype=np.float32)
        if width != self._current_line_width:
            _gl_LineWidth(float(width))
            self._current_line_width = width
        self._draw_solid(verts, GL_LINES, color, alpha)

    def draw_lines(self, points: List[Tuple[int, int]],
                   color: Tuple[int, int, int], alpha: int = 255,
                   width: int = 1, closed: bool = False) -> None:
        if len(points) < 2 or alpha == 0:
            return
        verts = np.array(points, dtype=np.float32)
        if width != self._current_line_width:
            _gl_LineWidth(float(width))
            self._current_line_width = width
        mode = GL_LINE_LOOP if closed else GL_LINE_STRIP
        self._draw_solid(verts, mode, color, alpha)

    def draw_circles_batch(self, circles: List[Tuple[Tuple[int, int], int]],
                           color: Tuple[int, int, int], alpha: int = 255,
                           border: int = 0) -> None:
        if not circles or alpha == 0:
            return

        if border == 0:
            # Filled circles: convert each circle's triangle fan to explicit
            # GL_TRIANGLES (center, v_i, v_{i+1}), concatenate into single VBO
            all_tris = []
            for center, radius in circles:
                segs = self._adaptive_segments(radius)
                fan = self._circle_vertices(center[0], center[1], radius, segs)
                # fan[0] is center, fan[1:] are ring vertices
                # Convert fan to explicit triangles
                cx, cy = fan[0]
                for i in range(1, len(fan) - 1):
                    all_tris.append(fan[0])
                    all_tris.append(fan[i])
                    all_tris.append(fan[i + 1])

            if all_tris:
                verts = np.array(all_tris, dtype=np.float32)
                self._draw_solid(verts, GL_TRIANGLES, color, alpha)
        else:
            # Outline circles: draw each individually (GL_LINE_LOOP can't be batched)
            if border != self._current_line_width:
                _gl_LineWidth(float(border))
                self._current_line_width = border
            for center, radius in circles:
                segs = self._adaptive_segments(radius)
                verts = self._circle_outline_vertices(center[0], center[1], radius, segs)
                self._draw_solid(verts, GL_LINE_LOOP, color, alpha)

    def draw_lines_batch(self,
                         lines: List[Tuple[Tuple[int, int], Tuple[int, int]]],
                         color: Tuple[int, int, int], alpha: int = 255,
                         width: int = 1) -> None:
        if not lines or alpha == 0:
            return

        if width != self._current_line_width:
            _gl_LineWidth(float(width))
            self._current_line_width = width

        # Flatten to [start1, end1, start2, end2, ...] for GL_LINES
        verts = np.empty((len(lines) * 2, 2), dtype=np.float32)
        for i, (start, end) in enumerate(lines):
            verts[i * 2] = start
            verts[i * 2 + 1] = end

        self._draw_solid(verts, GL_LINES, color, alpha)

    def draw_line_batch(self, lines: List[Tuple[Tuple[int, int], Tuple[int, int],
                                                Tuple[int, ...], int]]) -> None:
        if not lines:
            return

        # Group lines by (color_rgba, width) for efficient batching
        groups: dict = {}
        for start, end, color, width in lines:
            r, g, b = color[0], color[1], color[2]
            a = color[3] if len(color) >= 4 else 255
            key = (r, g, b, a, width)
            if key not in groups:
                groups[key] = []
            groups[key].append(start)
            groups[key].append(end)

        for (r, g, b, a, width), pts in groups.items():
            verts = np.array(pts, dtype=np.float32)
            if width != self._current_line_width:
                _gl_LineWidth(float(width))
                self._current_line_width = width
            self._draw_solid(verts, GL_LINES, (r, g, b), a)

    def draw_text(self, text: str, position: Tuple[int, int],
                  color: Tuple[int, int, int], font_size: int = 24,
                  background: Optional[Tuple[int, int, int]] = None,
                  angle: float = 0.0) -> None:
        if not text:
            return

        # Cache key
        key = (text, font_size, color[:3], background, angle)
        cached = self._text_cache.get(key)

        if cached is not None:
            tex_id, tw, th = cached
            # Move to end (most recently used)
            self._text_cache.move_to_end(key)
        else:
            # Render with pygame.font
            if font_size not in self._fonts:
                self._fonts[font_size] = pygame.font.Font(None, font_size)
            font = self._fonts[font_size]
            text_surface = font.render(text, True, color[:3])

            if background:
                bg_rect = text_surface.get_rect().inflate(4, 2)
                bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
                bg_surface.fill((*background[:3], 255))
                bg_surface.blit(text_surface, (2, 1))
                text_surface = bg_surface

            if angle != 0.0:
                text_surface = pygame.transform.rotate(text_surface, angle)

            tw, th = text_surface.get_size()
            # Convert to RGBA bytes
            rgba_data = pygame.image.tostring(text_surface, "RGBA", False)

            tex_id = self._upload_texture(rgba_data, tw, th)
            self._owned_textures.append(tex_id)

            # Evict oldest if cache is full
            if len(self._text_cache) >= _TEXT_CACHE_MAX:
                _, (old_tex, _, _) = self._text_cache.popitem(last=False)
                glDeleteTextures(1, [old_tex])
                if old_tex in self._owned_textures:
                    self._owned_textures.remove(old_tex)

            self._text_cache[key] = (tex_id, tw, th)

        # Draw centered at position
        x = position[0] - tw // 2
        y = position[1] - th // 2
        self._draw_textured_quad(tex_id, x, y, tw, th)

    def create_image(self, rgba_bytes: bytes, width: int, height: int) -> int:
        """Upload RGBA data to a GL texture. Returns texture ID."""
        tex_id = self._upload_texture(rgba_bytes, width, height)
        self._owned_textures.append(tex_id)
        return tex_id

    def draw_image(self, handle: int, position: Tuple[int, int],
                   size: Tuple[int, int] = None) -> None:
        """Draw a GL texture at position. size=(w, h) or None to skip."""
        if size is None:
            return
        self._draw_textured_quad(handle, position[0], position[1],
                                 size[0], size[1])

    def blit_surface(self, surface, position: Tuple[int, int]) -> None:
        """Compatibility shim — not used by GLES path but kept for safety."""
        logger.warning("blit_surface called on GLESRenderer — ignored")

    def flip(self) -> None:
        pygame.display.flip()

    def tick(self, fps: int) -> float:
        if self.clock:
            return self.clock.tick(fps) / 1000.0
        return 0.0

    def get_events(self) -> List:
        return pygame.event.get()

    def quit(self) -> None:
        """Delete all GL resources and quit pygame."""
        # Clean up text cache textures
        tex_ids = [tid for tid, _, _ in self._text_cache.values()]
        if tex_ids:
            glDeleteTextures(len(tex_ids), tex_ids)
        self._text_cache.clear()

        # Clean up any remaining owned textures
        remaining = [t for t in self._owned_textures if t not in tex_ids]
        if remaining:
            glDeleteTextures(len(remaining), remaining)
        self._owned_textures.clear()

        pygame.quit()
        logger.info("GLESRenderer shut down")
