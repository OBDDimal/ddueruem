import pytest

from tempfile import NamedTemporaryFile

from usampling import USampler


@pytest.mark.parametrize("sampler", USampler.get_plugins())
def test_install(sampler):
    sampler.install()
    assert sampler.check()


@pytest.mark.depends(on=["test_install"])
@pytest.mark.parametrize("sampler", USampler.get_plugins())
def test_simple_sampling(sampler):
    sample = sampler.sample(
        file_in="__examples/sandwich.dimacs",
        size=16,
        remove_duplicates=False,
        timeout=5,
    )

    assert sample.success is True
    assert sample.timeouted is False

    if sampler.__name__ in ["Unigen", "Quicksampler"]:
        assert len(sample) > 0
    else:
        assert len(sample) == 16


@pytest.mark.depends(on=["test_install"])
@pytest.mark.parametrize("sampler", USampler.get_plugins())
def test_error_sampling(sampler):

    with NamedTemporaryFile(suffix=".dimacs") as file:
        with open(file.name, "w+") as fh:
            fh.write("can't parse me")

        sample = sampler.sample(
            file_in=file.name, size=16, remove_duplicates=False, timeout=5
        )

    assert sample.success is False
    assert sample.timeouted is False
    assert sample.meta.get("error") is not None


@pytest.mark.depends(on=["test_install"])
@pytest.mark.parametrize("sampler", USampler.get_plugins())
def test_timeout_sampling(sampler):
    """Unrealistic test to test the timeouting of the samplers"""

    if sampler.__name__ in ["CMSGen", "Quicksampler"]:
        assert True
        return

    sample = sampler.sample(
        file_in="__examples/linux2.6.33.3.dimacs",
        size=1024,
        remove_duplicates=False,
        timeout=5,
    )

    assert sample.success is False
    assert sample.timeouted is True
