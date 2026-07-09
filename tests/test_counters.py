import pytest

from counting import Counter


@pytest.mark.parametrize("counter", Counter.get_plugins())
def test_install(counter):
    counter.install()


@pytest.mark.depends(on=["test_install"])
def test_spur_as_default_counter():

    counter = Counter()
    _test_counter(counter)


@pytest.mark.depends(on=["test_install"])
@pytest.mark.parametrize("counter", Counter.get_plugins())
def test_counter(counter):
    _test_counter(counter)


def _test_counter(counter):
    counter.count("__examples/sandwich.dimacs") == 2808
    counter.count(
        "__examples/busybox.dimacs"
    ) == 2061138519356781760670618805653750167349287991336595876373542198990734653489713239449032049664199494301454199336000050382457451123894821886472278234849758979132037884598159833615564800000000000000000000


@pytest.mark.depends(on=["test_counter"])
@pytest.mark.parametrize("counter", Counter.get_plugins())
def test_cardinalities(counter):
    cardinalities = {
        1: 936,
        2: 2496,
        3: 1296,
        4: 2592,
        5: 1248,
        6: 1404,
        7: 936,
        8: 2808,
        9: 2457,
        10: 2808,
        11: 1248,
        12: 936,
        13: 1404,
        14: 864,
        15: 1728,
        16: 1248,
        17: 1404,
        18: 864,
        19: 1296,
    }

    assert counter.cardinalities("__examples/sandwich.dimacs") == cardinalities
