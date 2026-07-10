"""General tool wrapper

To install tool:
> ddueruem install <tool>

To run tool:
> ddueruem run tool -- --help"""

import frameworks
import preprocessing
from bdd import BDD_Compiler
from climplicit import command, tool
from svo import SVO
from tsampling import TSampler
from usampling import USampler

from util.cli import cli, formatting
from util.plugins import Executable


@tool("ddueruem", desc="Wraps raw tools but ensures dependencies etc.")
class DDUERUEM:

    @classmethod
    def _find_tool(cls, stub):

        stub2plugin = USampler.get_plugins_dict()
        stub2plugin.update(TSampler.get_plugins_dict())
        stub2plugin.update(SVO.get_plugins_dict())
        stub2plugin.update(BDD_Compiler.get_plugins_dict())
        stub2plugin.update(preprocessing.get_plugins_dict())
        stub2plugin.update(frameworks.get_plugins_dict())

        # print(stub2plugin)
        # print(stub2plugin.get(stub.strip().lower()))

        if tool := stub2plugin.get(stub.strip().lower()):
            return tool
        else:
            cli.warn("Tool", formatting.h(stub), "is not available in ddueruem.")

    @classmethod
    @command()
    def install(cls, stub):

        tool = cls._find_tool(stub)

        if tool.check():
            cli.say(
                formatting.check(),
                formatting.h(stub),
                formatting.good("is already installed"),
            )
        else:
            tool.install()
            if tool.check():
                cli.say(
                    formatting.check(),
                    formatting.h(stub),
                    formatting.good("was successfully installed"),
                )
            else:
                cli.error(
                    formatting.check(), formatting.h(stub), "Installation failed!"
                )

        pass

    @classmethod
    @command(hides = ["help"])
    def run(cls, stub, *args):

        tool = cls._find_tool(stub)
        if tool and issubclass(tool, Executable):

            args = " ".join(args)
            tool.plain(args)
        else:
            cli.say(formatting.h(stub), "does not have a CLI.")
