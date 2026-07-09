import preprocessing
from formats import CNF
from frameworks import Dimagic

from svo import SVO, svo
from svo.heuristics import Random, Rank


def compute_cog(clause, var2index):

    cog = sum([var2index[abs(x)] for x in clause])

    return cog / len(clause)


class Force(SVO):

    @classmethod
    def run(
        cls,
        *args,
        order=None,
        only=None,
        append_remaining=True,
        weighted_clauses=None,
        weighted_weight=1,
    ):

        _, clauses, nv = svo.args_triage(*args)

        if order is None:
            order = Random.run(clauses, nv)

        cache = set()

        while True:
            cogs_vc = [0] * (nv + 1)
            cogs_vn = [0] * (nv + 1)
            var2index = [0] * (nv + 1)

            for i, var in enumerate(order):
                var2index[var] = i

            for i, clause in enumerate(clauses):

                weight = 1
                if weighted_clauses and clause in weighted_clauses:
                    weight = weighted_weight

                cog = compute_cog(clause, var2index)

                for x in clause:
                    if not only or x in only:
                        cogs_vc[abs(x)] += cog * weight
                        cogs_vn[abs(x)] += weight

            tlocs = []
            order = []
            rem = []
            for i in range(1, nv + 1):

                center = cogs_vc[i]
                n = cogs_vn[i]

                if n > 0:
                    tlocs.append((i, center / n))
                else:
                    rem.append(i)

            tlocs = sorted(tlocs, key=lambda x: x[1])

            order = [x[0] for x in tlocs]
            if rem and append_remaining:
                if only:
                    rem = [x for x in rem if x in only]

                if rem:
                    order = order + rem

            hsh = hash(str(order))
            if hsh in cache:
                break

            cache.add(hsh)

        return order


class ForceXG(SVO):

    @classmethod
    def run(
        cls,
        *args,
        constants=None,
        xor_variables=None,
        xor_groups=None,
        clauses_rem=None,
        use_mince=False,
        use_rank=True,
    ):

        cnf, _, _ = svo.args_triage(*args)

        if constants is None:
            cnf, cores, deads = preprocessing.simplify_yield_unit_clauses(cnf)

            constants = cores.union(deads)

        if xor_variables is None or xor_groups is None or clauses_rem is None:
            xor_variables, xor_groups, _, clauses_rem = (
                preprocessing.identify_xor_groups(cnf)
            )

        var2group = dict()
        group_orders = []

        if use_mince:
            cnf = CNF(from_clauses=clauses_rem)
            order = Dimagic.run(cnf, cmd="-c remince -v remince")

        else:
            order = []
            if use_rank:
                order = Rank.run(clauses_rem, cnf.nv)

            order = Force.run(clauses_rem, cnf.nv, order=order)

        for i, group in enumerate(xor_groups):
            for x in group:
                var2group[abs(x)] = i + 1

            order_g = [x for x in order if x in set(group)]

            group_orders.append(order_g)

        new2old = dict()
        j = 1
        for i in range(1, cnf.nv + 1):
            if i in xor_variables or i in constants:
                continue

            var2group[i] = len(xor_groups) + j
            new2old[len(xor_groups) + j] = i
            j += 1

        pseudo_clauses = []
        for clause in clauses_rem:
            clean = [var2group[abs(x)] for x in clause if abs(x) not in constants]

            if clean:
                pseudo_clauses.append(set(clean))

        if use_mince:
            cnf = CNF(from_clauses=pseudo_clauses)
            cnf.nv = len(set(var2group.values()))

            order = Dimagic.run(cnf, cmd="-c remince -v remince")

        else:
            order = []
            if use_rank:
                order = Rank.run(pseudo_clauses, max(var2group.values()))

            order = Force.run(pseudo_clauses, max(set(var2group.values())), order=order)

        order_full = []

        for u in order:
            if u <= len(xor_groups):
                order_full.append(group_orders[u - 1])
            else:
                order_full.append([new2old[u]])

        order_full.append(sorted(constants))
        order_full = sum(order_full, [])

        return order_full


class DetForce(SVO):
    @classmethod
    def run(cls, *args, order=None, **kwargs):

        if order is None:
            order = []

        return Force.run(*args, order=[], **kwargs)


class ForceBest(SVO):
    @classmethod
    def run(cls, cnf, n, *args, **kwargs):

        order_best = None
        span_best = None

        for i in range(n):
            print(i)
            order = Force.run(cnf, *args, **kwargs)
            span = svo.compute_span(cnf.clauses, order)

            if order_best is None or span < span_best:
                order_best = order
                span_best = span

        return order_best


SVO.register_plugin(Force)
SVO.register_plugin(DetForce)
SVO.register_plugin(ForceXG)
