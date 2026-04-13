from dt_shell import DTCommandAbs, DTShell
from utils.assets_utils import get_asset_icon_path
from utils.duckietown_viewer_utils import \
    ensure_duckietown_viewer_installed, launch_viewer

# NOTE: this must match the name of the launcher in the dt-duckietown-viewer project
LAUNCHER_NAME = "led_controller"
ICON_ASSET = "icon-led-control.png"


class DTCommand(DTCommandAbs):
    help = "Runs the LED controller"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = DTCommand._resolve_parsed(args, kwargs.get("parsed"))
        # ---
        # make sure the app is installed
        ensure_duckietown_viewer_installed()
        # launch viewer
        launch_viewer(
            LAUNCHER_NAME,
            robot=parsed.robot,
            verbose=parsed.verbose,
            fullscreen=parsed.fullscreen,
            on_top=parsed.on_top,
            enable_hardware_acceleration=parsed.enable_hardware_acceleration,
            browser=parsed.browser,
            window_args={
                "icon": get_asset_icon_path(ICON_ASSET),
                "min-height": 600,
                "min-width": 600,
                "width": 600,
            }
        )
