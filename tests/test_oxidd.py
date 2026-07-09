import pytest

from bdd import BDD
from bdd.compilers import OxiDD


from frameworks.dimagic import Dimagic

from tempfile import NamedTemporaryFile


def test_oxidd_install():
    Dimagic.install()
    assert Dimagic.check()

    OxiDD.install()
    assert OxiDD.check()


@pytest.mark.depends(on=["test_oxidd_install"])
def test_simple_bdd_compilation():

    with NamedTemporaryFile(suffix=".dddmp") as file:

        OxiDD.compile("__examples/sandwich.dimacs", order=None, file_out=file.name)
        bdd = BDD(from_file=file.name)

    assert bdd.count_models() == 2808


testdata = [
    ("__examples/jhipster.dimacs", 26256),
    (
        "__examples/busybox.dimacs",
        2061138519356781760670618805653750167349287991336595876373542198990734653489713239449032049664199494301454199336000050382457451123894821886472278234849758979132037884598159833615564800000000000000000000,
    ),
    ("__examples/financialServices01.dimacs", 97451212554676),
]


@pytest.mark.depends(on=["test_oxidd_install"])
@pytest.mark.parametrize("data", [*testdata])
def test_complex_bdd_compilation(data):

    filepath, expected_ssat = data

    with NamedTemporaryFile(suffix=".dddmp") as file:
        OxiDD.compile(filepath, file_out=file.name, complement_edges=False, best=True)
        bdd = BDD(from_file=file.name)

        assert bdd.count_models() == expected_ssat
