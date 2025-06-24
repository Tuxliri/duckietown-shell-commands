import webbrowser

from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the dashboard for a DT robot"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = DTCommand.parser.parse_args(args)
        page = parsed.page.strip("/") if parsed.page else ""
        if page:
            page += "/"
        webbrowser.open(f"http://{parsed.robot}.local/dashboard/{page}")
