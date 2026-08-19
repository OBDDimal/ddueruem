from .d4 import D4
from .ddnnife import DDNNIFE
from .dimagic import Dimagic
from .divkc import DivKC
from .featjar import FeatJar


def get_plugins_dict():
    return dict(d4 = D4, featjar=FeatJar, dimagic=Dimagic, divkc=DivKC)
