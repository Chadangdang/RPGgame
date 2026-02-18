from game.mixins.init_mixin import GameMainInitMixin
from game.mixins.logging_mixin import GameMainLoggingMixin
from game.mixins.flow_ui_mixin import GameMainFlowUiMixin
from game.mixins.update_mixin import GameMainUpdateMixin
from game.mixins.render_mixin import GameMainRenderMixin
from game.mixins.export_mixin import GameMainExportMixin


class GameMain(
    GameMainInitMixin,
    GameMainLoggingMixin,
    GameMainFlowUiMixin,
    GameMainUpdateMixin,
    GameMainRenderMixin,
    GameMainExportMixin,
):
    """Composed game controller assembled from focused mixins."""

    pass
