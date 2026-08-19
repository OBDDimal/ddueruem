from tempfile import NamedTemporaryFile

import pytest
from bdd import BDD, BDD_Compiler


@pytest.mark.parametrize("compiler", BDD_Compiler.get_plugins())
def test_install(compiler):
    compiler.install()
    assert compiler.check()


@pytest.mark.depends(on=["test_install"])
@pytest.mark.parametrize("compiler", BDD_Compiler.get_plugins())
def test_simple_bdd_compilation(compiler):

    if compiler.__name__.lower() == "cnf2obdd":
        pytest.skip("cnf2obdd does not support dddmp")

    with NamedTemporaryFile(suffix=".dddmp") as file:

        compiler.compile("__examples/sandwich.dimacs", order=None, file_out=file.name)
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


@pytest.mark.depends(on=["test_install"])
@pytest.mark.parametrize("data", [*testdata])
@pytest.mark.parametrize("compiler", BDD_Compiler.get_plugins())
def test_complex_bdd_compilation(data, compiler):

    if compiler.__name__.lower() == "cnf2obdd":
        pytest.skip("cnf2obdd does not support dddmp")

    filepath, expected_ssat = data

    with NamedTemporaryFile(suffix=".dddmp") as file:
        compiler.compile(filepath, file_out=file.name, best=True)
        bdd = BDD(from_file=file.name)

        assert bdd.count_models() == expected_ssat
