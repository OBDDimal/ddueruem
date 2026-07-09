"""Contains code related to the uniform sampler Spur"""

import random
import re
import shutil
from copy import copy
from os import linesep, makedirs, path
from tempfile import NamedTemporaryFile

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

REP_CONFIG = re.compile(r"(?P<rolls>\d+),(?P<conf>[01*]+)")

STUB = "spur"
FULL = "Spur"

EXE_NAME = "spur"
URL_SPUR = "https://github.com/ZaydH/spur"


class Spur(USampler, Installable, Executable):
    """Wraps the uniform sampler Spur (https://github.com/ZaydH/spur), with support for:
    * Installing Spur [Installable]
    * Counting [Counter]
    * Uniform Sampling [USample]
    """

    @classmethod
    def plain(cls, args):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{exe_path} {args}", debug=True, rc=None)

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size=1024, seed=None, **kwargs):
        """
        Computes a sample with Spur via subprocess \
        - intended to be called with USampler.sample
        """

        file_abs = path.abspath(file_in)
        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, STUB)

        cmd = f"{exe_path} -cnf {file_abs} -s {size} -out {file_out}{f' -seed {seed}' if seed is not None else ''}"
        call = via_subprocess(cmd, **kwargs)

        return call

    @classmethod
    def cleanup(cls, _file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of Spur into the common format"""

        raw = []

        with open(file_out, "r", encoding="utf-8") as file:
            raw = file.readlines()

        confs = []

        for line in raw:
            if m := REP_CONFIG.match(line):
                rolls = int(m["rolls"])
                oconf = m["conf"].strip()

                free = []
                conf = []
                for i, c in enumerate(oconf):
                    if c == "1":
                        conf.append(i + 1)
                    elif c == "0":
                        conf.append(-(i + 1))
                    else:
                        free.append(i + 1)

                oconf = conf
                for _ in range(rolls):
                    conf = copy(oconf)
                    for x in free:
                        if random.randint(0, 1) == 1:
                            conf.append(x)
                        else:
                            conf.append(-x)

                    confs.append(conf)

        return confs

    @classmethod
    def _count(cls, file_in, **kwargs):

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        cmd = f"./spur -cnf {file_in} -count-only"

        call = via_subprocess(cmd, cwd=exe_dir, rc=None, **kwargs)

        stdout = call.stdout
        m = re.search(r"# solutions\s*[\n\r](?P<count>\d+)", stdout)

        return int(m["count"])

    @classmethod
    def _cardinalities(cls, file_in):

        cnf = CNF(from_file=file_in)
        var2count = {}

        with NamedTemporaryFile(suffix=".dimacs") as ntf:
            for x in range(1, cnf.nv + 1):
                cnf.clauses.append([x])

                cnf.to_file(ntf.name)
                var2count[x] = cls._count(ntf.name)

                cnf.clauses.pop()

        return var2count

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds Spur after all dependencies have been procured
        """

        src_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        makedirs(exe_dir, exist_ok=True)

        with open(path.join(src_dir, "CMakeLists.txt"), "r", encoding="utf-8") as file:
            lines = file.readlines()

        lines[0] = "cmake_minimum_required (VERSION 3.5)" + linesep
        lines[11] = 'set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE}' + '\
            -std=c++11 -O3 -DNDEBUG -Wall -include cstdint")' + linesep

        with open(path.join(src_dir, "CMakeLists.txt"), "w+", encoding="utf-8") as file:
            file.write("".join(lines))

        via_subprocess("cmake -DCMAKE_BUILD_TYPE=Release .", cwd=src_dir)
        via_subprocess("make", cwd=src_dir)

        shutil.copy2(path.join(src_dir, EXE_NAME), exe_dir)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if Spur is installed correctly"""

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)

        if not path.exists(exe_path):
            return False

        call = via_subprocess(exe_path, rc=None)
        return call.returncode == 64

    @classmethod
    def get_installable(cls):
        """Generates the install package for Spur"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ToolDependency("make"),
                ToolDependency("cmake"),
                LibraryDependency("libgmp"),
                GitDependency(target=f"{STUB}", url=URL_SPUR, commit=None),
            ],
            cls=cls,
        )


USampler.register_plugin(Spur, set_default=True)
