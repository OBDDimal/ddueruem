from .uvl2dimacs import UVL2DIMACS


def get_plugins_dict():
    return dict(uvl2dimacs = UVL2DIMACS)
