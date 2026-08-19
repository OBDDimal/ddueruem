from frameworks import DDNNIFE as DDNNIFE_base

from ..counter import Counter


class DDNNIFE(DDNNIFE_base, Counter):
    pass


Counter.register_plugin(DDNNIFE)
