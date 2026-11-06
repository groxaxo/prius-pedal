import pyray as rl

from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget


class PriusBannerWidget(Widget):
  """Decorative home-screen image, fitted without cropping the supplied car."""

  def __init__(self):
    super().__init__()
    self._texture = gui_app.texture("images/prius_pedal_banner.png")
    rl.set_texture_filter(self._texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)

  def _render(self, rect: rl.Rectangle):
    if rect.width <= 0 or rect.height <= 0:
      return
    rl.draw_rectangle_rounded(rect, 0.025, 10, rl.Color(13, 18, 26, 255))
    if self._texture.width <= 0 or self._texture.height <= 0:
      return

    scale = min(rect.width / self._texture.width, rect.height / self._texture.height)
    width, height = self._texture.width * scale, self._texture.height * scale
    destination = rl.Rectangle(rect.x + (rect.width - width) / 2, rect.y + (rect.height - height) / 2, width, height)
    source = rl.Rectangle(0, 0, self._texture.width, self._texture.height)
    rl.draw_texture_pro(self._texture, source, destination, rl.Vector2(0, 0), 0, rl.WHITE)
