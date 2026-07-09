from copy import copy

from formats import CNF
from pysat.solvers import Solver


def compute_atomic_sets(cnf, yield_core_dead=False, crossover=False):

    cores = set()
    deads = set()
    decided = set()

    atomic_sets = []

    previous_cands = {}

    with Solver(bootstrap_with=cnf.clauses) as solver:

        for x in range(1, cnf.nv + 1):
            if x in decided:
                continue

            aset = set([x])

            if solver.solve(assumptions=[x]):
                config1 = solver.get_model()

                if solver.solve(assumptions=[-x]):
                    config2 = {-y for y in solver.get_model() if y < 0}

                    if x in previous_cands:
                        cands = (
                            previous_cands[x]
                            .intersection(config2)
                            .intersection(config1)
                            .difference(decided)
                        )
                    else:
                        cands = config2.intersection(config1).difference(decided)
                else:
                    cores.add(x)
                    decided.add(x)
                    continue
            else:
                deads.add(x)
                decided.add(x)
                continue

            cands_keep = copy(cands)
            cands = {y for y in cands if y > x}

            while cands:
                y = cands.pop()

                if not solver.solve([x, -y]):
                    if not solver.solve([-x, y]):
                        aset.add(y)
                    else:
                        cands = cands.difference(solver.get_model())
                else:
                    cands = cands.difference(
                        {abs(u) for u in solver.get_model() if u < 0}
                    )

            decided.update({abs(y) for y in aset})

            cands_keep = cands_keep.difference(decided)

            for y in cands_keep:
                if y in previous_cands:
                    previous_cands[y] = cands_keep.intersection(previous_cands[y])
                else:
                    previous_cands[y] = cands_keep

            if len(aset) > 1:
                atomic_sets.append(aset)

        if len(cores) > 1:
            atomic_sets.append(cores)

        if len(deads) > 1:
            atomic_sets.append(deads)

    if yield_core_dead:
        return atomic_sets, cores, deads
    else:
        return atomic_sets


def simplify_atomic_sets(cnf, yield_core_dead=False, crossover=True):

    atomic_sets, cores, deads = compute_atomic_sets(
        cnf, yield_core_dead=True, crossover=crossover
    )

    atomic_sets = sorted(atomic_sets, key=len)

    # mapping of old variable ids to new variable ids
    old2new = dict()

    # running variable id
    current = 1

    core_var = 0
    dead_var = 0

    for aset in atomic_sets:
        for x in aset:
            if x < 0:
                old2new[abs(x)] = -current
            else:
                old2new[abs(x)] = current

        current += 1

    # if len(cores) == 1 it is not considered an atomic set
    if len(cores) == 1:
        for x in cores:
            old2new[abs(x)] = current

        current += 1

    # if len(deads) == 1 it is not considered an atomic set
    if len(deads) == 1:
        for x in deads:
            old2new[abs(x)] = current

        current += 1

    # identify the varid representing all prev. core variables
    if len(cores) > 0:
        core_var = old2new[list(cores)[0]]
        cores = set([core_var])

    # identify the varid representing all prev. dead variables
    if len(deads) > 0:
        dead_var = old2new[list(deads)[0]]
        deads = set([dead_var])

    # map variables outside of atomic sets / c / d to new ids
    for x in range(1, cnf.nv + 1):
        if x in old2new:
            continue

        old2new[x] = current
        current += 1

    cache = set()

    clauses_new = []

    if core_var > 0:
        clauses_new.append([core_var])

    if dead_var > 0:
        clauses_new.append([-dead_var])

    cache.update([hash(str(sorted(clause, key=abs))) for clause in clauses_new])

    for clause in cnf.clauses:

        clause = set([old2new[abs(x)] if x > 0 else -old2new[abs(x)] for x in clause])

        satisfied = False
        nclause = []

        for x in clause:
            if x > 0 and x == core_var:
                satisfied = True
                break
            elif x > 0 and x == dead_var:
                continue
            elif x < 0 and abs(x) == core_var:
                continue
            elif x < 0 and abs(x) == dead_var:
                satisfied = True
                break

            nclause.append(x)

        if len(set(nclause)) > len({abs(x) for x in nclause}):
            satisfied = True

        nclause = sorted(nclause, key=abs)

        if not satisfied and nclause and (hsh := hash(str(nclause))) not in cache:
            clauses_new.append(nclause)
            cache.add(hsh)

    comments = []
    if cnf.var2names:
        new2names = {}

        for k, v in old2new.items():
            if v in new2names:
                new2names[v].append(cnf.var2names[k])
            else:
                new2names[v] = [cnf.var2names[k]]

        for i in range(1, current):
            # FIXME: This potentially creates very long variable names, breaking e.g. BDDSampler, better idea? 
            comments.append(f'c {i} {"_&_".join(new2names[i])}')

    cnf2 = CNF(from_clauses=clauses_new, nv=current - 1, comments=comments)

    if yield_core_dead:
        return cnf2, cores, deads
    else:
        return cnf2
