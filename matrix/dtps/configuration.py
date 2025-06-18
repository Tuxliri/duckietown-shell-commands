import argparse
from typing import List, Optional

from dt_shell.commands import DTCommandConfigurationAbs
from dt_shell.environments import ShellCommandEnvironmentAbs


class DTCommandConfiguration(DTCommandConfigurationAbs):
    @classmethod
    def aliases(cls) -> List[str]:
        """
        Alternative names for this command.
        """
        return []

    @classmethod
    def environment(cls, *args, **kwargs) -> Optional[ShellCommandEnvironmentAbs]:
        """
        The environment in which this command will run.
        """
        return None

    @classmethod
    def parser(cls, *args, **kwargs) -> Optional[argparse.ArgumentParser]:
        """
        The parser this command will use.
        """
        parser = argparse.ArgumentParser("dts matrix dtps")
        parser.add_argument(
            "-e",
            "--engine",
            dest="engine_hostname",
            default=None,
            type=str,
            help="Hostname or IP address of the engine to connect to"
        )
        parser.add_argument(
            "--topic",
            default=None,
            type=str,
            help="DTPS topic"
        )
        return parser
