import re
import shutil
from os import makedirs, path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from climplicit import command
from frameworks import Dimagic

import config as CONFIG
from util.cli import cli
from util.plugins import Executable, Install, Installable, ToolDependency
from util.runner import via_subprocess

from .compiler import BDD_Compiler

STUB = "oxidd"
EXE_NAME = "oxidd-cli"


class OxiDD(BDD_Compiler, Installable, Executable):

    @classmethod
    def plain(cls, args):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)
        via_subprocess(f"{exe_path} {args}", rc = None, debug = True)

    @classmethod
    def format_dddmp(cls, file):
        """Reintroduce auxid for compatibility to BDDSampler / CUDD"""
        with open(file) as fp:
            lines = fp.readlines()

        for i, line in enumerate(lines):

            if re.match(r"^\d", line):

                node_id, var, high, low = re.split(r"\s+", line.strip())
                lines[i] = (
                    f"{node_id} {var} {var if var not in ["F", "T"] else 1} {high} {low}\n"
                )

        lines = [line for line in lines if line is not None]

        with open(file, "w+") as fp:
            fp.writelines(lines)

    @classmethod
    @command(
        desc="CLI tool to build BDDs with OxiDD",
        descs={
            "balanced": "Process orders balanced",
            "best": "Apply Dimagic from Dubslaff et al. (JSS'25)",
            "complement_edges": "Build and export with complement edges",
        },
        ignores=["file_in", "file_out"],
    )
    def _compile(
        cls,
        file_in,
        file_out=None,
        balanced=False,
        complement_edges=False,
        best=False,
        timeout_dimagic: int = None,
        timeout_oxidd: int = None,
        soft=False,
        threads = 1,
        **kwargs,
    ):

        if best:
            with NamedTemporaryFile(suffix=".nnf") as file_nnf:
                call_dimagic = Dimagic.run(
                    file_in,
                    file_out=file_nnf.name,
                    cmd=f"-p -o -v remince -c remince --threads {threads}",
                    for_oxidd=True,
                    timeout=timeout_dimagic,
                )

                call = cls._compile(
                    file_nnf.name,
                    file_out,
                    balanced=True,
                    complement_edges=complement_edges,
                )

                call.add_time("time_pre", call_dimagic.get_time_total())

                return call

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)

        if balanced:
            gbs = "balanced"
        else:
            gbs = "left-deep"

        cmd = f'{exe_path} {file_in}{f" -e {file_out} --dddmp-ascii" if file_out else ""} -t {"bcdd" if complement_edges else "bdd"} --gate-build-scheme {gbs} --threads 1 -p --read-var-order'

        call = via_subprocess(cmd, timeout=timeout_oxidd)

        return call

    @classmethod
    def extract_meta(cls, call, file_out):
        SCALE = {
            "ns": 1e-9,
            "us": 1e-6,
            "ms": 1e-3,
            "s": 1,
            "m": 60,
            "h": 3600,
        }

        m = re.search(r"\s+nodes:\s+(?P<size>\d+)", call.stdout)

        size = int(m["size"]) - 1 if m else None

        time_pre = call.times.get("time_pre")

        m_export = re.search(
            r"exported BDD \([^)]+\) in (?P<time>\d+)\s+(?P<unit>\w+)", call.stdout
        )
        time_export = (
            float(m_export["time"]) * SCALE[m_export["unit"]] if m_export else None
        )

        # m1 = re.search(r"parsing done within (?P<time>\d+)\s+(?P<unit>\w+)", call.stdout)
        # m2 = re.search(r"simplified after (?P<time>\d+)\s+(?P<unit>\w+)", call.stdout)
        # m3 = re.search(r"DD building done within (?P<time>\d+)\s+(?P<unit>\w+)", call.stdout)
        # m4 = re.search(r"garbage collection took (?P<time>\d+)\s+(?P<unit>\w+)", call.stdout)
        # m5 = re.search

        # if m1 and m2 and m3 and m4:
        #     time_kc = float(m1["time"]) * SCALE[m1["unit"]] + float(m2["time"]) * SCALE[m2["unit"]] + float(m3["time"]) * SCALE[m3["unit"]] + float(m4["time"]) * SCALE[m4["unit"]]
        # else:
        # cli.warn("oxidd output could not be parsed, falling back to wall time")
        # times reported by oxidd stdout are not accurate!
        time_kc = call.times["time"]

        return time_pre, time_kc, time_export, size

    @classmethod
    def build(cls):

        cli.subsay("Installing Dimagic")
        Dimagic.install()

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        makedirs(exe_dir, exist_ok=True)

        with TemporaryDirectory() as workdir:

            via_subprocess(f"cargo install oxidd-cli@0.3.0 --root {workdir}")
            shutil.copy2(path.join(workdir, "bin", "oxidd-cli"), exe_dir)

    @classmethod
    def check(cls):

        if not Dimagic.check():
            return False

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)
        return path.exists(exe_path)

    @classmethod
    def get_installable(cls):
        return Install(
            stub="oxidd",
            full="OxiDD",
            dependencies=[
                ToolDependency("cargo"),
            ],
            cls=cls,
        )


BDD_Compiler.register_plugin(OxiDD)
