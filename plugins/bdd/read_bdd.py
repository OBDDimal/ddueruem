import random
import re
from collections import deque
from os import path

# Precompiled once at import time - re.match(pattern_string, line) re-hits
# re's internal compiled-pattern cache (a dict lookup keyed by the whole
# pattern string) on every single call, which dominates from_dddmp's runtime
# on large files (~761k lines for a 760k-node BDD) even though the pattern
# itself is never actually recompiled after the first call.
_NODE_RE_5 = re.compile(
    r"(?P<nid>\d+)\s+(?P<aid>[TF\d]+)\s+(?P<varid>[T\d]+)\s+(?P<high>\d+)\s+(?P<low>[-]?\d+)"
)
_NODE_RE_4 = re.compile(r"(?P<nid>\d+)\s+(?P<varid>[TF\d]+)\s+(?P<high>\d+)\s+(?P<low>[-]?\d+)")
_IDS_RE = re.compile(r"\.ids\s+(?P<ids>(\d+\s)+\d+)")
_PERMIDS_RE = re.compile(r"\.permids\s+(?P<ids>(\d+\s)+\d+)")
_ROOTIDS_RE = re.compile(r"\.rootids\s+((?P<roots>([-]?\d+\s*)+))")
_NVARS_RE = re.compile(r"\.nvars (?P<nvars>\d+)")


class ReadBDD:

    def __init__(self, nodes=None, nvars=None, order=None, roots=None, from_file=None):
        """Build a ReadBDD either from explicit nodes/order/roots, or by parsing from_file."""

        if any(x is None for x in (nodes, nvars, order, roots)):
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

        self._var2index = None
        self._var2nodes = None

    @property
    def var2index(self):
        """Position of each variable id within self.order, cached since order is immutable."""
        if self._var2index is None:
            var2index = [0] * (self.nvars + 1)

            for i, x in enumerate(self.order):
                var2index[x] = i

            self._var2index = var2index

        return self._var2index

    def from_dddmp(self, filename):
        """Parse a CUDD/OxiDD .dddmp file into self.nodes/self.order/self.roots/self.nvars."""

        filename = path.abspath(filename)

        if not path.exists(filename):
            raise FileNotFoundError(f"{filename} does not exist")

        with open(filename) as file:
            raw = file.readlines()

        # Parse Nodes
        nodes = []
        has_complemented_edges = False

        for line in raw:
            if (m := _NODE_RE_5.match(line)) or (m := _NODE_RE_4.match(line)):

                high = int(m["high"])
                low = int(m["low"])

                # dddmp only ever allows the low ("else") edge to carry a complement
                # bit (encoded as a negative id); high is always non-negative.
                if not has_complemented_edges and (high < 0 or low < 0):
                    has_complemented_edges = True

                nodes.append((int(m["nid"]), m["varid"], high, low))

            elif m := _IDS_RE.match(line):
                ids = m["ids"]
            elif m := _PERMIDS_RE.match(line):
                permids = m["ids"]
            elif m := _ROOTIDS_RE.match(line):
                roots = re.split(r"\s", m["roots"])
                # Keep root ids raw (1-based, signed) here; the `- 1` alignment shift
                # is only safe once we know whether we're on the complemented path
                # (see below), since it would otherwise corrupt the sign too.
                roots = [int(x) for x in roots if x]

                if any(root < 0 for root in roots):
                    has_complemented_edges = True

            elif m := _NVARS_RE.match(line):
                nvars = int(m["nvars"])

        ids = [int(x) for x in re.split(r"\s+", ids)]
        permids = [int(x) for x in re.split(r"\s+", permids)]
        order = [0] * (nvars)

        # order[dddmp varid] -> variable id (+1, since 0 is reserved below to mark
        # terminal nodes in the parsed node tuples).
        for i in range(len(permids)):
            order[permids[i]] = ids[i] + 1

        # Drop unset slots; relies on permids/ids covering every index 0..nvars-1
        # (true whenever nvars == nsuppvars, as in all files handled here).
        order = [x for x in order if x != 0]

        self.nvars = nvars
        self.order = order

        if has_complemented_edges:
            self.roots = roots
            self.nodes = nodes
            self._uncomplement()
        else:
            for i, node in enumerate(nodes):
                nid, varid, high, low = node

                # high == low == 0 marks a terminal row; dddmp always lists the
                # False terminal before the True terminal, so nid - 1 lands on the
                # canonical ids 0 (False) / 1 (True) used everywhere in this class.
                if high == 0 and low == 0:
                    nodes[i] = (nid - 1, 0, 0, 0)
                else:
                    nodes[i] = (nid - 1, order[int(varid)], high - 1, low - 1)

            self.roots = [root - 1 for root in roots]
            self.nodes = nodes

    def _uncomplement(self):
        """Eliminate complement edges via BFS, producing a canonical two-terminal BDD.

        self.nodes/self.roots must still hold raw, unshifted dddmp ids (1-based,
        with the low edge's sign as its complement bit) at this point; see
        from_dddmp. Every (raw dddmp id, complement context) pair we ever reach is
        materialized as its own physical node in the output, since the same raw
        node can represent two different functions depending on whether it was
        reached through a complemented edge.
        """
        raw_nodes = {}

        for nid, varid, high, low in self.nodes:
            if high == 0 and low == 0:
                # Terminal row: dddmp encodes which boolean constant it is (0/1)
                # directly in the varid column, since there may be only one
                # physical terminal node shared by both constants.
                raw_nodes[nid] = (True, int(varid))
            else:
                raw_nodes[nid] = (False, self.order[int(varid)], high, low)

        # Canonical convention used throughout this class: id 0 = False, id 1 = True.
        new_nodes = [(0, 0, 0, 0), (1, 0, 0, 0)]
        memo = {}
        queue = deque()

        def resolve(raw_id, complemented):
            """Return the output node id representing raw_id, negated iff complemented."""
            key = (raw_id, complemented)

            if key in memo:
                return memo[key]

            is_terminal = raw_nodes[raw_id][0]

            if is_terminal:
                value = raw_nodes[raw_id][1]
                # Negating a constant just flips it between the two terminal ids.
                new_id = (1 - value) if complemented else value
                memo[key] = new_id
                return new_id

            # Allocate the id before recursing/queueing so children can reference
            # their (not-yet-populated) parent; filled in once popped from queue.
            new_id = len(new_nodes)
            new_nodes.append(None)
            memo[key] = new_id
            queue.append((new_id, raw_id, complemented))
            return new_id

        # A negative root id means the whole function is the complement of the
        # node it points to.
        new_roots = [resolve(abs(root), root < 0) for root in self.roots]

        while queue:
            new_id, raw_id, complemented = queue.popleft()
            _, var, high, low = raw_nodes[raw_id]

            # The "then"/high edge is never itself complemented in dddmp's
            # encoding, so it simply inherits the parent's complement context.
            high_id = resolve(high, complemented)
            # The "else"/low edge's effective complement bit is its own stored
            # sign XORed with the parent's complement context.
            low_id = resolve(abs(low), (low < 0) != complemented)

            new_nodes[new_id] = (new_id, var, high_id, low_id)

        self.nodes = new_nodes
        self.roots = new_roots

    def _dist(self, node_var, other_var):
        """Number of variable levels skipped between node_var and other_var in self.order.

        Reduced BDDs omit nodes for variables that don't affect the function, so
        an edge can jump straight past several levels; each skipped level
        contributes a free factor of 2 to model counts (see count_models).
        other_var == 0 means the edge goes straight to a terminal, i.e. every
        remaining variable after node_var is skipped.
        """
        if other_var == 0:
            return len(self.order) - self.var2index[node_var] - 1

        return self.var2index[other_var] - self.var2index[node_var] - 1

    def verify(self, config, root = None):
        """Check whether config (a set of true variable ids) is a model of the BDD."""

        node_id = root if root is not None else self.roots[0]

        while node_id >= 2:  # ids 0/1 are the False/True terminals

            node_id, node_var, high_id, low_id = self.nodes[node_id]

            if node_var in config:
                node_id = high_id
            else:
                node_id = low_id

        return node_id == 1

    # -- Model counting -----------------------------------------------

    def count_models_dfs(self, roots=None):
        """Count models per root (DFS/worklist variant); scalar if a single root, else a dict."""
        if roots is None:
            roots = self.roots

        nodes = self.nodes

        order = self.order

        counts = [None] * len(self.nodes)
        counts[0] = 0
        # Variables never appearing on the True-terminal path are still free to
        # take either value, each contributing a factor of 2.
        counts[1] = 2 ** (self.nvars - len(order))
        self.counts = counts

        stack = list(roots)
        while stack:
            node_id = stack.pop()
            node_id, node_var, high_id, low_id = nodes[node_id]

            # Post-order via re-push: if a child's count isn't ready yet, requeue
            # this node behind its children and revisit once they're computed.
            if counts[high_id] is None or counts[low_id] is None:
                stack.append(node_id)

                if counts[high_id] is None:
                    stack.append(high_id)

                if counts[low_id] is None:
                    stack.append(low_id)

                continue

            high_id, high_var, _, _ = nodes[high_id]
            low_id, low_var, _, _ = nodes[low_id]

            low_count = counts[low_id]
            high_count = counts[high_id]

            dist_low = self._dist(node_var, low_var)
            dist_high = self._dist(node_var, high_var)

            # Scale each branch's count by 2^(skipped levels) before combining.
            # Shifted rather than `* 2**dist`: for a non-negative int exponent
            # they're exactly equal, but `<<` skips general exponentiation
            # and the separate multiply - measured ~2x faster here since
            # counts can run to hundreds of digits.
            counts[node_id] = (high_count << dist_high) + (low_count << dist_low)

        counts = {root: counts[root] for root in roots}

        if len(counts) == 1:
            return list(counts.values())[0]
        else:
            return counts

    def compute_cardinalities(self, root=None):
        """Number of models of the BDD rooted at root that each variable appears in.

        Propagates aggr (models reaching each node from root) top-down and, for
        each edge, distributes its share of models across every variable skipped
        between the edge's endpoints (see _dist), accumulating into comms.
        """

        if root is None:
            root = self.roots[0]

        nodes = self.nodes

        if getattr(self, "counts", None) is None:
            self.count_models()
        count = self.counts[root]
        aggr = [0] * len(nodes)

        aggr[root] = count
        # Indexed directly by node_id (each node has exactly one high edge,
        # so no need for the full (node_id, high_id) tuple key) - avoids
        # hashing a 2-tuple per node, on top of the dict overhead itself.
        edge_high = [0] * len(nodes)

        comms = [0] * (self.nvars + 1)
        # Range-update array over positions in `order`: rather than adding a
        # skipped edge's contribution to every position it spans one at a
        # time (O(edges * skip width) bignum additions, dominant cost on
        # wide-skip BDDs), record just the start/end of each span and fold
        # them into comms with a single prefix sum afterwards.
        delta = [0] * (len(self.order) + 1)

        counts = self.counts
        order = self.order
        var2index = self.var2index
        var2nodes = self.compute_var2nodes()

        for var in order:
            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                high_id, high_var, _, _ = nodes[high_id]
                low_id, low_var, _, _ = nodes[low_id]

                low_count = counts[low_id]
                high_count = counts[high_id]

                dist_low = self._dist(node_var, low_var)
                low_end = len(order) if low_var == 0 else var2index[low_var]

                dist_high = self._dist(node_var, high_var)
                high_end = len(order) if high_var == 0 else var2index[high_var]

                # Models reaching node_id, split proportionally across its two
                # outgoing edges (aggr[node_id] / counts[node_id] is that ratio).
                # Computed once per edge and reused below, rather than
                # recomputed from scratch for every skipped variable and again
                # for the edge/aggr bookkeeping - these are all full bignum
                # multiplications, and counts/aggr can run to hundreds of
                # digits, so recomputing them repeatedly is expensive.
                high_share = (high_count << dist_high) * aggr[node_id] // counts[node_id]
                low_share = (low_count << dist_low) * aggr[node_id] // counts[node_id]

                # Each variable strictly between node_var and low_var/high_var
                # is skipped by that edge (don't-care), so it gets an equal
                # share (halved per extra level) of the models flowing
                # through that branch.
                start = var2index[node_var] + 1

                if dist_low > 0:
                    low_contribution = (
                        (low_count << (dist_low - 1))
                        * aggr[node_id]
                        // counts[node_id]
                    )
                    delta[start] += low_contribution
                    delta[low_end] -= low_contribution

                if dist_high > 0:
                    high_contribution = (
                        (high_count << (dist_high - 1))
                        * aggr[node_id]
                        // counts[node_id]
                    )
                    delta[start] += high_contribution
                    delta[high_end] -= high_contribution

                # The low-edge share is intentionally not stored: nothing
                # ever reads it back out.
                edge_high[node_id] = high_share

                aggr[high_id] += high_share
                aggr[low_id] += low_share

        running = 0
        for i, var in enumerate(order):
            running += delta[i]
            comms[var] += running

        for var in order:
            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                # A model "depends on" var if it takes the high branch at a node
                # for var (the low/don't-care share was already added above).
                comms[var] += edge_high[node_id]

        out = dict()
        for var in order:
            out[var] = comms[var]

        return out

    def count_models(self, roots=None):
        """Count models per root (level-order variant); scalar if a single root, else a dict."""
        if roots is None:
            roots = self.roots

        nodes = self.nodes

        order = self.order

        counts = [None] * len(self.nodes)
        counts[0] = 0
        counts[1] = 2 ** (self.nvars - len(order))
        self.counts = counts

        var2nodes = self.compute_var2nodes()

        # Process variables leaf-to-root: every child of a node at position i in
        # order has already been computed by the time we reach it.
        for var in reversed(order):
            for node in var2nodes[var]:
                node_id, node_var, high_id, low_id = node

                high_id, high_var, _, _ = nodes[high_id]
                low_id, low_var, _, _ = nodes[low_id]

                low_count = counts[low_id]
                high_count = counts[high_id]

                dist_low = self._dist(node_var, low_var)
                dist_high = self._dist(node_var, high_var)

                counts[node_id] = (high_count << dist_high) + (low_count << dist_low)

        counts = {root: counts[root] for root in roots}

        if len(counts) == 1:
            return list(counts.values())[0]
        else:
            return counts

    # -- Sampling -----------------------------------------------------

    def dfs(self, root=None):
        """Yield each non-terminal node reachable from root exactly once (DFS order)."""

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
        """Yield (parent_id, child_id) for every edge reachable from root, DFS order."""

        for node in self.dfs(root):
            node_id, _, high_id, low_id = node

            if high_id > 0:
                yield (node_id, high_id)

            if low_id > 0:
                yield (node_id, low_id)

    def sample_uniform(self, n=1024, root=None):
        """Draw n models of the BDD rooted at root, uniformly at random.

        Performs n independent weighted random walks from root to a terminal:
        at each node, the high/low branch is chosen with probability
        proportional to the (2^dist-scaled) model count it leads to, so every
        model is equally likely overall. Any variable never encountered as a
        decision node along the walk doesn't affect satisfiability here -
        whether it's skipped between two visited nodes, absent from self.order
        entirely, or (for a non-top root) simply precedes root's variable in
        the order - so each such variable is assigned independently by a fair
        coin flip in a single pass over every variable, rather than trying to
        enumerate the skipped ranges during the walk. Returns a list of n
        configs (sets of variables assigned True), directly usable as `sample`
        for compute_sample_induced_bdd.
        """

        if root is None:
            root = self.roots[0]

        if root == 0:
            raise ValueError("root has no models")

        if getattr(self, "counts", None) is None:
            self.count_models()

        counts = self.counts

        def sample_one():
            config = set()
            decided = set()
            _, node_var, high_id, low_id = self.nodes[root]

            while node_var > 0:
                decided.add(node_var)

                _, high_var, _, _ = self.nodes[high_id]
                _, low_var, _, _ = self.nodes[low_id]

                weight_high = counts[high_id] << self._dist(node_var, high_var)
                weight_low = counts[low_id] << self._dist(node_var, low_var)

                if random.random() * (weight_high + weight_low) < weight_high:
                    config.add(node_var)
                    next_id = high_id
                else:
                    next_id = low_id

                _, node_var, high_id, low_id = self.nodes[next_id]

            for var in range(1, self.nvars + 1):
                if var not in decided and random.random() < 0.5:
                    config.add(var)

            return config

        return [sample_one() for _ in range(n)]

    def compute_sample_induced_bdd(self, sample, root=None):
        """Build the sub-BDD induced by the paths that sample's configs take through root.

        Each config in sample must be a model of the BDD; edges never touched by
        any config are dropped, and any child left dangling by that pruning is
        redirected to the False terminal.
        """

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
                raise ValueError(f"sample config {config} is not a model of the BDD")

        nodes = set()

        for p, c in edges_marked:
            nodes.add(self.nodes[p])
            nodes.add(self.nodes[c])

        # sort nodes by id
        nodes = sorted(nodes, key=lambda x: x[0])

        # Terminals keep their canonical ids; internal nodes are renumbered
        # densely from 2 upward in id order.
        old2new = {0: 0, 1: 1}

        cur = 2

        for node in nodes:
            node_id, node_var, _, _ = node

            if node_var == 0:
                continue

            old2new[node_id] = cur
            cur += 1

        node_ids = {x[0] for x in nodes}

        nodes_new = [(0, 0, 0, 0)]
        for node in nodes:

            node_id, node_var, high_id, low_id = node

            if node_var == 0:
                nodes_new.append(node)
                continue

            # A child left out of the induced subgraph (never visited by any
            # sample config) becomes a dead branch to the False terminal.
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

    def compute_var2nodes(self, root=None):
        """Group nodes by variable id: all nodes if root is None, else only those reachable from root.

        The root=None case (every node, not just those reachable from a
        particular root) is cached, since count_models() and
        compute_cardinalities() each call it independently and would
        otherwise redundantly rebuild the same grouping from scratch.
        """
        if root is None:
            if self._var2nodes is not None:
                return self._var2nodes

            var2nodes = {i: [] for i in range(0, max(self.order) + 1)}

            for node in self.nodes:
                _, node_var, _, _ = node
                var2nodes[node_var].append(node)

            self._var2nodes = var2nodes
            return var2nodes

        var2nodes = {}

        for node in self.dfs(root):
            _, node_var, _, _ = node
            var2nodes[node_var] = var2nodes.get(node_var, [])
            var2nodes[node_var].append(node)

        return var2nodes

    def count_2wise(self, root=None, support=None):
        """Count 2-wise (pairwise) variable-literal interactions realized by some model.

        support restricts which variables are considered (default: every
        variable reachable from root); variables outside support are "free"
        (unconstrained) and contribute a fixed baseline of pairwise interactions
        among themselves, computed once up front rather than via traversal.
        Returns (n_ints2, n_ints2_ncd): the second value restricts the count to
        variables that are neither core nor dead, i.e. both polarities (t > 0
        and f > 0) are actually reachable.
        """

        if root is None:
            root = self.roots[0]

        nodes = self.nodes
        order = self.order

        var2index = self.var2index

        var2nodes = self.compute_var2nodes(root)

        if support is None:
            support = set(var2nodes.keys())

        # node2literals[n] accumulates, for every path from root to n seen so
        # far, the literals fixed along that path.
        node2literals = dict()

        for node_id, _, _, _ in self.nodes:
            node2literals[node_id] = set()

        # lit2ints[lit] collects every literal that has co-occurred with lit on
        # some root-to-node path.
        lit2ints = dict()
        for var in range(1, self.nvars + 1):
            lit2ints[var] = set()
            lit2ints[-var] = set()

        _, root_var, _, _ = self.nodes[root]

        free_variables = set(range(1, self.nvars + 1)).difference(support)

        # Baseline: every pair of literals from two distinct free variables is
        # trivially co-satisfiable (they're unconstrained), so count them
        # up front instead of via traversal. 2 literals/var, minus the var's own
        # 2 literals when pairing against itself: len(free) * (2*len(free) - 2).
        n_ints2 = 0
        if len(free_variables) > 1:
            n_ints2 = len(free_variables) * (2 * len(free_variables) - 2)

        n_ints2_ncd = n_ints2

        started = False

        for i, var in enumerate(order):

            # Skip variable levels above the root; they can't appear on any
            # root-to-terminal path.
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

                    # Variables skipped by this edge (between node_var and
                    # high_var, exclusive) are don't-cares here: either literal
                    # co-occurs with everything already fixed on this path.
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

                node2literals.pop(node_id)  # fully processed, free the memory

            # t/f: how many earlier-order literals co-occur with var/-var; only
            # count literals from variables that precede var in the order, so
            # each interaction is counted once (from the earlier variable's side).
            t = len({x for x in lit2ints[var] if var2index[abs(x)] < var2index[var]})
            f = len({x for x in lit2ints[-var] if var2index[abs(x)] < var2index[var]})

            # Every free variable pairs with both polarities of var/-var too.
            if t > 0 or (var == root_var and high_id > 0):
                t += 2 * len(free_variables)

            if f > 0 or (var == root_var and low_id > 0):
                f += 2 * len(free_variables)

            n_ints2 += t + f
            n_ints2_ncd += t + f if t > 0 and f > 0 else 0

            lit2ints.pop(var)
            lit2ints.pop(-var)

        return n_ints2, n_ints2_ncd
