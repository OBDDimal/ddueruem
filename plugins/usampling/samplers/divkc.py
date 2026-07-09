from frameworks import DivKC as DivKC_BASE

from ..usampler import USampler


class DivKC(DivKC_BASE, USampler):
    pass


USampler.register_plugin(DivKC)
