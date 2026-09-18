"""
OpenGL present: GPU-scale the 720p canvas AND draw ultrawide bezels.

Uses moderngl if installed. Avoids pygame._sdl2 Texture (broken colorkey
on Windows pygame 2.6).
"""
from __future__ import annotations

import pygame

from settings import BASE_WIDTH, BASE_HEIGHT

_VS = """
#version 330
in vec2 in_vert;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    v_uv = in_uv;
}
"""

_FS = """
#version 330
uniform sampler2D image;
in vec2 v_uv;
out vec4 f_color;
void main() {
    f_color = texture(image, v_uv);
}
"""


def _rect_quad(x, y, w, h, sw, sh):
    """Pixel rect → NDC triangle strip (pygame y-down)."""
    if sw <= 0 or sh <= 0 or w <= 0 or h <= 0:
        return None
    x0 = 2.0 * x / sw - 1.0
    x1 = 2.0 * (x + w) / sw - 1.0
    y0 = 1.0 - 2.0 * (y + h) / sh
    y1 = 1.0 - 2.0 * y / sh
    # strip: TL, BL, TR, BR
    return [
        x0, y1, 0.0, 1.0,
        x0, y0, 0.0, 0.0,
        x1, y1, 1.0, 1.0,
        x1, y0, 1.0, 0.0,
    ]


class GlPresenter:
    def __init__(self):
        self.active = False
        self.last_error = ""
        self.size = (BASE_WIDTH, BASE_HEIGHT)
        self._ctx = None
        self._prog = None
        self._game_tex = None
        self._left_tex = None
        self._right_tex = None
        self._bezel_key = None
        self._vao = None
        self._vbo = None

    def close(self):
        self.active = False
        self._prog = None
        self._game_tex = None
        self._left_tex = None
        self._right_tex = None
        self._vao = None
        self._vbo = None
        self._ctx = None
        self._bezel_key = None

    def bind(self, size):
        """Call after set_mode(..., OPENGL). Returns False if moderngl missing."""
        self.close()
        try:
            import moderngl
        except Exception as e:
            self.last_error = "moderngl not installed: %s" % e
            print("GPU-GL:", self.last_error)
            print("  python -m pip install moderngl")
            return False
        try:
            self._ctx = moderngl.create_context()
            self._ctx.enable(moderngl.BLEND)
            self._ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            self._prog = self._ctx.program(vertex_shader=_VS, fragment_shader=_FS)
            self._game_tex = self._ctx.texture((BASE_WIDTH, BASE_HEIGHT), 3)
            self._game_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._game_tex.repeat_x = False
            self._game_tex.repeat_y = False
            self._vbo = self._ctx.buffer(reserve=16 * 4)
            self._vao = self._ctx.simple_vertex_array(
                self._prog, self._vbo, "in_vert", "in_uv"
            )
            self.size = (int(size[0]), int(size[1]))
            self.active = True
            print("GPU-GL present ready", self.size)
            return True
        except Exception as e:
            self.last_error = str(e)
            print("GPU-GL bind failed:", e)
            self.close()
            return False

    def _tex_from_surf(self, surf):
        if surf is None or self._ctx is None:
            return None
        try:
            rgb = pygame.Surface(surf.get_size(), 0, 24)
            rgb.blit(surf, (0, 0))
            data = pygame.image.tostring(rgb, "RGB", False)
            tex = self._ctx.texture(rgb.get_size(), 3, data)
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex.repeat_x = False
            tex.repeat_y = False
            return tex
        except Exception as e:
            print("GPU-GL bezel tex:", e)
            return None

    def _sync_bezels(self, left, right, key):
        if key == self._bezel_key:
            return
        self._bezel_key = key
        self._left_tex = self._tex_from_surf(left)
        self._right_tex = self._tex_from_surf(right)

    def _draw_quad(self, tex, x, y, w, h, sw, sh):
        verts = _rect_quad(x, y, w, h, sw, sh)
        if verts is None or tex is None:
            return
        import struct
        self._vbo.write(struct.pack("16f", *verts))
        tex.use(0)
        self._prog["image"] = 0
        self._vao.render(mode=self._ctx.TRIANGLE_STRIP)

    def present(self, game_surface, dest_rect, left_surf=None, right_surf=None,
                bezel_key=None, shake=(0, 0)):
        if not self.active or self._ctx is None:
            return False
        try:
            sw, sh = self.size
            data = pygame.image.tostring(game_surface, "RGB", False)
            self._game_tex.write(data)
            self._ctx.viewport = (0, 0, sw, sh)
            self._ctx.clear(0.0, 0.0, 0.0, 1.0)
            if left_surf is not None or right_surf is not None:
                self._sync_bezels(left_surf, right_surf, bezel_key)
                if self._left_tex is not None and dest_rect.x > 0:
                    self._draw_quad(self._left_tex, 0, 0, dest_rect.x, sh, sw, sh)
                rw = max(0, sw - dest_rect.right)
                if self._right_tex is not None and rw > 0:
                    self._draw_quad(self._right_tex, dest_rect.right, 0, rw, sh, sw, sh)
            dx = dest_rect.x + int(shake[0])
            dy = dest_rect.y + int(shake[1])
            self._draw_quad(
                self._game_tex, dx, dy, dest_rect.width, dest_rect.height, sw, sh
            )
            pygame.display.flip()
            return True
        except Exception as e:
            self.last_error = str(e)
            print("GPU-GL frame failed:", e)
            self.active = False
            return False
