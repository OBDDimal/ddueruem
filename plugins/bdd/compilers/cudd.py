from bdd.apis import CUDD as CUDD_API

from .compiler import BDD_Compiler


class CUDD(CUDD_API, BDD_Compiler):
    """Allows uniform sampling with ddnnife (https://github.com/SoftVarE-Group/d-dnnf-reasoner), with support for:
    * Installing ddnnife
    * Uniform Sampling [USample]
    """

    pass


BDD_Compiler.register_plugin(CUDD)
