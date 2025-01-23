import argparse
from dt_shell.commands import DTCommandConfigurationAbs
from dt_shell.environments import ShellCommandEnvironmentAbs
from typing import Optional, List

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
        parser = argparse.ArgumentParser("dts docs library")
        parser.add_argument(
            "-vv",
            default=False,
            action="store_true",
            help="Run in verbose mode"
        )
        parser.add_argument(
            "--daffy",
            default=False,
            action="store_true",
            help="Open the daffy version of the DT Documentation Library"
        )
        return parser
