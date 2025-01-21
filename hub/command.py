from dt_shell import DTCommandAbs, DTShell
from utils.assets_utils import get_asset_icon_path
from utils.duckietown_viewer_utils import \
    ensure_duckietown_viewer_installed, launch_viewer

LAUNCHER_NAME = "hub"
ICON_ASSET = "icon.png"


class DTCommand(DTCommandAbs):
    help = "Opens the DT Hub"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = DTCommand.parser.parse_args(args)
        # ---
        # make sure the app is installed
        ensure_duckietown_viewer_installed()
        # launch viewer
        launch_viewer(
            LAUNCHER_NAME,
            verbose=parsed.vv,
            fullscreen=True,
            menu=True,
            window_args={
                "icon": get_asset_icon_path(ICON_ASSET),
                "url": "https://hub.duckietown.com/",
                "min-width": 694,
                "min-height": 634
            }
        )
