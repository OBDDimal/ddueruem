from frameworks import DDNNIFE as DDNNIFE_base

from ..usampler import USampler


class DDNNIFE(DDNNIFE_base, USampler):
    """Allows uniform sampling with ddnnife (https://github.com/SoftVarE-Group/d-dnnf-reasoner), with support for:
    * Installing ddnnife
    * Uniform Sampling [USample]
    """

    pass


USampler.register_plugin(DDNNIFE)
