import json
import re
from os import linesep

from formats import CNF
from pysat.solvers import Solver

from util.cli import cli, formatting

from .result import ResultIterable


class SampleResult(ResultIterable):

    @property
    def sample(self):
        return self.result

    def __str__(self):
        meta = self.meta

        if self.sample is not None:
            return f'Sample[{len(self.sample)}] {meta.get("file_in")} -> {meta.get("file_out")}'
        elif meta.get("timeout", False) is True:
            return f'Emtpy Sample (t/o) ({meta.get("file_in")})'
        else:
            return (
                f'Emtpy Sample (error: {meta.get("error", "")}) ({meta.get("file_in")})'
            )

    def __repr__(self):
        return f"|{str(self)}|"

    def render(self):

        file_out = self.meta.get("file_out")
        out = f"-> {formatting.h(file_out)}" if file_out else ""

        if self.success:
            cli.say(
                formatting.check(),
                f"{self.time_split},",
                len(self),
                "configurations",
                out,
            )
        else:
            print(self.meta)


def store_sample(
    file_in,
    sample,
    file_out,
    raw=False,
    remove_invalid=True,
    remove_duplicates=True,
    **kwargs,
):
    """save sample configurations to file"""

    cnf = CNF(from_file=file_in)

    sample, stats = process_sample(
        sample,
        raw=raw,
        verify_with=file_in if remove_invalid else None,
        remove_duplicates=remove_duplicates,
    )

    data = dict(
        nv=cnf.nv,
        size=len(sample),
        configurations=[" ".join([str(x) for x in conf]) for conf in sample],
    )

    with open(file_out, "w", encoding="utf-8") as file:
        if raw:
            lines = f'{linesep.join(data["configurations"])}{linesep}'
            file.write(lines)
        else:
            json.dump(data, file, indent=2)

    return stats


def load_sample(file_sample, expand=False):
    """load sample configurations from file"""

    sample = []
    try:

        with open(file_sample, "r", encoding="utf-8") as file:
            data = json.load(file)

        support = set(range(1, data["nv"] + 1))

        for line in data["configurations"]:

            config = re.split(r"\s+", line)
            config = {int(x) for x in config}

            if expand:
                for x in support:
                    if x not in config:
                        config.add(-x)

            sample.append(config)
    except json.JSONDecodeError:

        with open(file_sample, "r", encoding="utf-8") as file:
            raw = file.readlines()

        sample = [re.split(r"\s+", c.strip()) for c in raw]
        sample = [{int(x) for x in config} for config in sample]

    return sample


def process_sample(sample, raw=False, verify_with=None, remove_duplicates=True):
    """process samples"""

    n_invalid = None
    n_duplicates = None

    solver = None

    if verify_with is not None:
        cnf = CNF(from_file=verify_with)
        solver = Solver(bootstrap_with=cnf.clauses)
        n_invalid = 0

    if remove_duplicates:
        n_duplicates = 0

    sample_good = []

    cache = set()

    for config in sample:

        if solver is not None and not solver.solve(config):
            n_invalid += 1
            continue

        if raw:
            config = sorted([x for x in config], key=abs)
        else:
            config = sorted([x for x in config if x > 0])

        hsh = hash(str(config))

        if remove_duplicates and hsh in cache:
            n_duplicates += 1
            continue

        cache.add(hsh)
        sample_good.append(config)

    if solver is not None:
        solver.delete()

    sample_good = sorted(sample_good)
    sample_good = sorted(sample_good, key=len)

    return sample_good, dict(n_invalid=n_invalid, n_duplicates=n_duplicates)
