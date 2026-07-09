"""Contains code related to the uniform sampler KUS"""

import re
import shutil
from os import path
from tempfile import TemporaryDirectory

import config as CONFIG
from util.plugins import Executable, GitDependency, Install, Installable, VenvDependency
from util.runner import via_subprocess

from ..usampler import USampler

# =========================================================================== #


# =========================================================================== #

REP_CONFIG = re.compile(r"\d+,(?P<conf>[\d\s-]+)")
REP_TIME_DDNNF = re.compile(r"\:\s+(?P<time>\d+\.\d+)$")

STUB = "kus"
FULL = "KUS"

EXE_NAME = "KUS.py"
URL_KUS = "https://github.com/h3ssto/KUS"
COMMIT_KUS = "ca93673"


class KUS(USampler, Installable, Executable):
    """Wraps the uniform sampler KUS (https://github.com/meelgroup/KUS), with support for:
    * Installing KUS [Installable]
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
        Computes a sample with KUS via subprocess \
        - intended to be called with USampler.sample
        """

        file_in = path.abspath(file_in)

        # KUS does not clear up the d-DNNF
        with TemporaryDirectory() as td:

            file_temp = shutil.copy(file_in, td)

            exe_dir = path.join(CONFIG.CACHE_DIR, STUB)
            exe_path = path.join(exe_dir, EXE_NAME)
            venv_path = path.join(exe_dir, ".venv", "bin", "python")

            call = via_subprocess(
                f"{venv_path} {exe_path} {file_temp} --samples {size} --outputfile {file_out}{f' --seed {seed}' if seed is not None else ''}",
                cwd=exe_dir,
                rc=0,
                **kwargs,
            )

            stdout = call.stdout
            lines = re.split(r"\n", stdout)
            time_ddnnf = float(REP_TIME_DDNNF.search(lines[0])["time"])

            call.times["time_kc"] = time_ddnnf
            call.times["time"] -= time_ddnnf

        return call

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of KUS into the common format"""

        raw = []

        with open(file_out, "r", encoding="utf-8") as file:
            raw = file.readlines()

        confs = []

        for line in raw:
            if m := REP_CONFIG.match(line):
                conf = m["conf"].strip()
                conf = [int(x) for x in re.split(r"\s+", conf)]
                confs.append(conf)

        return confs

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds KUS after all dependencies have been procured
        """

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if KUS is installed correctly"""

        exe_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)
        venv_path = path.join(exe_dir, ".venv", "bin", "python")

        if not path.exists(exe_path) or not path.exists(venv_path):
            return False

        call = via_subprocess(f"{venv_path} {exe_path}", rc=2)

        out = call.stderr
        return out.startswith("usage: KUS.py [-h] [--outputfile OUTPUTFILE]")

    @classmethod
    def get_installable(cls):
        """Generates the install package for KUS"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                GitDependency(target=f"{STUB}", url=URL_KUS, commit=COMMIT_KUS),
                VenvDependency(
                    parent=f"{STUB}",
                    install=["wheel", "numpy", "pydot"],
                    # requirements to outdated to use
                    from_requirements=False,
                ),
            ],
            cls=cls,
        )


USampler.register_plugin(KUS)
