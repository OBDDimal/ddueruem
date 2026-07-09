import shutil
from ctypes import (
    CDLL,
    POINTER,
    Structure,
    byref,
    c_char_p,
    c_double,
    c_int,
    c_uint,
    c_ulong,
    c_void_p,
)
from os import makedirs, path

import preprocessing
from climplicit import command
from formats import CNF
from svo.heuristics import Force, ForceXG

import config as CONFIG
from util.benchmarking import tic, toc
from util.cli import cli, formatting
from util.plugins import ArchiveDependency, Install, Installable, ToolDependency
from util.runner import via_subprocess

from ..bdd import BDD

SO_LOCATION = path.join(CONFIG.TOOLS_DIR, "cudd", "libcudd.so")

# -----------------------------------------------------------------------------
# CUDD Structs


class DdNode(Structure):
    """C struct for DdNode in CUDD"""


class DdSubtable(Structure):
    """C struct for DdSubtable in CUDD"""


class DdManager(Structure):
    """C struct for DdManager in CUDD"""


def declare(f, argtypes, restype=None):
    """Helper function to declare types for C functions"""

    x = f
    x.argtypes = argtypes

    if restype:
        x.restype = restype

    return x


class CUDD(BDD, Installable):

    @classmethod
    @command(
        desc="CLI tool to build BDDs with CUDD",
        descs={
            "best": 'Apply "ForceXG" strategy from Heß et al. (SPLC\'24)',
            "complement_edges": "Build and export with complement edges",
            "dvo": "Strategy for Dynamic Variable Ordering",
            "no_dvo_control": "Disable active DVO control from SPLC'24",
            "no_xor": "Do not recover XORs",
            "progress": "Show progress bar",
            "soft": "BDD compilation is interrupted at timeout with the partial BDD being stored",
            "intermediate_exports": "Export intermediate BDDs every k clauses (significantly slower!, 0 = disabled)",
            "save_varnames": "Export with variable names (if available)",
        },
        values={"dvo": lambda: CUDD.available_dvo_heuristics()},
        ignores=["file_in", "file_out", "order"],
    )
    def _compile(
        cls,
        file_in,
        file_out=None,
        order=None,
        dvo="win3c",
        best=False,
        soft=False,
        no_dvo_control=False,
        no_xor=False,
        progress=False,
        intermediate_exports=0,
        complement_edges=False,
        save_varnames=False,
    ):

        varnames = None
        time_pre = None
        if best:
            tic()
            cnf = CNF(from_file=file_in)

            if save_varnames:
                varnames = cnf.variables_by_name

            cnf, cores, deads = preprocessing.simplify_yield_unit_clauses(cnf)

            if not no_xor:
                constants = cores.union(deads)

                xor_variables, xor_groups, xor_groups_raw, clauses_rem = (
                    preprocessing.identify_xor_groups(cnf)
                )

            if len(xor_groups_raw) < 20 or no_xor:
                order = Force.run(cnf, order=[])
            else:
                order = ForceXG.run(
                    cnf,
                    constants=constants,
                    xor_variables=xor_variables,
                    xor_groups=xor_groups,
                    clauses_rem=clauses_rem,
                    use_rank=True,
                )
            time_pre = toc()

            tic()
            with CUDD(order=order, dvo=dvo) as mgr:

                if len(xor_groups) < 20 or no_xor:
                    bdd, meta = mgr.compile_cnf(
                        cnf,
                        dvo_control=not no_dvo_control,
                        dco=no_dvo_control,
                        progress=progress,
                        intermediate_exports=intermediate_exports,
                        soft_timeout=soft if soft else 0,
                    )
                else:
                    bdd, meta = mgr.compile_xor_clauses(
                        clauses=clauses_rem,
                        xor_groups=xor_groups_raw,
                        dvo_control=not no_dvo_control,
                        dco=no_dvo_control,
                        progress=progress,
                        intermediate_exports=intermediate_exports,
                        soft_timeout=soft if soft else 0,
                    )

                size = mgr.size(bdd)
                time_kc = toc()

                time_export = None
                if file_out:
                    tic()
                    mgr.export_(
                        bdd,
                        file_out,
                        complement_edges=complement_edges,
                        varnames=varnames,
                    )
                    time_export = toc()
        else:

            if order is None:
                cnf = CNF(from_file=file_in)
                order = cnf.get_order()

            if save_varnames:
                cnf = CNF(from_file=file_in)
                varnames = cnf.variables_by_name

            tic()
            with CUDD(order=order, dvo=dvo) as mgr:
                bdd, meta = mgr.compile_file(
                    file_in,
                    dvo_control=not no_dvo_control,
                    dco=no_dvo_control,
                    progress=progress,
                    intermediate_exports=intermediate_exports,
                    soft_timeout=soft if soft else 0,
                )

                size = mgr.size(bdd)
                time_kc = toc()

                time_export = None
                if file_out:
                    tic()
                    mgr.export_(
                        bdd,
                        file_out,
                        complement_edges=complement_edges,
                        varnames=varnames,
                    )
                    time_export = toc()

        if meta.get("interrupted"):
            cli.warn(
                "BDD compilation was interrupted by soft timeout after",
                formatting.h(f"{soft}s"),
                "and",
                formatting.h(meta.get("clauses")),
                "of",
                formatting.h(meta.get("of_clauses")),
                "clauses",
            )

        if intermediate_exports > 0:
            cli.warn(
                "Due to",
                formatting.h(f"intermediate_export = {intermediate_exports} > 0"),
                "compilation time may be significantly slowed down!",
            )

        return dict(
            size=size, time_pre=time_pre, time_kc=time_kc, time_export=time_export
        )

    @classmethod
    def format_dddmp(cls, _):
        pass

    @classmethod
    def supports_soft_timeout(cls):
        return True

    @classmethod
    def extract_meta(cls, call, file_out):
        """CUDD is not run via via_subprocess, so returncode contains the actual meta data"""

        meta = call.returncode

        return (
            meta.get("time_pre"),
            meta.get("time_kc"),
            meta.get("time_export"),
            meta.get("size"),
        )

    class DVO(BDD.DVO):
        """DVO heuristics available in CUDD"""

        OFF = 1

        RANDOM = 2
        RANDOM_PVT = 3

        SIFT = 4
        SIFTC = 5

        SIFT_SYM = 6
        SIFT_SYMC = 7

        WIN2 = 8
        WIN3 = 9
        WIN4 = 10

        WIN2C = 11
        WIN3C = 12
        WIN4C = 13

        SIFT_GROUP = 14
        SIFT_GROUPC = 15

        ANNEALING = 16
        GENETIC = 17

        LINEAR = 18
        LINEARC = 19

        SIFT_LAZY = 20
        EXACT = 21

        @classmethod
        def default(cls):
            """The default DVO heuristic to use when no heuristic is specified"""
            return cls.WIN3C

    @classmethod
    def available_dvo_heuristics(cls):
        """returns a list of available DVO heuristics"""
        return sorted(iter(CUDD.DVO))

    @classmethod
    def bootstrap(cls):
        """Initialize the class with mappings of internal functions to the respective function in the shared library"""
        cls._cudd = CDLL(SO_LOCATION)

        cls._init = declare(
            cls._cudd.Cudd_Init,
            [c_uint, c_uint, c_uint, c_uint, c_ulong],
            POINTER(DdManager),
        )
        cls._exit = declare(cls._cudd.Cudd_Quit, [POINTER(DdManager)])
        cls._newvar = declare(cls._cudd.Cudd_bddNewVar, [POINTER(DdManager)], c_int)

        # constants / variables
        cls._zero = declare(
            cls._cudd.Cudd_ReadLogicZero, [POINTER(DdManager)], POINTER(DdNode)
        )
        cls._one = declare(
            cls._cudd.Cudd_ReadOne, [POINTER(DdManager)], POINTER(DdNode)
        )
        cls._ithvar = declare(
            cls._cudd.Cudd_bddIthVar, [POINTER(DdManager), c_int], POINTER(DdNode)
        )

        # biop
        cls._and = declare(
            cls._cudd.Cudd_bddAnd,
            [POINTER(DdManager), POINTER(DdNode), POINTER(DdNode)],
            POINTER(DdNode),
        )
        cls._or = declare(
            cls._cudd.Cudd_bddOr,
            [POINTER(DdManager), POINTER(DdNode), POINTER(DdNode)],
            POINTER(DdNode),
        )
        cls._xor = declare(
            cls._cudd.Cudd_bddXor,
            [POINTER(DdManager), POINTER(DdNode), POINTER(DdNode)],
            POINTER(DdNode),
        )

        # setop
        cls._intersect = declare(
            cls._cudd.Cudd_bddIntersect,
            [POINTER(DdManager), POINTER(DdNode), POINTER(DdNode)],
            POINTER(DdNode),
        )

        # triop
        cls._ite = declare(
            cls._cudd.Cudd_bddIte,
            [POINTER(DdManager), POINTER(DdNode), POINTER(DdNode), POINTER(DdNode)],
            POINTER(DdNode),
        )

        # util
        cls._size = declare(cls._cudd.Cudd_DagSize, [POINTER(DdNode)], c_int)
        cls._living = declare(cls._cudd.Cudd_ReadNodeCount, [POINTER(DdManager)], c_int)
        cls._dead = declare(cls._cudd.Cudd_ReadDead, [POINTER(DdManager)], c_int)
        cls._ssat = declare(
            cls._cudd.Cudd_CountMinterm,
            [POINTER(DdManager), POINTER(DdNode), c_int],
            c_double,
        )
        cls._allsat = declare(
            cls._cudd.Cudd_PrintMinterm, [POINTER(DdManager), POINTER(DdNode)]
        )
        cls._addref = declare(cls._cudd.Cudd_Ref, [POINTER(DdNode)])
        cls._delref = declare(
            cls._cudd.Cudd_RecursiveDeref, [POINTER(DdManager), POINTER(DdNode)]
        )

        cls._read_perm = declare(cls._cudd.Cudd_ReadPerm, [POINTER(DdManager), c_int])
        cls._enable_dynorder = declare(
            cls._cudd.Cudd_AutodynEnable, [POINTER(DdManager), c_int]
        )
        cls._disable_dynorder = declare(
            cls._cudd.Cudd_AutodynDisable, [POINTER(DdManager)]
        )
        cls._setorder = declare(
            cls._cudd.Cudd_ShuffleHeap, [POINTER(DdManager), POINTER(c_uint)]
        )
        cls._read_reordering_time = declare(
            cls._cudd.Cudd_ReadReorderingTime, [POINTER(DdManager)]
        )
        cls._reorder = declare(
            cls._cudd.Cudd_ReduceHeap, [POINTER(DdManager), c_int, c_int], c_int
        )

        cls._to_add = declare(
            cls._cudd.Cudd_BddToAdd,
            [POINTER(DdManager), POINTER(DdNode)],
            POINTER(DdNode),
        )
        cls._dump_mult = declare(
            cls._cudd.Dddmp_cuddBddArrayStore,
            [
                POINTER(DdManager),
                c_char_p,
                c_int,
                POINTER(POINTER(DdNode)),
                POINTER(c_char_p),
                POINTER(c_char_p),
                POINTER(c_uint),
                c_int,
                c_uint,
                c_char_p,
                c_void_p,
            ],
        )
        cls._dump_mult_add = declare(
            cls._cudd.Dddmp_cuddAddArrayStore,
            [
                POINTER(DdManager),
                c_char_p,
                c_int,
                POINTER(POINTER(DdNode)),
                POINTER(c_char_p),
                POINTER(c_char_p),
                POINTER(c_uint),
                c_int,
                c_uint,
                c_char_p,
                c_void_p,
            ],
        )

        cls._add_group = declare(
            cls._cudd.Cudd_MakeTreeNode,
            [POINTER(DdManager), c_uint, c_uint, c_uint],
            POINTER(DdNode),
        )

        cls._set_timeout = declare(
            cls._cudd.Cudd_SetTimeLimit, [POINTER(DdManager), c_ulong], None
        )
        cls._unset_timeout = declare(
            cls._cudd.Cudd_UnsetTimeLimit, [POINTER(DdManager)], None
        )

        cls._debug = declare(cls._cudd.Cudd_DebugCheck, [POINTER(DdManager)], c_int)

    def __init__(self, dvo=None, order=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mgr = self._init(0, 0, 256, 1 << 22, 0)

        if dvo is None:
            self.dvo = self.DVO.default()
            self.disable_dvo()
        elif dvo == "off":
            self.disable_dvo()
        else:
            self.dvo = self.DVO.get(dvo)
            self.enable_dvo(self.dvo)

        if order is not None:
            self.set_order(order)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._exit(self.mgr)

    # -----------------------------------------------------------------------------

    def to_index(self, varid):
        return abs(varid) - 1

    # -----------------------------------------------------------------------------
    # Constants and Primitives

    def zero(self):
        out = self._zero(self.mgr)

        return out

    def one(self):
        out = self._one(self.mgr)

        return out

    def ithvar(self, varid):
        out = self._ithvar(self.mgr, varid)
        self.addref_(out)

        return out

    def nithvar(self, varid):
        obj = self._ithvar(self.mgr, varid)

        # this is pointer arithmetic akin to CUDD
        out = byref(obj.contents, 1)
        self.addref_(out)

        return out

    # -----------------------------------------------------------------------------
    # Unary Operations

    def not_(self, obj, free_factors=True):

        return self.ite(obj, self.zero(), self.one(), free_factors)

    # -----------------------------------------------------------------------------
    # Binary Operations

    def and_(self, lhs, rhs, free_factors=True):
        out = self._and(self.mgr, lhs, rhs)

        self.addref_(out)

        if free_factors and bool(out):
            self.delref_(lhs)
            self.delref_(rhs)

        return out

    def or_(self, lhs, rhs, free_factors=True):
        out = self._or(self.mgr, lhs, rhs)

        self.addref_(out)

        if free_factors and bool(out):
            self.delref_(lhs)
            self.delref_(rhs)

        return out

    def xor_(self, lhs, rhs, free_factors=True):
        out = self._xor(self.mgr, lhs, rhs)
        self.addref_(out)

        if free_factors and bool(out):
            self.delref_(lhs)
            self.delref_(rhs)

        return out

    def intersect(self, lhs, rhs, free_factors=True):
        out = self._intersect(self.mgr, lhs, rhs)
        self.addref_(out)

        if free_factors and bool(out):
            self.delref_(lhs)
            self.delref_(rhs)

        return out

    # -----------------------------------------------------------------------------
    # Meta Operations

    def ite(self, a, b, c, free_factors=True):
        out = self._ite(self.mgr, a, b, c)

        self.addref_(out)

        if free_factors and bool(out):
            self.delref_(a)
            self.delref_(b)
            self.delref_(c)

        return out

    # -----------------------------------------------------------------------------
    # CUDD Utilities

    def set_timeout(self, timeout=None):
        if timeout:
            self._set_timeout(self.mgr, timeout)

    def unset_timeout(self):
        self._unset_timeout(self.mgr)

    def set_no_variables(self, no_variables):
        for x in range(0, no_variables):
            if self._read_perm(self.mgr, x) < 0:
                self._newvar(self.mgr)

    def set_groups(self, groups):

        # define MTR_DEFAULT 0x00000000
        # define MTR_TERMINAL    0x00000001
        # define MTR_SOFT    0x00000002
        # define MTR_FIXED   0x00000004
        for group in groups:
            self._add_group(self.mgr, self.to_index(min(group)), len(group), 0)

    def addref_(self, obj):

        if bool(obj):
            self._addref(obj)
        else:
            return None

    def delref_(self, obj):

        if bool(obj):
            self._delref(self.mgr, obj)
        else:
            return None

    # -----------------------------------------------------------------------------
    # Variable Ordering

    def get_order(self):
        i = 0

        order = []

        while True:
            x = self._read_perm(self.mgr, i)
            if x < 0:
                break

            order.append((i, x))
            i += 1

        order = sorted(order, key=lambda x: x[1])

        return [x + 1 for x, _ in order]

    def set_order(self, order):

        self.set_no_variables(len(order))

        order_min = min(order)

        if order_min > 0:
            order = [x - order_min for x in order]

        arr = (c_uint * len(order))(*order)

        self._setorder(self.mgr, arr)

    def enable_dvo(self, dvo):

        self.dvo = self.DVO.get(dvo)

        if self.dvo < self.DVO.OFF:
            self.disable_dvo()
        else:
            self._enable_dynorder(self.mgr, self.dvo)

    def disable_dvo(self):
        self._disable_dynorder(self.mgr)

    def reorder(self, minsize, dvo=None):

        if dvo is None:
            dvo = self.DVO.default()
        else:
            dvo = self.DVO.get(dvo)

        return self._reorder(self.mgr, dvo, int(minsize))

    def dvo_time(self):
        return self._read_reordering_time(self.mgr) / 1000

    # -----------------------------------------------------------------------------
    # Queries

    def size(self, bdd):
        return self._size(bdd)

    def count_alive(self):
        return self._living(self.mgr)

    def count_dead(self):
        return self._dead(self.mgr)

    def has_model(self, bdd):
        pass

    def count_models(self, bdd, variable_support=None):

        if variable_support is None:
            variable_support = len(self.get_order())

        return self._ssat(self.mgr, bdd, variable_support)

    # -----------------------------------------------------------------------------
    # Import / Export

    def import_(self, file):
        pass

    def export_(self, root, *args, **kwargs):
        return self.export_bdds([root], *args, **kwargs)

    def export_bdds(self, roots, filename, varnames=None, complement_edges=False):

        if varnames:
            varnames = [s.encode("utf-8") for s in varnames if s]

            ArrayType = c_char_p * len(varnames)
            varnames = ArrayType(*varnames)

        if complement_edges:
            roots = (POINTER(DdNode) * len(roots))(*roots)
            self._dump_mult(
                self.mgr,
                None,
                len(roots),
                roots,
                None,
                varnames,
                None,
                c_int(65),
                1,
                c_char_p(filename.encode("utf-8")),
                None,
            )
        else:
            roots_add = []
            for root in roots:
                root_add = self._to_add(self.mgr, root)
                self.addref_(root_add)
                roots_add.append(root_add)

            roots = (POINTER(DdNode) * len(roots_add))(*roots_add)
            self._dump_mult_add(
                self.mgr,
                None,
                len(roots),
                roots,
                None,
                varnames,
                None,
                c_int(65),
                1,
                c_char_p(filename.encode("utf-8")),
                None,
            )

    # -----------------------------------------------------------------------------
    # Installation

    @classmethod
    def build(cls):
        src_dir = path.join(CONFIG.CACHE_DIR, "cudd/cudd-3.0.0")
        so_path = path.join(src_dir, "cudd", ".libs", "libcudd.so")
        final_path = path.join(CONFIG.TOOLS_DIR, "cudd", "libcudd.so")

        via_subprocess("./configure --enable-shared --enable-dddmp", cwd=src_dir)
        via_subprocess("make", cwd=src_dir)

        makedirs(path.dirname(final_path), exist_ok=True)
        shutil.copy2(so_path, final_path)

        BDD.register_plugin(CUDD, set_default=True)

        return True

    @classmethod
    def check(cls):
        try:
            cls.bootstrap()
            return True
        except OSError:
            return False

    @classmethod
    def get_installable(cls):
        return Install(
            stub="cudd",
            full="CUDD 3.0.0",
            dependencies=[
                ToolDependency("make"),
                ArchiveDependency(
                    target="cudd",
                    archive="cudd-3.0.0.tar.gz",
                    url="https://github.com/davidkebo/cudd/raw/main/cudd_versions/cudd-3.0.0.tar.gz",
                    md5="4fdafe4924b81648b908881c81fe6c30",
                ),
            ],
            cls=cls,
        )


try:
    CUDD.bootstrap()
    BDD.register_plugin(CUDD, set_default=True)
except OSError:
    pass
