"""meta and template class for BDD wrappers"""

from contextlib import nullcontext
from tempfile import NamedTemporaryFile

from formats import CNF
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from svo import svo

from util.cli import cli, formatting

from .api import BDD_API
from .read_bdd import ReadBDD


class BDD(BDD_API):
    """Meta Class and Template Class to interface with BDD
    libraries wrapped by ddueruem.
    """

    # -------------------------------------------------------------------------------------------- #

    def __init__(self, dvo_limit=1 << 17, dvo_min_factor=1):

        self.dvo_selected = None
        self.dvo = None
        self.initial_dvo_limit = dvo_limit
        self.dvo_min_factor = dvo_min_factor
        self.dvo_limit = None
        self.dvo_limit_min = None

        self.cached_size = 0
        self.sifted_once = False

    def __new__(cls, *args, from_file=None, lib=None, **kwargs):
        """
        Constructor that triages :lib:

        :type lib: None or str or BDD
        """

        # forward, if just called via super().__new__(cls)
        if cls != BDD:
            return super().__new__(cls)

        if from_file:
            return cls.from_file(from_file)

        if lib is None:
            lib = cls.get_default()

            if lib is None:
                raise ValueError("No BDD library specified and no default library set.")

        if isinstance(lib, str):
            lib = cls.get_plugin(lib)

            if lib is None:
                raise ValueError(f"BDD library {lib} not available.")

        if not issubclass(lib, BDD):
            raise TypeError(f"{lib} must inherit from BDD")

        return lib(*args, **kwargs)

    @classmethod
    def from_file(cls, filename):
        """Parse a stored BDD"""
        return ReadBDD(from_file=filename)

    # -----------------------------------------------------------------------------
    # Compile Strategies

    def compile_file(self, file_in, *args, **kwargs):
        cnf = CNF(from_file=file_in)
        return self.compile_clauses(cnf.clauses, *args, **kwargs)

    def compile_cnf(self, cnf, *args, **kwargs):
        """Compiles a BDD from CNF"""
        return self.compile_clauses(cnf.clauses, *args, **kwargs)

    def compile_clauses(
        self,
        clauses,
        dco=False,
        dvo_control=False,
        bdd=None,
        progress=False,
        roots=None,
        intermediate_exports=0,
        intermediate_export_kwargs=None,
        soft_timeout=0,
    ):
        """compiles a BDD from a list of clauses"""

        if soft_timeout > 0:
            self.set_timeout(soft_timeout * 1000)

        if intermediate_export_kwargs is None:
            intermediate_export_kwargs = {}

        with (
            Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                transient=True,
            )
            if progress
            else nullcontext()
        ) as _prog:

            if dco or dvo_control:
                order = self.get_order()
                clauses = self.reorder_clauses(
                    order, clauses, i=None, sort_clauses=True
                )

            if dvo_control:
                self.dvo_selected = self.dvo
                self.dvo = self.DVO.get("off")
                self.disable_dvo()
                self.dvo_limit = self.initial_dvo_limit
                self.dvo_limit_min = self.initial_dvo_limit // self.dvo_min_factor

            dvo_time_last = 0

            n = len(clauses)

            if progress:
                _task = _prog.add_task("Compiling Clauses", total=n)

            interrupted = False
            last_bdd = None
            for i in range(n):
                clause = clauses[i]
                agg = None

                for lit in clause:
                    lit_id = self.to_index(lit)

                    if lit > 0:
                        tmp = self.ithvar(lit_id)
                    else:
                        tmp = self.nithvar(lit_id)

                    if not bool(tmp):
                        interrupted = True
                        break

                    if agg is not None:
                        agg = self.or_(agg, tmp)
                    else:
                        agg = tmp

                    if not bool(agg):
                        interrupted = True
                        break

                if interrupted:
                    break

                if bdd is not None:
                    bdd = self.and_(bdd, agg)
                else:
                    bdd = agg

                if not bool(bdd):
                    interrupted = True
                    break
                else:
                    last_bdd = bdd

                if progress:
                    if not dvo_control:
                        _prog.update(
                            _task,
                            description=f"Compiling Clauses: {f'{i}'.rjust(len(str(n)))} / {n}",
                        )
                    _prog.advance(_task)

                if intermediate_exports > 0 and i % intermediate_exports == 0:

                    file_out = intermediate_export_kwargs.get("file_out_template")
                    file_out = (
                        file_out.format(i)
                        if file_out
                        else NamedTemporaryFile(suffix=f"-{i}.dddmp").name
                    )

                    if progress:
                        _prog.console.print("Exported intermediate BDD:", file_out)

                    self.export_(
                        bdd,
                        file_out,
                        complement_edges=intermediate_export_kwargs.get(
                            "complement_edges", False
                        ),
                        varnames=intermediate_export_kwargs.get("varnames"),
                    )

                if i == n - 1:
                    continue

                if dvo_control:
                    clauses, dvo_control = self.controlled_dvo(
                        bdd,
                        clauses,
                        i,
                        roots,
                        progress=(_prog, _task) if progress else None,
                    )

                    if not dvo_control:
                        dco = True
                        self.disable_dvo()
                elif dco:
                    t = self.dvo_time()
                    if t is not None:
                        if t > dvo_time_last:
                            dvo_time_last = t
                            clauses = self.reorder_clauses(self.get_order(), clauses, i)

            meta = dict(interrupted=interrupted, clauses=i, of_clauses=n)

            if interrupted and last_bdd is not None:
                self.unset_timeout()
                bdd = last_bdd

            if progress:
                cli.say(formatting.check(), "compiled clauses")

            return bdd, meta

    def compile_xor_clauses(
        self,
        clauses,
        xor_groups,
        dco=False,
        dvo_control=False,
        progress=False,
        **kwargs,
    ):
        """compiles a BDD from a list of XOR groups and remaining CNF clauses"""

        bdd = None

        xor_groups = sorted(xor_groups, key=len)
        order = self.get_order()
        var2index = [0] * (len(order) + 1)

        for i, var in enumerate(order):
            var2index[var] = i

        for group_i, group in enumerate(xor_groups):

            group = sorted(group, key=lambda x: -var2index[x])
            sel = None
            unsel = None

            for u in group:
                v = self.to_index(u)
                if sel is None or unsel is None:
                    sel = self.nithvar(v)
                    unsel = self.ithvar(v)
                    continue

                sel_old = sel
                unsel_old = unsel
                sel = self.ite(self.ithvar(v), self.zero(), sel_old, False)
                unsel = self.ite(self.ithvar(v), sel_old, unsel_old)

            agg = self.or_(sel, unsel)

            if bdd is None:
                bdd = agg
            else:
                bdd = self.and_(bdd, agg)

        if progress:
            cli.say(formatting.check(), "compiled XOR groups")

        return self.compile_clauses(
            clauses,
            dco=dco,
            dvo_control=dvo_control,
            bdd=bdd,
            progress=progress,
            **kwargs,
        )

    def controlled_dvo(self, bdd, clauses, i, roots, progress=None):
        """Overrides the DVO trigger mechanic of the library"""

        dvo_control = True
        limit = self.dvo_limit

        old_size = int(self.size(bdd))

        if old_size > limit:

            if progress:
                _prog, _task = progress
                _prog.update(
                    _task,
                    description=f'{f"{i + 1}".rjust(len(str(len(clauses))))} / {len(clauses)} | {old_size} | {limit} | {self.dvo}',
                )

            if self.dvo == self.dvo.OFF:
                self.dvo = self.dvo.get(self.dvo_selected)

            if limit <= 1 << 22:  # 4M
                self.reorder(minsize=limit // 4, dvo=self.dvo)
            elif limit <= 1 << 24:  # 16M
                self.reorder(minsize=limit, dvo=self.dvo)
            else:
                dvo_control = False
                self.enable_dvo(self.dvo_selected)
                return clauses, dvo_control

            new_size = int(self.size(bdd))

            if new_size < limit // 4:
                limit = max(limit // 2, self.dvo_limit_min)
            elif new_size < limit:
                pass
            else:
                limit *= 2

            self.dvo_limit = limit

            new_order = self.get_order()

            if new_size < old_size:
                clauses = self.reorder_clauses(
                    new_order, clauses, i, sort_clauses=False
                )

        elif progress:
            _prog, _task = progress
            _prog.update(
                _task,
                description=f'{f"{i + 1}".rjust(len(str(len(clauses))))} / {len(clauses)} | {old_size} | {limit} | {self.dvo}\n',
            )

        return clauses, dvo_control

    def reorder_clauses(self, order, clauses, i=None, sort_clauses=False):
        """reorders the list of clauses to suit the current variable order"""

        if i is None:
            nclauses = svo.span_order_clauses(clauses, order, sort_clauses)
            i = -1
        else:
            nclauses = svo.span_order_clauses(clauses[i + 1 :], order, sort_clauses)

        for j, _ in enumerate(nclauses):
            clauses[i + 1 + j] = nclauses[j]

        return clauses
