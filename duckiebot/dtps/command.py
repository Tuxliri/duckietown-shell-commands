import webbrowser

from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the DT Postal Service (DTPS) topic list for a DT robot"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        parsed = kwargs.get("parsed", None)
        if parsed is None:
            parsed = DTCommand.parser.parse_args(args)
        port = 11411 if parsed.kv_store else 11911
        topic = parsed.topic.strip("/") if parsed.topic else ""
        if topic:
            topic += "/"
        webbrowser.open(f"http://{parsed.robot}.local:{port}/{topic}")
