from usampling.samplers import Spur as Spur_US

from ..counter import Counter


class Spur(Spur_US, Counter):
    pass


Counter.register_plugin(Spur, set_default=True)
