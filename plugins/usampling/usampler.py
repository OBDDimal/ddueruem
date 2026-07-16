"""Abstract wrapper class for uniform samplers"""

import traceback
from abc import ABC, abstractmethod
from os import path
from tempfile import NamedTemporaryFile

from climplicit import command, tool
from formats import CNF

from util.cli import cli, formatting
from util.exceptions import UnexpectedStatuscodeException
from util.plugins import Extendable
from util.runner import with_timeout
from util.sample import SampleResult, load_sample, store_sample


@tool("usample", desc="CLI interface for uniform sampling")
class USampler(ABC, Extendable):
    """Abstract wrapper class for uniform samplers"""

    @classmethod
    @command(
        shorts={"file_out": "o", "verbose": "v", "quiet": "q"},
        pseudos={"file_out": "out"},
        descs={
            "file_in": "Path to input CNF in DIMACS format",
            "file_out": "Path for exporting the sample to",
            "size": "Target size of the sample",
            "timeout": "Timeout in s",
            "raw": "Store configurations raw line-wise",
            "quiet": "Silences all terminal output",
            "verbose": "Prints result to the command line",
        },
        values={"sampler": lambda: USampler.get_plugin_stubs()},
    )
    def sample_with(
        cls,
        sampler,
        file_in,
        file_out=None,
        size: int = 1024,
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
            file_in, file_out=file_out, size=size, timeout=timeout, raw=raw, **kwargs
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
    def sample(
        cls,
        file_in,
        file_out=None,
        payload=None,
        size=1024,
        timeout=None,
        sparse=False,
        seed=None,
        **kwargs,
    ):
        """meta function for uniform sampling"""

        if not cls.check():
            raise Exception(f'{cls.__name__} is not installed, aborting.')

        if payload is None:
            payload = {}

        seed = payload.pop("seed", seed)
        file_in = path.abspath(file_in)

        sample = None
        try:
            with NamedTemporaryFile() as file_temp:
                call = with_timeout(
                    cls._sample_uniform,
                    file_in,
                    file_temp.name,
                    size=size,
                    seed=seed,
                    timeout=timeout,
                    **payload,
                )

                sample = cls.format_uniform(file_in, file_temp.name)
                file_store = file_out if file_out else file_temp.name

                stats = store_sample(file_in, sample, file_store, **kwargs)

                meta = dict(
                    success=True,
                    timeout=False,
                    times=call.times,
                    file_in=file_in,
                    file_out=file_out,
                    stats=stats,
                )
                if seed is not None:
                    meta["seed"] = seed

                if sparse:
                    sample = None
                    return meta
                else:
                    sample = load_sample(file_store)

        except TimeoutError:
            meta = dict(success=False, timeout=True, file_in=file_in, file_out=file_out)

        except Exception, UnexpectedStatuscodeException:
            meta = dict(
                success=False,
                timeout=False,
                file_in=file_in,
                file_out=file_out,
                error=traceback.format_exc(),
            )

        finally:
            cls.cleanup(file_in)

        if not sparse:
            return SampleResult(sample, meta=meta)
        else:
            return meta

    @classmethod
    @abstractmethod
    def format_uniform(cls, file_in, file_out):
        """ Wrapper classes need to implement this function that\
            parses the sample files yielded by the samplers """

    @classmethod
    @abstractmethod
    def cleanup(cls, file_in):
        """Cleanup after execution / timeout"""

    @classmethod
    @abstractmethod
    def _sample_uniform(cls, file_in, file_out, size):
        pass
