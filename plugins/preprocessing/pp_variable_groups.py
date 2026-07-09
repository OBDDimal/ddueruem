import itertools
from copy import deepcopy


def identify_xor_groups(cnf, min_size=2):
    var2pairs = dict()

    clauses = [sorted(clause, key=abs) for clause in cnf.clauses]

    clauses2 = [clause for clause in clauses if len(clause) == 2]

    for clause in clauses2:
        x, y = sorted(clause, key=abs)

        if x in var2pairs:
            var2pairs[x].add(y)
        else:
            var2pairs[x] = set([y])

    xor = 0
    xor_groups = []
    xor_clauses = set()

    for clause in sorted(clauses, key=len):
        cands = sorted([x for x in clause if x > 0])

        if len(cands) <= min_size:
            continue

        pairs = set()
        for x, y in itertools.combinations(cands, 2):
            if -x in var2pairs:
                if -y in var2pairs[-x]:
                    pairs.add(str([-x, -y]))

        if len(pairs) == len(cands) * (len(cands) - 1) // 2:
            xor += 1
            xor_clauses.update(pairs)
            xor_groups.append(set([abs(x) for x in cands]))

    clauses_rem = []

    for clause in clauses:
        if str(clause) in xor_clauses:
            continue

        clauses_rem.append(clause)

    xor_groups_raw = sorted(deepcopy(xor_groups), key=len, reverse=True)
    xor_groups = sorted(deepcopy(xor_groups), key=len, reverse=True)

    merged = True

    while merged:
        var2xor = dict()
        merged = False

        for i, group in enumerate(xor_groups):
            for x in group:
                if x in var2xor:
                    merged = True
                    ind = var2xor[x]

                    xor_groups[ind].update(group)

                    for y in group:
                        var2xor[y] = ind

                    xor_groups[i] = None
                    break
                else:
                    var2xor[x] = i

        xor_groups = [g for g in xor_groups if g is not None]

    xor_variables = set(var2xor)

    return xor_variables, xor_groups, xor_groups_raw, clauses_rem
