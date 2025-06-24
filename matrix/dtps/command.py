import webbrowser

from dt_shell import DTCommandAbs, DTShell

DEFAULT_DUCKIEMATRIX_ENGINE_PORT = 7501


class DTCommand(DTCommandAbs):
    help = "Opens the DT Postal Service (DTPS) topic list for the Duckiematrix"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = DTCommand.parser.parse_args(args)
        engine_hostname = parsed.engine_hostname if parsed.engine_hostname is not None else "localhost"
        topic = parsed.topic.strip("/") if parsed.topic else ""
        if topic:
            topic += "/"
        webbrowser.open(f"http://{engine_hostname}:{DEFAULT_DUCKIEMATRIX_ENGINE_PORT}/{topic}")
