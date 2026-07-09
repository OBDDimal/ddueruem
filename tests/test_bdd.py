import pytest

from bdd import BDD
from bdd.compilers import CUDD

from formats import CNF

import preprocessing
from svo.heuristics import Force, ForceXG

from tempfile import NamedTemporaryFile


def test_cudd_install():
    CUDD.install()

    assert CUDD.check()


@pytest.mark.depends(on=["test_cudd_install"])
def test_simple_bdd_compilation():

    with BDD() as mgr:

        bdd, _ = mgr.compile_file("__examples/sandwich.dimacs")
        assert mgr.count_models(bdd) == 2808


testdata = [
    ("__examples/jhipster.dimacs", 26256),
    (
        "__examples/busybox.dimacs",
        2061138519356781760670618805653750167349287991336595876373542198990734653489713239449032049664199494301454199336000050382457451123894821886472278234849758979132037884598159833615564800000000000000000000,
    ),
    ("__examples/financialServices01.dimacs", 97451212554676),
]


@pytest.mark.depends(on=["test_cudd_install"])
@pytest.mark.parametrize("data", [*testdata])
def test_complex_bdd_compilation(data):

    filepath, expected_ssat = data

    with NamedTemporaryFile(suffix=".dddmp") as file:
        CUDD.compile(filepath, file_out=file.name, best=True)
        bdd = BDD(from_file=file.name)

        model_counts = bdd.count_models()

        assert model_counts == expected_ssat


@pytest.mark.depends(on=["test_cudd_install"])
@pytest.mark.parametrize("data", testdata)
def test_complex_bdd_compilation_ase(data):

    filepath, expected_ssat = data

    cnf2 = CNF(from_file=filepath)

    cnf = preprocessing.simplify_atomic_sets(cnf2)

    order1 = ForceXG.run(cnf)
    order2 = Force.run(cnf, order=[])

    assert len(order1) == len(order2)
    assert set(order1) == set(order2)

    with NamedTemporaryFile(suffix=".dddmp") as file:
        CUDD.compile(cnf, file.name, best=True)
        bdd = BDD(from_file=file.name)
        model_counts = bdd.count_models()
        assert model_counts == expected_ssat
