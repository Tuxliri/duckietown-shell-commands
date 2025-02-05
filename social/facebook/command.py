import webbrowser
from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the DT Facebook page"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = DTCommand.parser.parse_args(args)
        webbrowser.open("https://www.facebook.com/duckietown/")
