import re
import shutil
import subprocess
import tempfile
from os import makedirs, path

from climplicit import command
from formats import CNF

import config as CONFIG
from util.plugins import (
    Executable,
    GitDependency,
    Install,
    Installable,
    LibraryDependency,
    ToolDependency,
)
from util.runner import via_subprocess

from .compiler import BDD_Compiler

dvo2name = {
    "off": "CUDD_REORDER_SAME",
    "random": "CUDD_REORDER_RANDOM",
    "random_pvt": "CUDD_REORDER_RANDOM_PIVOT",
    "sift": "CUDD_REORDER_SIFT",
    "siftc": "CUDD_REORDER_SIFT_CONVERGE",
    "sift_sym": "CUDD_REORDER_SYMM_SIFT",
    "sift_symc": "CUDD_REORDER_SYMM_SIFT_CONV",
    "sift_group": "CUDD_REORDER_GROUP_SIFT",
    "sift_groupc": "CUDD_REORDER_GROUP_SIFT_CONV",
    "win2c": "CUDD_REORDER_WINDOW2_CONV",
    "win3c": "CUDD_REORDER_WINDOW3_CONV",
    "win4c": "CUDD_REORDER_WINDOW4_CONV",
    "annealing": "CUDD_REORDER_ANNEALING",
    "genetic": "CUDD_REORDER_GENETIC",
    "exact": "CUDD_REORDER_EXACT",
}


class Logic2BDD(BDD_Compiler, Installable, Executable):

    @classmethod
    @command(
        desc="CLI tool to build BDDs with Logic2BDD",
        values={"dvo": lambda: list(dvo2name.keys())},
        ignores=["file_in", "file_out", "order"],
    )
    def _compile(cls, file_in, file_out = None, order = None, use_xor = False, dvo = "win3c", complement_edges = False, **kwargs):

        if dvo != "off":
            dvo = f"-reorder-method {dvo2name.get(dvo.lower())}"
        else:
            dvo = "-noreorder"

        splot2model = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "splot2model")
        logic2bdd = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "Logic2BDD")
        lib = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "libcudd-3.0.0.so.0")

        filepath = path.abspath(file_in)
        fileprefix = path.splitext(path.basename(filepath))[0]

        file_sxfm = f"{fileprefix}.xml"

        cnf = CNF(from_file = file_in)

        with tempfile.TemporaryDirectory(delete = False) as workpath:

            filepath = path.join(workpath, file_sxfm)
            cnf.to_sxfm(filepath)

            call_splot2model = via_subprocess(f'{splot2model} {"-use-XOR" if use_xor else ""} {filepath}')

            varfile = path.join(workpath, f'{fileprefix}.var')
            expfile = path.join(workpath, f'{fileprefix}.exp')

            if order:
                var2names = cnf.var2names
                with open(varfile, "w+") as fp:
                    fp.write(" ".join([var2names[var] for var in order]))
 
            # from
            # https://github.com/davidfa71/Extending-Logic/blob/master/runSPLOT.sh
            
            call = via_subprocess(f'{logic2bdd} -line-length 70 -min-nodes 100000 -constraint-reorder minspan -base {filepath} -cudd {dvo} -no-static-comp {varfile} {expfile}', env=dict(LD_LIBRARY_PATH=path.dirname(lib)))
            call.add_time("time_pre", call_splot2model.get_time_total())

            file_tmp = path.join(workpath, f'{fileprefix}.xml.dddmp')

            with open(file_tmp) as fp:
                raw = fp.read()
                m = re.search(r"[.]nnodes\s+(?P<size>\d+)", raw)

                if m:
                    call.meta["size"] = int(m["size"])

            if file_out:
                shutil.copy2(path.join(workpath, f'{fileprefix}.xml.dddmp'), file_out)


        return call

    @classmethod
    def format_dddmp(*args, **kwargs):
        pass

    @classmethod
    def extract_meta(cls, call, file_out):
        time_pre = call.times.get("time_pre")
        time_kc = call.times.get("time")

        return time_pre, time_kc, None, call.meta.get("size")

    @classmethod
    def plain(cls, args):
        logic2bdd = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "Logic2BDD")
        lib = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "libcudd-3.0.0.so.0")

        via_subprocess(f'{logic2bdd} {args}', env=dict(LD_LIBRARY_PATH=path.dirname(lib)), rc = None, debug = True)

    # -----------------------------------------------------------------------------
    # Installation

    @classmethod
    def build(cls):
        FINAL_PATH = path.join(CONFIG.TOOLS_DIR, "logic2bdd")
        SRC_DIR = path.join(CONFIG.CACHE_DIR, "logic2bdd", "code")
        BIN_PATH1 = path.join(SRC_DIR, "bin", "Logic2BDD")
        BIN_PATH2 = path.join(SRC_DIR, "bin", "splot2model")
        SO_PATH = path.join(SRC_DIR, "lib", "libcudd-3.0.0.so.0")

        if not all(path.exists(p) for p in [BIN_PATH1, BIN_PATH2, SO_PATH]):
            cmd = re.split(r"\s+", "make")
            call = subprocess.run(cmd, cwd=SRC_DIR, capture_output=True)

            if call.returncode != 0:
                return False

        makedirs(FINAL_PATH, exist_ok=True)

        shutil.copy2(BIN_PATH1, FINAL_PATH)
        shutil.copy2(BIN_PATH2, FINAL_PATH)
        shutil.copy2(SO_PATH, FINAL_PATH)

        return True

    @classmethod
    def check(cls):

        splot2model = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "splot2model")
        logic2bdd = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "Logic2BDD")

        lib = path.join(CONFIG.TOOLS_DIR, "logic2bdd", "libcudd-3.0.0.so.0")

        if not path.exists(splot2model) or not path.exists(
                logic2bdd) or not path.exists(lib):
            return False

        cmd = re.split(r"\s+", f"{splot2model}")
        call = subprocess.run(cmd, capture_output=True)

        if call.returncode != 255:
            return False

        cmd = re.split(r"\s+", f"{logic2bdd}")
        call = subprocess.run(cmd, env=dict(
            LD_LIBRARY_PATH=path.dirname(lib)), capture_output=True)

        if call.returncode != 255:
            return False

        return True

    @classmethod
    def get_installable(cls):
        return Install(
            stub="logic2bdd",
            full="Logic2BDD",
            dependencies=[
                ToolDependency("bison"),
                ToolDependency("flex"),
                ToolDependency("git"),
                ToolDependency("gperf"),
                ToolDependency("make"),
                LibraryDependency("libfl"),
                GitDependency(
                    target="logic2bdd",
                    url="https://github.com/davidfa71/Extending-Logic.git",
                    commit="63ce01c"
                )
            ],
            build=cls.build,
            check=cls.check,
            cls=cls
        )


BDD_Compiler.register_plugin(Logic2BDD)
