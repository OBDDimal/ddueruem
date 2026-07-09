import pytest

from counting import Counter
from formats import CNF

from frameworks import DDNNIFE_base as DDNNIFE
from frameworks import FeatJar

import preprocessing
from preprocessing import Arjun, PMC

from tempfile import NamedTemporaryFile


@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_atomic_set_elimination(file_test):

    cnf = CNF(from_file=file_test)

    cnf_ase, cores1, deads1 = preprocessing.simplify_atomic_sets(
        cnf, yield_core_dead=True
    )

    assert len(cores1) <= 1
    assert len(deads1) <= 1

    counter = Counter()

    assert counter.count(cnf) == counter.count(cnf_ase)

    cnf_ase_cd, cores2, deads2 = preprocessing.simplify_yield_unit_clauses(cnf_ase)

    assert cores1 == cores2
    assert deads1 == deads2

    assert cnf_ase.nv == cnf_ase_cd.nv

    assert counter.count(cnf) == counter.count(cnf_ase_cd)
    assert counter.count(cnf_ase) == counter.count(cnf_ase_cd)


@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_atomic_set_detection(file_test):

    cnf = CNF(from_file=file_test)
    asets, cores, deads = preprocessing.compute_atomic_sets(cnf, yield_core_dead=True)

    if len(cores) > 1:
        assert cores in asets
    else:
        assert cores not in asets

    if len(deads) > 1:
        assert deads in asets
    else:
        assert deads not in asets

    cache = set()

    for aset in asets:
        for x in aset:
            if x in cache:
                assert False

            cache.add(x)


def test_ddnnife_install():
    DDNNIFE.install()

    assert DDNNIFE.check()


@pytest.mark.depends(on=["test_ddnnife_install", "test_atomic_set_detection"])
@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_atomic_set_detection_ddnnife(file_test):

    cnf = CNF(from_file=file_test)

    asets_ddueruem = preprocessing.compute_atomic_sets(cnf)
    hashs1 = {hash(str(sorted(aset))) for aset in asets_ddueruem}

    asets_ddnnife = DDNNIFE.compute_atomic_sets(file_test)
    hashs2 = {hash(str(sorted(aset))) for aset in asets_ddnnife}

    assert hashs1 == hashs2


def test_featjar_install():
    FeatJar.install()

    assert FeatJar.check()


# @pytest.mark.skip(reason="Computation of atomic sets is currently broken in FeatJar https://github.com/FeatureIDE/FeatJAR-formula-analysis-sat4j/issues/5#issuecomment-2981753979")
@pytest.mark.depends(on=["test_featjar_install", "test_atomic_set_detection"])
@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_atomic_set_detection_featjar(file_test):

    cnf = CNF(from_file=file_test)

    asets_ddueruem = preprocessing.compute_atomic_sets(cnf)
    hashs1 = {hash(str(sorted(aset))) for aset in asets_ddueruem}

    asets_featjar = FeatJar.compute_atomic_sets(file_test)
    hashs2 = {hash(str(sorted(aset))) for aset in asets_featjar}

    assert hashs1 == hashs2


@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_xor_detection_detection(file_test):

    cnf = CNF(from_file=file_test)

    xor_variables, xor_groups, xor_groups_raw, clauses_rem = (
        preprocessing.identify_xor_groups(cnf)
    )

    for xg in xor_groups:
        for x in xg:
            if x not in xor_variables:
                assert False

    for xg in xor_groups_raw:
        for x in xg:
            if x not in xor_variables:
                assert False

    cache = set()
    for xg in xor_groups:

        for x in xg:
            if x in cache:
                assert False

            cache.add(x)


@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_core_dead_detection(file_test):

    cnf = CNF(from_file=file_test)

    cores1, deads1 = preprocessing.compute_core_deads(cnf)
    cores2, deads2 = preprocessing.compute_core_deads2(cnf)
    _, cores3, deads3 = preprocessing.compute_atomic_sets(cnf, yield_core_dead=True)

    assert isinstance(cores1, set)
    assert isinstance(cores2, set)
    assert isinstance(cores3, set)

    assert isinstance(deads1, set)
    assert isinstance(deads2, set)
    assert isinstance(deads3, set)

    assert cores1 == cores2
    assert cores2 == cores3

    assert deads1 == deads2
    assert deads2 == deads3


# PMC
def test_pmc_install():
    PMC.install()

    assert PMC.check()


@pytest.mark.depends(on=["test_pmc_install"])
@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_pmc(file_test):

    cnf = CNF(from_file=file_test)

    cnf_pp = PMC.run(file_test)

    assert cnf.nv == cnf_pp.nv

    counter = Counter()

    assert counter.count(cnf) == counter.count(cnf_pp)


# Arjun
def test_arjun_install():
    Arjun.install()

    assert Arjun.check()


@pytest.mark.depends(on=["test_arjun_install"])
@pytest.mark.parametrize(
    "file_test",
    [
        "__examples/busybox.dimacs",
        "__examples/jhipster.dimacs",
        "__examples/berkeleydb.dimacs",
        "__examples/automotive01.dimacs",
        "__examples/ea2468.dimacs",
    ],
)
def test_arjun(file_test):

    cnf = CNF(from_file=file_test)

    with NamedTemporaryFile(suffix=".dimacs") as ntf:
        Arjun.run(file_test, ntf.name, preserve_count=True)

        cnf_pp = CNF(from_file=ntf.name)

    # Arjun does typically not preserve the variables
    # assert cnf.nv == cnf_pp.nv

    # Arjun does typically not preserve the model count, but we force it by adding free variables
    counter = Counter()

    assert counter.count(cnf) == counter.count(cnf_pp)
