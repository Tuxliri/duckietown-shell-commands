import argparse
import webbrowser
from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the DT Documentation Library"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--ente",
            default=False,
            action="store_true",
            help="Open the ente version of the DT Documentation Library"
        )
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = parser.parse_args(args)
        if parsed.ente:
            version = "ente"
        else:
            version = "daffy"
        webbrowser.open(f"https://docs.duckietown.com/{version}/")
