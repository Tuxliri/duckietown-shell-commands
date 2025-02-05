import webbrowser
from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the DT Documentation Library"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = DTCommand.parser.parse_args(args)
        if parsed.ente:
            version = "ente"
        else:
            version = "daffy"
        webbrowser.open(f"https://docs.duckietown.com/{version}/")
