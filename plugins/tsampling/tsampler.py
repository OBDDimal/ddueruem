import subprocess
from abc import ABC, abstractmethod
from tempfile import NamedTemporaryFile

from climplicit import command, tool
from formats import CNF, ensure_CNF2File

from util.cli import cli, formatting
from util.exceptions import UnexpectedStatuscodeException
from util.plugins import Extendable
from util.runner import with_timeout
from util.sample import SampleResult, load_sample, store_sample


@tool("tsample", desc="CLI interface for t-wise sampling")
class TSampler(ABC, Extendable):

    @classmethod
    @command(
        shorts={"file_out": "o", "verbose": "v", "quiet": "q"},
        pseudos={"file_out": "out"},
        descs={
            "file_in": "Path to input CNF in DIMACS format",
            "file_out": "Path for exporting the sample to",
            "t": 'Putting the "t" in t-wise...',
            "timeout": "Timeout in s",
            "raw": "Store configurations raw line-wise",
            "quiet": "Silences all terminal output",
            "verbose": "Prints result to the command line",
        },
        values={"sampler": lambda: TSampler.get_plugin_stubs()},
    )
    def sample_with(
        cls,
        sampler,
        file_in,
        file_out=None,
        t: int = 2,
        timeout: int | None = None,
        raw=False,
        quiet=False,
        verbose=False,
        **kwargs,
    ):
        if quiet and verbose:
            cli.say(
                formatting.warn(
                    f'Both {formatting.h("quiet")} and {formatting.h("verbose")} have been specified. Aborting.'
                ),
                error=True,
            )
            return

        result = cls.get_plugin(sampler).sample(
            file_in, file_out=file_out, t=t, timeout=timeout, raw=raw, **kwargs
        )
        result.render()

        if verbose:
            cnf = CNF(from_file=file_in)
            cli.say()
            cli.say(formatting.heading("# Output ".ljust(32, "-")))
            cli.say(f"NV:{cnf.nv}", f"NC:{len(cnf.clauses)}")
            for config in result:
                print(" ".join([str(x) for x in sorted(config, key=abs)]))

    @classmethod
    @ensure_CNF2File
    def sample(
        cls,
        file_in,
        file_out=None,
        t=2,
        timeout=None,
        remove_invalid=True,
        remove_duplicates=True,
        raw=False,
        **kwargs,
    ):

        if not cls.check():
            raise Exception(f'{cls.__name__} is not installed, aborting.')

        sample = None
        try:
            with NamedTemporaryFile() as file_temp:

                tempfile = file_temp.name

                call = with_timeout(
                    cls._sample_twise, file_in, tempfile, t=t, timeout=timeout, **kwargs
                )

                sample = cls.format_twise(file_in, tempfile)

                file_store = file_out if file_out else tempfile
                stats = store_sample(
                    file_in,
                    sample,
                    file_store,
                    remove_invalid=remove_invalid,
                    remove_duplicates=remove_duplicates,
                    raw=raw,
                    **kwargs,
                )

                meta = dict(
                    success=True,
                    timeout=False,
                    times=call.times,
                    file_in=file_in,
                    file_out=file_out,
                    stats=stats,
                )

                sample = load_sample(file_store, expand=False)

        except subprocess.TimeoutExpired:
            meta = dict(success=False, timeout=True, file_in=file_in)

        except (Exception, UnexpectedStatuscodeException) as ex:
            meta = dict(success=False, timeout=False, file_in=file_in, error=ex)

        return SampleResult(sample, meta=meta)

    @classmethod
    @abstractmethod
    def _sample_twise(cls, file_in, file_out, t=2, **kwargs):
        pass

    @classmethod
    @abstractmethod
    def format_twise(cls, file_in, file_out):
        pass

    @classmethod
    def count_ints2(cls, sample, nvars):

        ints2 = dict()

        variables = set(range(1, nvars + 1))

        for config in sample:

            missing = variables.difference(config)
            config.update({-x for x in missing})

            config = sorted(config, key=abs)

            for i, x in enumerate(config):

                literals = ints2.get(x, set())
                literals.update(config[i + 1 :])
                ints2[x] = literals

        return sum([len(literals) for _, literals in ints2.items()])
