"""Contains code related to the uniform sampler Smarch"""

import glob
import re
import shutil
import warnings
from os import linesep, path
from tempfile import TemporaryDirectory

import config as CONFIG
from util.plugins import (
    Executable,
    GitDependency,
    Install,
    Installable,
    ToolDependency,
    VenvDependency,
)
from util.runner import via_subprocess

from ..usampler import USampler

# =========================================================================== #

REP_CONFIG = re.compile(r"(?P<rolls>\d+),(?P<conf>[01*]+)")

STUB = "smarch"
FULL = "Smarch"

EXE_NAME = "smarch_base.py"
URL_SMARCH = "https://github.com/jeho-oh/Smarch"

URL_SHARPSAT = "https://github.com/jeho-oh/sharpSAT"
COMMIT_SHARPHSAT = "c44cc3683332a89c255bdfe2c361a2c4fa920751"

# =========================================================================== #


def build_sharpsat():
    """builds the sharpSAT version required by Smarch"""
    smarch_dir = path.join(CONFIG.CACHE_DIR, STUB)
    sharpsat_dir = path.join(smarch_dir, "sharpSAT")
    sharpsat_bin = path.join(sharpsat_dir, "build", "Release")

    # fix cmake of sharpSAT
    with open(path.join(sharpsat_dir, "CMakeLists.txt"), "r", encoding="utf-8") as file:
        lines = file.readlines()

    lines[0] = "cmake_minimum_required (VERSION 3.5)" + linesep
    lines[6] = (
        'set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -std=c++11 -O3 -DNDEBUG -Wall -include cstdint")'
        + linesep
    )

    with open(
        path.join(sharpsat_dir, "CMakeLists.txt"), "w+", encoding="utf-8"
    ) as file:
        file.write("".join(lines))

    # build sharpSAT
    via_subprocess("./setupdev.sh", cwd=sharpsat_dir)
    via_subprocess("make", cwd=sharpsat_bin)


class Smarch(USampler, Installable, Executable):
    """Wraps the uniform sampler Smarch(https://github.com/jeho-oh/Smarch), with support for:
    * Installing Smarch [Installable]
    * Uniform Sampling [USample]
    """

    @classmethod
    def plain(cls, args):

        exe_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)
        venv_path = path.join(exe_dir, ".venv", "bin", "python")

        via_subprocess(f"{venv_path} {exe_path} {args}", debug=True, rc=None)

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size=1024, seed=None, **kwargs):
        """
        Computes a sample with Smarch via subprocess \
        - intended to be called with USampler.sample
        """

        warnings.warn(
            "Smarch scales orders of magnitude worse that other uniform samplers."
        )

        exe_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)
        venv_path = path.join(exe_dir, ".venv", "bin", "python")

        with TemporaryDirectory() as d:
            call = via_subprocess(
                f"{venv_path} {exe_path} -o {d} {file_in} {size}", **kwargs
            )

            file_temp = glob.glob(path.join(d, "*.samples"))[0]
            shutil.copy2(file_temp, file_out)

        return call

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of Smarch into the common format"""

        raw = []

        with open(file_out, "r", encoding="utf-8") as file:
            raw = file.readlines()

        confs = []
        for line in raw:
            config = re.match(r"(?P<config>(-?\d+,)+)$", line)["config"]
            config = [int(x) for x in re.split(r",", config) if x]
            confs.append(config)

        return confs

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds Smarch after all dependencies have been procured
        """

        smarch_dir = path.join(CONFIG.CACHE_DIR, STUB)
        build_sharpsat()

        # repair Smarch
        filename = path.join(smarch_dir, "smarch_base.py")

        line_fixes = [
            {  # fixes sharpSAT path
                "linenr": 16,
                "old": "SHARPSAT = srcdir + '/sharpSAT/Release/sharpSAT'",
                "rep": "SHARPSAT = srcdir + '/sharpSAT/build/Release/sharpSAT'",
            },
        ]

        with open(filename, "r", encoding="utf-8") as file:
            raw = file.readlines()

        for fix in line_fixes:
            linenr = fix["linenr"]
            old = fix["old"]
            rep = fix["rep"]

            if old in raw[linenr]:
                i = raw[linenr].index(old)
                raw[linenr] = " " * i + rep + linesep

        raw = "".join(raw)

        with open(filename, "w", encoding="utf-8") as file:
            file.write(raw)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if Smarch is installed correctly"""

        exe_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)
        venv_path = path.join(exe_dir, ".venv", "bin", "python")

        if not path.exists(exe_path):
            return False

        call = via_subprocess(f"{venv_path} {exe_path}", rc=2)

        out = call.stdout

        return out.startswith("smarch.py -c <constfile> -o <outputdir>  -q")

    @classmethod
    def get_installable(cls):
        """Generates the install package for Smarch"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ToolDependency("make"),
                ToolDependency("cmake"),
                GitDependency(target=f"{STUB}", url=URL_SMARCH, commit=None),
                GitDependency(
                    target=f"{STUB}/sharpSAT", url=URL_SHARPSAT, commit=COMMIT_SHARPHSAT
                ),
                VenvDependency(
                    parent=f"{STUB}",
                    install=["wheel", "pycosat"],
                    from_requirements=False,
                ),
            ],
            cls=cls,
        )


USampler.register_plugin(Smarch)
