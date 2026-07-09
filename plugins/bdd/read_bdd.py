import re
from os import path


class ReadBDD:

    def __init__(self, nodes=None, nvars=None, order=None, roots=None, from_file=None):

        if any([x is None for x in [nodes, nvars, order, roots]]):
            if from_file is None:
                raise ValueError("from_file required")

            if from_file.endswith(".dddmp"):
                self.from_dddmp(from_file)
            else:
                raise ValueError("unsupported format")
        else:
            self.roots = roots
            self.nodes = nodes
            self.order = order
            self.nvars = nvars

    def from_dddmp(self, filename):

        filename = path.abspath(filename)

        if not path.exists(filename):
            raise FileNotFoundError(f"{filename} does not exist")

        with open(filename) as file:
            raw = file.readlines()

        # Parse Nodes
        nodes = []
        has_complemented_edges = False

        for line in raw:
            if (
                m := re.match(
                    r"(?P<nid>\d+)\s+(?P<aid>[TF\d]+)\s+(?P<varid>[T\d]+)\s+(?P<high>\d+)\s+(?P<low>[-]?\d+)",
                    line,
                )
            ) or (
                m := re.match(
                    r"(?P<nid>\d+)\s+(?P<varid>[TF\d]+)\s+(?P<high>\d+)\s+(?P<low>[-]?\d+)",
                    line,
                )
            ):

                high = int(m["high"])
                low = int(m["low"])

                if not has_complemented_edges and (high < 0 or low < 0):
                    has_complemented_edges = True

                nodes.append((int(m["nid"]), m["varid"], high, low))

            elif m := re.match(r"\.ids\s+(?P<ids>(\d+\s)+\d+)", line):
                ids = m["ids"]
            elif m := re.match(r"\.permids\s+(?P<ids>(\d+\s)+\d+)", line):
                permids = m["ids"]
            elif m := re.match(r"\.rootids\s+((?P<roots>([-]?\d+\s*)+))", line):
                roots = re.split(r"\s", m["roots"])
                roots = [int(x) - 1 for x in roots if x]
            elif m := re.match(r"\.nvars (?P<nvars>\d+)", line):
                nvars = int(m["nvars"])
            elif m := re.match(r"\.bdd", line):
                raise NotImplementedError("Cannot import BDDs with complemented edges")

        ids = [int(x) for x in re.split(r"\s+", ids)]
        permids = [int(x) for x in re.split(r"\s+", permids)]
        order = [0] * (nvars)

        for i in range(len(permids)):
            order[permids[i]] = ids[i] + 1

        order = [x for x in order if x != 0]

        for i, node in enumerate(nodes):
            nid, varid, high, low = node

            if high == 0 and low == 0:
                nodes[i] = (nid - 1, 0, 0, 0)
            else:
                nodes[i] = (nid - 1, order[int(varid)], high - 1, low - 1)

        self.roots = roots
        self.nodes = nodes
        self.nvars = nvars
        self.order = order

    def verify(self, config):

        node_id = self.roots[0]

        while node_id >= 2:

            node_id, node_var, high_id, low_id = self.nodes[node_id]

            if node_var in config:
                node_id = high_id
            else:
                node_id = low_id

        return node_id == 1

    def count_models_dfs(self, roots=None):
        if roots is None:
            roots = self.roots

        nodes = self.nodes

        order = self.order

        counts = [None] * len(self.nodes)
        counts[0] = 0
        counts[1] = 2 ** (self.nvars - len(order))
        self.counts = counts

        stack = [roots[0]]
        while stack:
            node_id = stack.pop()
            node_id, node_var, low_id, high_id = nodes[node_id]

            if counts[low_id] is None or counts[high_id] is None:
                stack.append(node_id)

                if counts[low_id] is None:
                    stack.append(low_id)

                if counts[high_id] is None:
                    stack.append(high_id)

                continue

            high_id, high_var, _, _ = nodes[high_id]
            low_id, low_var, _, _ = nodes[low_id]

            low_count = counts[low_id]
            high_count = counts[high_id]

            if low_var == 0:
                dist_low = len(order) - order.index(node_var) - 1

            else:
                dist_low = (order.index(low_var) - order.index(node_var)) - 1

            if high_var == 0:
                dist_high = len(order) - order.index(node_var) - 1

            else:
                dist_high = (order.index(high_var) - order.index(node_var)) - 1

            if counts[node_id] is None:
                counts[node_id] = 0

            counts[node_id] = high_count * 2**dist_high + low_count * 2**dist_low

        return {root: counts[root] for root in roots}

    def count_models_by_variable_dfs(self, root=None):

        if not root:
            root = self.roots[0]

        nodes = self.nodes

        count = self.count_models()
        aggr = [0] * len(nodes)

        aggr[root] = count
        edge2count = dict()

        comms = [0] * (self.nvars + 1)

        counts = self.counts
        order = self.order
        var2nodes = dict()

        for i in range(0, max(order) + 1):
            var2nodes[i] = []

        for node in nodes:
            _, node_var, _, _ = node

            var2nodes[node_var].append(node)

        for var in order:
            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                high_id, high_var, _, _ = nodes[high_id]
                low_id, low_var, _, _ = nodes[low_id]

                low_count = counts[low_id]
                high_count = counts[high_id]

                if low_var == 0:
                    dist_low = len(order) - order.index(node_var) - 1

                    for i in range(order.index(node_var) + 1, len(order)):
                        comms[order[i]] += (
                            (low_count * 2 ** (dist_low - 1))
                            * aggr[node_id]
                            // counts[node_id]
                        )
                else:
                    dist_low = (order.index(low_var) - order.index(node_var)) - 1

                    for i in range(order.index(node_var) + 1, order.index(low_var)):
                        comms[order[i]] += (
                            (low_count * 2 ** (dist_low - 1))
                            * aggr[node_id]
                            // counts[node_id]
                        )

                if high_var == 0:
                    dist_high = len(order) - order.index(node_var) - 1

                    for i in range(order.index(node_var) + 1, len(order)):
                        comms[order[i]] += (
                            (high_count * 2 ** (dist_high - 1))
                            * aggr[node_id]
                            // counts[node_id]
                        )
                else:
                    dist_high = (order.index(high_var) - order.index(node_var)) - 1

                    for i in range(order.index(node_var) + 1, order.index(high_var)):
                        comms[order[i]] += (
                            (high_count * 2 ** (dist_high - 1))
                            * aggr[node_id]
                            // counts[node_id]
                        )

                edge2count[(node_id, high_id)] = (
                    (high_count * 2**dist_high) * aggr[node_id] // counts[node_id]
                )
                edge2count[(node_id, low_id)] = (
                    (low_count * 2**dist_low) * aggr[node_id] // counts[node_id]
                )

                aggr[high_id] += (
                    (high_count * 2**dist_high) * aggr[node_id] // counts[node_id]
                )
                aggr[low_id] += (
                    (low_count * 2**dist_low) * aggr[node_id] // counts[node_id]
                )

        for var in order:
            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                comms[var] += edge2count[(node_id, high_id)]

        out = dict()
        for var in order:
            out[var] = comms[var]

        return out

    def count_models(self, roots=None):
        if roots is None:
            roots = self.roots

        nodes = self.nodes

        order = self.order

        var2index = [0] * (self.nvars + 1)

        for i, x in enumerate(order):
            var2index[x] = i

        counts = [None] * len(self.nodes)
        counts[0] = 0
        counts[1] = 2 ** (self.nvars - len(order))
        self.counts = counts

        var2nodes = dict()

        for i in range(0, max(order) + 1):
            var2nodes[i] = []

        for node in nodes:
            _, node_var, _, _ = node

            var2nodes[node_var].append(node)

        for var in reversed(order):
            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                high_id, high_var, _, _ = nodes[high_id]
                low_id, low_var, _, _ = nodes[low_id]

                low_count = counts[low_id]
                high_count = counts[high_id]

                if low_var == 0:
                    dist_low = len(order) - var2index[node_var] - 1

                else:
                    dist_low = (var2index[low_var] - var2index[node_var]) - 1

                if high_var == 0:
                    dist_high = len(order) - var2index[node_var] - 1

                else:
                    dist_high = (var2index[high_var] - var2index[node_var]) - 1

                counts[node_id] = high_count * 2**dist_high + low_count * 2**dist_low

        counts = {root: counts[root] for root in roots}

        if len(counts) == 1:
            return list(counts.values())[0]
        else:
            return counts

    def dfs(self, root=None):

        if root is None:
            root = self.roots[0]

        stack = [root]

        seen = set()

        while stack:
            node_id = stack.pop()

            seen.add(node_id)

            node = self.nodes[node_id]
            node_id, node_var, high_id, low_id = node

            if node_var == 0:
                continue

            yield node

            if high_id not in seen:
                seen.add(high_id)
                stack.append(high_id)

            if low_id not in seen:
                seen.add(low_id)
                stack.append(low_id)

    def gen_edges_dfs(self, root=None):

        for node in self.dfs(root):
            node_id, _, high_id, low_id = node

            if high_id > 0:
                yield (node_id, high_id)

            if low_id > 0:
                yield (node_id, low_id)

    def compute_sample_induced_bdd(self, sample, root=None):

        if root is None:
            root = self.roots[0]

        edges_marked = set()

        for config in sample:
            node_id, node_var, high_id, low_id = self.nodes[root]

            while node_var > 0:

                if node_var in config:
                    next_id = high_id
                else:
                    next_id = low_id

                edges_marked.add((node_id, next_id))

                node_id, node_var, high_id, low_id = self.nodes[next_id]

            if node_id == 0:
                print("This should not happen")

        nodes = set()

        for p, c in edges_marked:
            nodes.add(self.nodes[p])
            nodes.add(self.nodes[c])

        # sort nodes by id
        nodes = sorted(nodes, key=lambda x: x[0])

        old2new = {0: 0, 1: 1}

        cur = 2

        for node in nodes:
            node_id, node_var, _, _ = node

            if node_var == 0:
                continue

            old2new[node_id] = cur
            cur += 1

        node_ids = set([x[0] for x in nodes])

        nodes_new = [(0, 0, 0, 0)]
        for node in nodes:

            node_id, node_var, high_id, low_id = node

            if node_var == 0:
                nodes_new.append(node)
                continue

            if high_id not in node_ids:
                high_id = 0

            if low_id not in node_ids:
                low_id = 0

            nodes_new.append(
                (old2new[node_id], node_var, old2new[high_id], old2new[low_id])
            )

        return ReadBDD(
            nodes_new, order=self.order, nvars=self.nvars, roots=[old2new[root]]
        )

    def compute_var2nodes(self, root):

        var2nodes = {}

        for node in self.dfs(root):
            _, node_var, _, _ = node
            var2nodes[node_var] = var2nodes.get(node_var, [])
            var2nodes[node_var].append(node)

        return var2nodes

    def count_2wise(self, root=None, support_from_node=None, support=None):

        if root is None:
            root = self.roots[0]

        nodes = self.nodes
        order = self.order

        var2index = [0] * (self.nvars + 1)

        for i, x in enumerate(order):
            var2index[x] = i

        var2nodes = self.compute_var2nodes(root)

        if support is None:
            support = set(var2nodes.keys())

        node2literals = dict()

        for node_id, _, _, _ in self.nodes:
            node2literals[node_id] = set()

        lit2ints = dict()
        for var in range(1, self.nvars + 1):
            lit2ints[var] = set()
            lit2ints[-var] = set()

        _, root_var, _, _ = self.nodes[root]

        free_variables = set(range(1, self.nvars + 1)).difference(support)

        n_ints2 = 0
        if len(free_variables) > 1:
            n_ints2 = len(free_variables) * (2 * len(free_variables) - 2)

        n_ints2_ncd = n_ints2

        started = False

        for i, var in enumerate(order):

            if not started and var != root_var:
                continue

            if var not in var2nodes or not var2nodes[var]:
                continue

            started = True

            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                literals = node2literals[node_id]

                high_id, high_var, _, _ = nodes[high_id]
                low_id, low_var, _, _ = nodes[low_id]

                if high_id > 0:
                    lit2ints[node_var].update(literals)

                    node2literals[high_id].add(node_var)
                    node2literals[high_id].update(literals)

                    if high_var == 0:
                        iterator = iter(order[i + 1 :])
                    else:
                        iterator = iter(order[i + 1 : var2index[high_var]])

                    for free_var in iterator:
                        if free_var not in support:
                            continue

                        literals2 = node2literals[high_id]

                        lit2ints[free_var].update(literals2)
                        lit2ints[-free_var].update(literals2)

                        node2literals[high_id].update([free_var, -free_var])

                if low_id > 0:
                    lit2ints[-node_var].update(literals)

                    node2literals[low_id].add(-node_var)
                    node2literals[low_id].update(literals)

                    if low_var == 0:
                        iterator = iter(order[i + 1 :])
                    else:
                        iterator = iter(order[i + 1 : var2index[low_var]])

                    for free_var in iterator:
                        if free_var not in support:
                            continue

                        literals2 = node2literals[low_id]

                        lit2ints[free_var].update(literals2)
                        lit2ints[-free_var].update(literals2)

                        node2literals[low_id].update([free_var, -free_var])

                node2literals.pop(node_id)

            t = len({x for x in lit2ints[var] if var2index[abs(x)] < var2index[var]})
            f = len({x for x in lit2ints[-var] if var2index[abs(x)] < var2index[var]})

            if t > 0 or (var == root_var and high_id > 0):
                t += 2 * len(free_variables)

            if f > 0 or (var == root_var and low_id > 0):
                f += 2 * len(free_variables)

            n_ints2 += t + f
            n_ints2_ncd += t + f if t > 0 and f > 0 else 0

            lit2ints.pop(var)
            lit2ints.pop(-var)

        return n_ints2, n_ints2_ncd
