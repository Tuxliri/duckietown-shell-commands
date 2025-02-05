import argparse
import webbrowser
from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the dashboard for a DT robot"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "robot",
            help="Name of the robot to connect to"
        )
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = parser.parse_args(args)
        webbrowser.open(f"http://{parsed.robot}.local/dashboard/")
