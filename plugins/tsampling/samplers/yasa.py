from frameworks import FeatJar

from ..tsampler import TSampler


class YASA(FeatJar, TSampler):
    pass


TSampler.register_plugin(YASA)
