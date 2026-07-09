import re
from tempfile import NamedTemporaryFile

from pysat.formula import CNF as PySAT_CNF

RE_VAR2NAME = re.compile(r"c\s+(?P<var>\d+)\s+(?P<name>.+[^\s]+)\s*$")


class CNF(PySAT_CNF):

    def __init__(self, nv=None, comments=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # FIXME
        # workaround around implementation of _compute_nv in python-sat
        # https://github.com/pysathq/pysat/blob/e6a6a2bf78aa7ad806f47a84aecd1b7bfd5b3b89/pysat/formula.py#L3039C5-L3039C27

        if not self.clauses:
            raise ValueError("DIMACS contains no clauses.")

        if "from_clauses" in kwargs:
            if nv is not None:
                self.nv = nv

            if comments is not None:
                self.comments = comments

            self.clauses = [sorted(clause, key=abs) for clause in self.clauses]

        if "from_file" in kwargs:
            filename = kwargs["from_file"]

            with open(filename, "r") as fp:
                raw = fp.readlines()

            pline = None

            for line in raw:
                if line.startswith("p"):
                    pline = re.split(r"\s+", line)
                    break

            if pline is None:
                raise ValueError("DIMACS file without p.")
            else:
                nv = int(pline[2])
            # nc = pline[3]     # maybe use for validation of #clauses in the future

            self.nv = nv

        self._var2names = None
        self._names2var = None

    @property
    def var2names(self):

        if self._var2names is None:
            self._var2names = {}

            for comment in self.comments:
                m = RE_VAR2NAME.match(comment)
                if m:
                    self._var2names[int(m["var"])] = m["name"].strip()

        return self._var2names

    @property
    def names2var(self):

        if self._names2var is None:

            self._names2var = {}

            if len(set(self.var2names.values())) < len(self.var2names.values()):
                raise ValueError("Cannot resolve names2var, duplicate names!")

            for k, v in self.var2names.items():
                self._names2var[v] = k

        return self._names2var

    @property
    def variables_by_name(self):

        if len(self.var2names) == 0:
            return [f"Feature-{i}" for i in range(1, self.nv + 1)]

        return list(self.var2names.values())

    def __str__(self):
        return f"ddueruem.formats.CNF NV: {self.nv} | NC: {len(self.clauses)} | CW: {sum([len(cl) for cl in self.clauses]) / len(self.clauses)}"

    def get_order(self):

        order = []

        for comment in self.comments:

            m = re.match(r"c\s+(?P<id>\d+)", comment)

            order.append(int(m["id"]))

        return order

    @classmethod
    def get_order_in_file(cls, file):

        order = []

        with open(file) as fp:
            raw = fp.readlines()

        comments = [line for line in raw if line.startswith("c")]

        for comment in comments:

            m = re.match(r"c\s+(?P<id>\d+)", comment)

            order.append(int(m["id"]))

        return order

    def save_with_order(self, file_out, order, align_clauses=True):
        cnf = CNF(from_clauses=self.clauses)

        if align_clauses:
            # FIXME: Quick & Dirty fix for cyclic dependency
            from svo import svo

            cnf.clauses = svo.span_order_clauses(cnf.clauses, order)

        cnf.nv = self.nv

        comments = []

        for i in order:
            pos = i - 1
            comments.append(self.comments[pos])

        cnf.comments = comments

        cnf.to_file(file_out)

    def rebase(self, dropped, escape_varnames=False):

        var2names = self.var2names

        if not var2names:
            var2names = {x: f"Variable{x}" for x in range(1, self.nv + 1)}

        dropped = set(dropped)

        old2new = {}

        varid = 1
        for x in range(1, self.nv + 1):
            if x in dropped:
                continue

            old2new[x] = varid
            varid += 1

        clauses_new = []
        for clause in self.clauses:
            clause_new = []
            for x in clause:
                if x < 0:
                    clause_new.append(-old2new[abs(x)])
                else:
                    clause_new.append(old2new[abs(x)])

            clauses_new.append(clause_new)

        self.nv = len(old2new)
        self.clauses = clauses_new

        comments_new = []

        new2old = {v: k for k, v in old2new.items()}

        for x in range(1, varid):
            varname = var2names[new2old[x]]

            if escape_varnames:
                varname = re.sub(r"\s+", "_", varname)

            comments_new.append(f"c {x} {varname}")

        self.comments = comments_new

        self._var2names = None
        self._names2var = None

    def sanitize_variable_names(self):
        self.rebase([], escape_varnames=True)

    def aligning_clone(self, xor_groups, xor_groups_raw):
        """Group members of xor groups continuously together"""

        old2new = {}

        xor_groups_new = []

        i = 1
        for group in xor_groups:
            group_new = set()

            for x in group:
                old2new[x] = i
                group_new.add(i)
                i += 1

            xor_groups_new.append(group_new)

        for x in range(1, self.nv + 1):
            if x not in old2new:
                old2new[x] = i
                i += 1

        # apply mapping to clauses
        clauses_new = []

        for clause in self.clauses:
            clause_new = []

            for x in clause:
                clause_new.append((x // abs(x)) * old2new[abs(x)])

            clauses_new.append(sorted(clause_new))

        cnf = CNF(from_clauses=clauses_new)
        cnf.nv = self.nv

        # apply mapping to or_groups_raw
        xor_groups_raw_new = []

        for group in xor_groups_raw:
            group_new = set()

            for x in group:
                group_new.add(old2new[x])

            xor_groups_raw_new.append(group_new)

        return cnf, xor_groups, xor_groups_raw_new, old2new


def ensure_CNF2File(f, name="file_in"):
    def wrapper(*args, **kwargs):
        if isinstance(args[0], type):
            cls_or_self = args[0]

            if len(args) < 2:
                file_or_cnf = kwargs[name]
            else:
                file_or_cnf = args[1]
        else:
            cls_or_self = None

            if len(args) < 1:
                file_or_cnf = kwargs[name]
            else:
                file_or_cnf = args[0]

        if isinstance(file_or_cnf, CNF):
            with NamedTemporaryFile(suffix=".dimacs") as tf:
                file_tmp = tf.name

                file_or_cnf.sanitize_variable_names()
                file_or_cnf.to_file(file_tmp)

                if cls_or_self:
                    return f(cls_or_self, file_tmp, *args[2:], **kwargs)
                else:
                    return f(file_tmp, *args[1:], **kwargs)

        return f(*args, **kwargs)

    return wrapper


def ensure_File2CNF(f):
    def wrapper(*args, **kwargs):
        if isinstance(args[0], type):
            cls_or_self = args[0]
            file_or_cnf = args[1]
        else:
            cls_or_self = None
            file_or_cnf = args[0]

        if not isinstance(file_or_cnf, CNF):
            cnf = CNF(from_file=file_or_cnf)

            if cls_or_self:
                return f(cls_or_self, cnf, *args[2:], **kwargs)
            else:
                return f(cnf, *args[1:], **kwargs)

        return f(*args, **kwargs)

    return wrapper
