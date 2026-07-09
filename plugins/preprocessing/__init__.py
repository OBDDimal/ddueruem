from .arjun import Arjun
from .cnf2xnf import cnf2xnf
from .pmc import PMC
from .pp_atomic_sets import *
from .pp_unit_variables import *
from .pp_variable_groups import *


def get_plugins_dict():
    return dict(arjun=Arjun, pmc=PMC, cnf2xnf=cnf2xnf)
