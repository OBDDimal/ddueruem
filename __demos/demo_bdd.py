from bdd import BDD
from bdd.compilers import CUDD, OxiDD

from formats import CNF  # Enhanced PySAT CNF

import preprocessing
from svo.heuristics import DetForce

filepath = "__examples/automotive01.dimacs"


# (needed due to forkserver default in Python 3.14+)
if __name__ == "__main__":

    # Install if not already installed
    CUDD.install()
    OxiDD.install()  # Also installs Dimagic, KaHyPar, Mince, PMC

    # Just compile and export to dddmp using CUDD and our strategy from SPLC'23 (https://dl.acm.org/doi/abs/10.1145/3646548.3672598):
    print("ForceXG + CUDD:")
    result = CUDD.compile(filepath, "automotive01.dimacs-cudd.dddmp", best=True)
    result.render()

    # # Just compile and export to dddmp using OxiDD and Dubslaff et al.'s strategy from JSS'25 (https://www.sciencedirect.com/science/article/pii/S0164121225002353):
    print()
    print("Dimagic + OxiDD:")
    result = OxiDD.compile(filepath, "automotive01.dimacs-oxidd.dddmp", best=True)
    result.render()

    # ---------------------------------------------------------------------------------------------
    # Using the CUDD API
    # ---------------------------------------------------------------------------------------------

    print()
    print("CUDD API:")
    cnf = CNF(from_file=filepath)

    # Propagates core and dead variables
    cnf = preprocessing.simplify_unit_clauses(cnf)

    # Variable ordering using deterministic Force
    order = DetForce.run(cnf)

    with CUDD(order=order, dvo="win3c") as mgr:
        bdd, _ = mgr.compile_cnf(cnf, progress=True, dvo_control=True)

        print("Size:", mgr.size(bdd))
        print("Count (CUDD):", mgr.count_models(bdd), "<- too large as CUDD uses float")

        mgr.export_(bdd, "automotive01.dimacs-manual.dddmp")

    # Load as read-only BDD
    bdd = BDD(from_file="automotive01.dimacs-manual.dddmp")
    print("Count (read):", bdd.count_models())
