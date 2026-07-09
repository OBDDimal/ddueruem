from .ddnnife import DDNNIFE_base
from .dimagic import Dimagic
from .divkc import DivKC
from .featjar import FeatJar


def get_plugins_dict():
    return dict(featjar=FeatJar, dimagic=Dimagic, divkc=DivKC)
