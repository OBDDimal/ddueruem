from abc import ABC, abstractmethod

from formats import CNF

from util.plugins import Extendable


class SVO(ABC, Extendable):

    # -----------------------------------------------------------------------------
    # API

    @abstractmethod
    def run(cls, cnf):
        pass


def compute_spans(clauses, order):

    spans = []

    only = set(order)
    var2index = [0] * (max(only) + 1)

    for i, var in enumerate(order):
        var2index[var] = i

    for clause in clauses:

        if only:
            clause = [abs(x) for x in clause if abs(x) in only]

        if len(clause) < 2:
            spans.append(0)
            continue

        indizes = [var2index[abs(x)] for x in clause]
        lspan = max(indizes) - min(indizes)

        spans.append(lspan)

    return spans


def compute_span(clauses, order):
    return sum(compute_spans(clauses, order))


def compute_avg_pos(clauses, order):

    pos = []

    only = set(order)

    var2index = [0] * (max(only) + 1)

    for i, var in enumerate(order):
        var2index[var] = i

    for clause in clauses:

        if only:
            clause = [abs(x) for x in clause if abs(x) in only]

        indizes = [var2index[abs(x)] for x in clause]
        lspan = sum(indizes)

        pos.append(lspan)

    return pos


def span_order_clauses(clauses, order, sort_clauses=False):
    spans = compute_spans(clauses, order)

    h = sorted(zip(clauses, spans), key=lambda x: x[1])

    if sort_clauses:
        var2index = [0] * (len(order) + 1)
        for i, var in enumerate(order):
            var2index[var] = i

        clauses = [sorted(clause, key=lambda x: -var2index[abs(x)]) for clause, _ in h]

    else:
        clauses = [x for x, _ in h]

    return clauses


def compute_dist(clauses, order):
    return sum(compute_dists(clauses, order))


# FIXME Inefficient
def compute_dists(clauses, order):

    var2index = [0] * (len(order) + 1)

    for i, var in enumerate(order):
        var2index[var] = i

    inner_dists = []

    for clause in clauses:

        dist = 0

        for i, x in enumerate(clause):
            x = abs(x)

            for y in clause[i + 1 :]:
                y = abs(y)
                dist += abs(var2index[x] - var2index[y])

        inner_dists.append(dist)

    return inner_dists


def args_triage(*args):

    if len(args) == 1:
        cnf = args[0]

        if not isinstance(cnf, CNF):
            cnf = CNF(from_file=cnf)

        clauses = cnf.clauses
        nv = cnf.nv
    elif len(args) == 2:
        clauses, nv = args
        cnf = CNF(from_clauses=clauses, nv=nv)
    else:
        raise ValueError(
            f"SVO heuristics accept either CNF, DIMACS file, or clauses and nv, given: {args}"
        )

    return cnf, clauses, nv
