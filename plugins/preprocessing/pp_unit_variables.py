from formats import CNF, ensure_File2CNF
from pysat.solvers import Solver


def compute_core_deads(cnf):

    found = set()

    cores = set()
    deads = set()

    with Solver(bootstrap_with=cnf.clauses) as solver:
        for x in range(1, cnf.nv + 1):

            x_found = x in found
            nx_found = -x in found

            if x_found and nx_found:
                continue

            if not x_found:
                if solver.solve(assumptions=[x]):
                    found.update(solver.get_model())
                else:
                    solver.add_clause([-x])
                    deads.add(x)

            if not nx_found:
                if solver.solve(assumptions=[-x]):
                    found.update(solver.get_model())
                else:
                    solver.add_clause([x])
                    cores.add(x)

    return cores, deads


def compute_core_deads2(cnf):

    poss = set()
    negs = set()

    cores = set()
    deads = set()

    with Solver(bootstrap_with=cnf.clauses) as solver:
        solver.solve()

        config = solver.get_model()

        poss = {x for x in config if x > 0}
        negs = {abs(x) for x in config if x < 0}

        while poss:
            x = poss.pop()

            if solver.solve(assumptions=[-x]):
                config = solver.get_model()
                poss = poss.difference({abs(x) for x in config if x < 0})
                negs = negs.difference(config)
            else:
                cores.add(x)

        while negs:
            x = negs.pop()

            if solver.solve(assumptions=[x]):
                config = solver.get_model()
                negs = negs.difference(config)
            else:
                deads.add(x)

    return cores, deads


@ensure_File2CNF
def simplify_unit_clauses(cnf):
    cnf, _, _ = simplify_yield_unit_clauses(cnf)

    return cnf


@ensure_File2CNF
def simplify_yield_unit_clauses(cnf):

    truths, falses = compute_core_deads(cnf)

    if truths is None and falses is None:
        return

    truths = truths if truths else set()
    falses = falses if falses else set()

    clauses = []

    for x in truths:
        clauses.append([x])

    for x in falses:
        clauses.append([-x])

    cache = set()

    clauses_good = []
    for clause in clauses:
        if (s := str(clause)) not in cache:
            clauses_good.append(clause)
            cache.add(s)

    clauses = clauses_good

    for clause in cnf.clauses:

        satisfied = False
        nclause = []

        for x in clause:
            if x > 0 and x in truths:
                # x and (x or ...)
                satisfied = True
                break
            elif x > 0 and x in falses:
                continue
            elif x < 0 and abs(x) in truths:
                continue
            elif x < 0 and abs(x) in falses:
                satisfied = True
                break

            nclause.append(x)

        if len(set(nclause)) > len({abs(x) for x in nclause}):
            satisfied = True

        nclause = sorted(nclause, key=abs)

        if not satisfied and nclause:
            if (s := str(nclause)) not in cache:
                clauses.append(nclause)
                cache.add(s)

    cnf2 = CNF(from_clauses=clauses, nv=cnf.nv, comments=cnf.comments)

    return cnf2, truths, falses
