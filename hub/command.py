import webbrowser
from dt_shell import DTCommandAbs, DTShell


class DTCommand(DTCommandAbs):
    help = "Opens the DT Hub"

    @staticmethod
    def command(shell: DTShell, args, **kwargs):
        webbrowser.open("https://hub.duckietown.com/")
