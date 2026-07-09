from abc import ABC, abstractmethod
from tempfile import NamedTemporaryFile

from climplicit import command, tool
from formats import CNF, ensure_CNF2File
from svo import SVO

from util.benchmarking import tic, toc
from util.cli import cli, formatting
from util.plugins import Extendable
from util.result import BDDResult
from util.runner import with_timeout


@tool("bdd", desc="CLI tool to build BDDs")
class BDD_Compiler(ABC, Extendable):

    @classmethod
    @command(
        desc="""
        Compile BDDs from DIMACS CNF.

        See `bdd compiler --help` for compiler-specific options and limitations, e.g.:
        `bdd cudd --help`
        """,
        shorts={"file_out": "o", "verbose": "v", "quiet": "q"},
        pseudos={"file_out": "out"},
        values={
            "compiler": lambda: BDD_Compiler.get_plugin_stubs(),
            "svo": lambda: SVO.get_plugin_stubs(),
        },
        descs={
            "file_in": "Path to input CNF in DIMACS format",
            "file_out": "Path for exporting the BDD to",
            "best": "Use compiler-specific pre, svo and build configuration",
            "svo": "Static Variable Ordering to perform",
            "timeout": "Timeout in s",
            "quiet": "Silences all terminal output",
            "verbose": "Prints result to the command line",
        },
        resolvers={"compiler": (lambda x: BDD_Compiler.get_plugin(x), "_compile")},
    )
    def build_with(
        cls,
        compiler,
        file_in,
        file_out=None,
        best=False,
        svo=None,
        timeout: int = None,
        quiet=False,
        verbose=False,
        **kwargs,
    ):
        if quiet and verbose:
            cli.warn(
                f'Both {formatting.h("quiet")} and {formatting.h("verbose")} have been specified. Aborting.',
                error=True,
            )
            return

        if best and svo:
            cli.say(
                f'Note that {formatting.h("--best")} superseeds {formatting.h("--svo")} ',
                error=True,
            )
            svo = None

        order = None
        if svo is not None:
            tic()
            order = SVO.get_plugin(svo).run(file_in)
            time_svo = toc()

        result = cls.get_plugin(compiler).compile(
            file_in,
            file_out=file_out,
            order=order,
            best=best,
            timeout=timeout,
            **kwargs,
        )

        result.add_meta("compiler", compiler)

        if svo is not None:
            result.add_time("time_pre", time_svo)

        result.render()

    @classmethod
    @ensure_CNF2File
    def compile(
        cls,
        file_in,
        file_out=None,
        order=None,
        best=False,
        timeout=None,
        soft=False,
        **kwargs,
    ):
        """meta function for BDD compilation"""

        if soft and cls.supports_soft_timeout():
            if timeout:
                soft, timeout = timeout, None
            else:
                cli.warn(
                    formatting.h("--soft"),
                    "is ignored, as",
                    formatting.h("--timeout"),
                    "was not specified.",
                )
        elif soft and not cls.supports_soft_timeout():
            cli.warn(
                formatting.h("--soft"),
                "is ignored, as",
                formatting.h(cls.__name__),
                "lacks support.",
            )

        try:
            with NamedTemporaryFile(suffix=".dimacs") as ntf:
                file_tmp = ntf.name

                cnf = CNF(from_file=file_in)
                cnf.sanitize_variable_names()
                if order is not None:
                    cnf.save_with_order(file_tmp, order, align_clauses=True)
                else:
                    cnf.to_file(file_tmp)

                call = with_timeout(
                    cls._compile,
                    file_tmp,
                    file_out,
                    order=order,
                    timeout=timeout,
                    best=best,
                    soft=soft,
                    **kwargs,
                )

            if file_out:
                cls.format_dddmp(file_out)

            time_pre, time_kc, time_export, size = cls.extract_meta(call, file_out)

            return BDDResult(
                meta=dict(
                    success=True,
                    timeout=False,
                    size=size,
                    times=dict(
                        time_pre=time_pre, time_kc=time_kc, time_export=time_export
                    ),
                    file_in=file_in,
                    file_out=file_out,
                )
            )
        except TimeoutError as e:
            return BDDResult(success=False, timeout=True, file_in=file_in, error=e)
        except Exception as e:
            return BDDResult(success=False, timeout=False, file_in=file_in, error=e)

    @classmethod
    @abstractmethod
    def _compile(cls):
        pass

    @classmethod
    @abstractmethod
    def extract_meta(cls):
        pass

    @classmethod
    @abstractmethod
    def format_dddmp(cls):
        pass

    @classmethod
    def supports_soft_timeout(cls):
        return False
