import logging
from tempfile import NamedTemporaryFile

import pytest
from bdd import BDD
from bdd.compilers import CUDD, OxiDD
from formats import CNF
from pysat.solvers import Solver
from tsampling import TSampler
from tsampling.samplers import YASA

log = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def setup_once():

    OxiDD.install()

    for sampler in TSampler.get_plugins():
        sampler.install()

    yield "test_tsampling: Setup done"


@pytest.mark.parametrize("sampler", TSampler.get_plugins())
def test_simple_sampling(sampler):

    file_in = "__examples/sandwich.dimacs"
    cnf = CNF(from_file=file_in)

    sample = sampler.sample(file_in=file_in, t=2, remove_duplicates=False)

    assert len(sample) > 5
    assert TSampler.count_ints2(sample, nvars=cnf.nv) == 596


@pytest.mark.parametrize("sampler", TSampler.get_plugins())
def test_medium_sampling(sampler):

    file_in = "__examples/busybox.dimacs"
    cnf = CNF(from_file=file_in)

    sample = sampler.sample(file_in=file_in, t=2, remove_duplicates=False)

    with Solver(bootstrap_with=cnf.clauses) as solver:
        for config in sample:
            assert solver.solve(config)

    assert len(sample) > 5
    assert TSampler.count_ints2(sample, nvars=cnf.nv) == 1387048


@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
    ],
)
def test_2wise_counting_easy(file_test):

    with NamedTemporaryFile(suffix=".dddmp") as ntf:
        OxiDD.compile(file_test, file_out=ntf.name, complement_edges=False, best=True)
        bdd = BDD(from_file=ntf.name)

        CUDD.compile(file_test, file_out=ntf.name, complement_edges=False, best=True)
        bdd2 = BDD(from_file=ntf.name)

    count_bdd, _ = bdd.count_2wise()
    count_bdd2, _ = bdd2.count_2wise()
    assert count_bdd == count_bdd2

    count_featjar = YASA._count_twise(file_test)
    assert count_bdd == count_featjar
