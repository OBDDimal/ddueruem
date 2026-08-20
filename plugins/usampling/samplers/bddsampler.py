"""Contains code related to the uniform sampler BDDSampler"""

import re
import shutil
import subprocess
from os import makedirs, path
from signal import SIGINT, signal
from tempfile import NamedTemporaryFile

from bdd.compilers import CUDD, OxiDD
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

from ..usampler import USampler

# =========================================================================== #


# =========================================================================== #

REP_CONFIG = re.compile(r"\d+,(?P<conf>[\d\s-]+)")
REP_TIME_DDNNF = re.compile(r"\:\s+(?P<time>\d+\.\d+)$")

STUB = "BDDSampler"
FULL = "BDDSampler"

EXE_PATH = path.join(CONFIG.TOOLS_DIR, "BDDSampler", "BDDSampler")
LIB_PATH = path.abspath(path.join(CONFIG.CACHE_DIR, "BDDSampler", "lib"))
URL = "https://github.com/davidfa71/BDDSampler"


def _initializer():
    signal(SIGINT, lambda: None)


class BDDSampler(USampler, Installable, Executable):
    """Wraps the uniform sampler BDDSampler (https://github.com/davidfa71/BDDSampler), with support for:
    * Installing BDDSampler [Installable]
    * Uniform Sampling [USample]
    """

    @classmethod
    def plain(cls, args):
        via_subprocess(
            f"{EXE_PATH} {args}",
            env=dict(LD_LIBRARY_PATH=LIB_PATH),
            rc=None,
            debug=True,
        )

    @classmethod
    def _sample_uniform(
        cls,
        file_in,
        file_out,
        bdd_file=None,
        size=1024,
        timeout=None,
        seed=None,
        **kwargs,
    ):

        kc_time = None
        with NamedTemporaryFile(suffix=".dddmp") as tmp:
            if bdd_file is None:

                tmpfile = tmp.name

                out = CUDD.compile(
                    file_in,
                    tmpfile,
                    complement_edges=True,
                    save_varnames=True,
                    best=True
                )

                kc_time = out.meta["times"]["time_kc"]

                if not out.success:
                    if out.timeouted:
                        raise subprocess.TimeoutExpired(
                            "BDDSampler: BDD Compilation", timeout
                        )
                    else:
                        raise out.meta["error"]

                file_bdd = path.abspath(tmpfile)
            else:
                file_bdd = path.abspath(bdd_file)

            cls.fix_dddmp(file_in, file_bdd)

            cmd = f"{EXE_PATH} {size} {file_bdd}"

            call = via_subprocess(
                cmd, env=dict(LD_LIBRARY_PATH=LIB_PATH), timeout=timeout, **kwargs
            )

        if kc_time:
            call.times["time_kc"] = kc_time

        samples_raw = call.stdout

        with open(file_out, "w+") as fp:
            fp.write(samples_raw)

        return call

    @classmethod
    def cleanup(cls, file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):

        with open(file_out, encoding="utf-8") as fp:
            raw = fp.readlines()

        configs = [re.split(r"\s+", line.strip()) for line in raw]
        configs = [
            [i + 1 if x == "1" else 0 for i, x in enumerate(config)]
            for config in configs
        ]
        configs = [{x for x in config if x > 0} for config in configs]

        return configs

    @classmethod
    def fix_dddmp(cls, file_in, file_dddmp):

        with open(file_dddmp) as fp:
            lines = fp.readlines()

        if len(lines) < 5:
            raise ValueError("BDD empty")

        for i, line in enumerate(lines):

            if line.startswith(".ver"):
                lines[i] = ".ver DDDMP-3.0\n"

            if line.startswith(".varinfo"):
                lines[i] = ".varinfo 1\n"

            if line.startswith(".rootnames"):
                lines[i] = None

            if line.startswith(".suppvarnames"):

                cnf = CNF(from_file=file_in)

                cnf.sanitize_variable_names()
                varnames = cnf.variables_by_name

                lines[i] = f".varnames {' '.join(varnames)}\n{line}"

            if re.match(r"^\d+", line):

                node_id, var, high, low = re.split(r"\s+", line.strip())
                lines[i] = (
                    f"{node_id} {var} {var if var not in ["F", "T"] else 1} {high} {low}\n"
                )

        lines = [line for line in lines if line is not None]

        with open(file_dddmp, "w+") as fp:
            fp.writelines(lines)

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds BDDSampler after all dependencies have been procured
        """

        OxiDD.install()

        src_dir = path.join(CONFIG.CACHE_DIR, "BDDSampler")

        file_fix = path.join(src_dir, "sampler", "src", "synExp.hpp")

        # fix missing include
        with open(file_fix) as fp:
            raw = fp.read()

        content = re.sub(
            r"#include <unordered_map>",
            "#include <unordered_map>\n#include <limits>",
            raw,
        )

        with open(file_fix, "w+") as fp:
            fp.write(content)

        via_subprocess("./configure", cwd=src_dir)
        via_subprocess("make", cwd=src_dir)

        makedirs(path.dirname(EXE_PATH), exist_ok=True)
        shutil.copy2(path.join(src_dir, "bin", "BDDSampler"), EXE_PATH)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if BDDSampler is installed correctly"""

        if not path.exists(EXE_PATH):
            return False

        lib = path.join(CONFIG.CACHE_DIR, "BDDSampler", "lib")

        call = via_subprocess(EXE_PATH, env=dict(LD_LIBRARY_PATH=lib), rc=255)

        return call.returncode == 255

    @classmethod
    def get_installable(cls):
        """Generates the install package for BDDSampler"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                LibraryDependency("libgmp"),
                ToolDependency("make"),
                GitDependency(
                    target=f"{STUB}",
                    url=URL,
                    commit="9d03c33c0791efbebc382b25816baa8b186ba137",
                ),
            ],
            cls=cls,
        )


USampler.register_plugin(BDDSampler)
