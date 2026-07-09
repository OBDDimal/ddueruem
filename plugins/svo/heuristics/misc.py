import random

from svo import SVO, svo


class Random(SVO):
    @classmethod
    def run(cls, *args, **kwargs):

        _, clauses, nv = svo.args_triage(*args)

        order = list(range(1, nv + 1))
        random.shuffle(order)

        return order


def count_occurrences(clauses, n_variables):

    occs_n = [0] * (n_variables + 1)
    occs_p = [0] * (n_variables + 1)

    for clause in clauses:
        for literal in clause:
            if literal < 0:
                occs_n[abs(literal)] += 1
            else:
                occs_p[literal] += 1

    return occs_n, occs_p


def var_abs(clauses, n_variables, op=max, only=None, **kwargs):
    occs_n, occs_p = count_occurrences(clauses, n_variables)

    data = [(i, op([x, y])) for i, (x, y) in enumerate(zip(occs_n, occs_p)) if i > 0]

    data = sorted(data, key=lambda x: x[1], reverse=True)

    if only:
        order = [var for var, _ in data if var in only]
    else:
        order = [var for var, _ in data]

    return order


class Rank(SVO):

    @classmethod
    def run(cls, *args, **kwargs):

        _, clauses, nv = svo.args_triage(*args)

        return var_abs(clauses, nv, **kwargs)


SVO.register_plugin(Random)
SVO.register_plugin(Rank)
