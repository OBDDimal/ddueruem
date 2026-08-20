from frameworks import DDNNIFE as DDNNIFE_base

from ..tsampler import TSampler


class DDNNIFE(DDNNIFE_base, TSampler):
    pass


TSampler.register_plugin(DDNNIFE)
