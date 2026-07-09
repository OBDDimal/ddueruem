import re
import shutil
from os import makedirs, path

from climplicit import command

import config as CONFIG
from util.cli import cli
from util.plugins import ArchiveDependency, Install, Installable, ToolDependency
from util.runner import via_subprocess

from .compiler import BDD_Compiler

STUB = "cnf2obdd"
EXE_NAME = "cnf2obdd"


class CNF2OBDD(BDD_Compiler, Installable):

    @classmethod
    @command(
        desc="""
        Build BDDs with CNF2OBDD

        >_NOTE_: CNF2OBDD cannot export BDDs and ignores variable order.""",
        ignores=["file_in"],
        hides=["file_out", "best", "svo"],
    )
    def _compile(cls, file_in, file_out=None, soft=False, **kwargs):

        if file_out is not None:
            cli.warn("cnf2obdd does not support BDD exports, --out is ignored")

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)

        call = via_subprocess(f"{exe_path} {file_in}")

        return call

    @classmethod
    def extract_meta(cls, call, file_out):

        m = re.search(r"\|obdd\|\s+:\s+(?P<size>\d+)", call.stdout)

        size = int(m["size"]) if m else None

        time_kc = call.times["time"]

        return None, time_kc, None, size

    @classmethod
    def build(cls):
        build_dir = path.join(CONFIG.CACHE_DIR, STUB, "bdd_minisat_all-1.0.2")
        via_subprocess("make r", cwd=build_dir)

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        makedirs(exe_dir, exist_ok=True)

        shutil.copy2(
            path.join(build_dir, "bdd_minisat_all_release"),
            path.join(exe_dir, EXE_NAME),
        )

    @classmethod
    def check(cls):
        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)

        if path.exists(exe_path):
            call = via_subprocess(f"{exe_path}")
            return call.stderr.startswith("Usage:")

        return False

    @classmethod
    def get_installable(cls):
        return Install(
            stub=STUB,
            full=STUB,
            dependencies=[
                ToolDependency("make"),
                ArchiveDependency(
                    target="cnf2obdd",
                    archive="cnf2obdd.tar.gz",
                    url="http://www.sd.is.uec.ac.jp/toda/code/bdd_minisat_all-1.0.2.tar.gz",
                    md5="56256aa2a866cb765b957e6c3d170bce",
                ),
            ],
            cls=cls,
        )


BDD_Compiler.register_plugin(CNF2OBDD)
