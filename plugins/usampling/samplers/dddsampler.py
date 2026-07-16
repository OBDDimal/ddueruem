"""Contains code related to the uniform sampler 3dsampler"""

import re
import shutil
from os import chmod, makedirs, path
from tempfile import NamedTemporaryFile

from bdd.compilers import CUDD

import config as CONFIG
from util.plugins import (
    Executable,
    Install,
    Installable,
    HttpDependency
)
from util.runner import via_subprocess

from ..usampler import USampler

# =========================================================================== #


# =========================================================================== #

REP_CONFIG = re.compile(r"(?P<rolls>\d+),(?P<conf>[01*]+)")

STUB = "3dsampler"
FULL = "3dsampler"

EXE_NAME = "3dsampler"
URL_3dsampler = "https://github.com/OBDDimal/3dsampler/releases/download/latest/3dsampler-linux-x86_64-static"

EXE_PATH = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)


class DDDSampler(USampler, Installable, Executable):
    """Wraps the uniform sampler 3dsampler (https://github.com/OBDDimal/3dsampler), with support for:
    * Installing 3dsampler [Installable]
    * Uniform Sampling [USample]
    """

    @classmethod
    def plain(cls, args):
        
        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)
        via_subprocess(f"{exe_path} {args}", debug=True, rc=None)

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size=1024, seed=None, timeout = None, bdd_file = None, **kwargs):
        """
        Computes a sample with 3dsampler via subprocess \
        - intended to be called with USampler.sample
        """
        kc_time = None
        with NamedTemporaryFile(suffix=".dddmp") as tmp:
            if bdd_file is None:

                tmpfile = tmp.name

                out = CUDD.compile(
                    file_in,
                    tmpfile,
                    complement_edges=True,
                    save_varnames=True,
                    best=True,
                )

                kc_time = out.meta["times"]["time_kc"]

                file_bdd = path.abspath(tmpfile)
            else:
                file_bdd = path.abspath(bdd_file)

            cmd = f"{EXE_PATH} {file_bdd} --size {size}{f'--seed {seed}' if seed is not None else ''}"

            call = via_subprocess(
                cmd, **kwargs
            )

        if kc_time:
            call.times["time_kc"] = kc_time

        samples_raw = call.stdout

        with open(file_out, "w+") as fp:
            fp.write(samples_raw)

        return call

    @classmethod
    def cleanup(cls, _file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of 3dsampler into the common format"""

        with open(file_out) as fp:
            lines = fp.readlines()
        
        configs = [re.split(r"\s+", line.strip()) for line in lines]
        configs = [{int(x) for x in config if int(x) > 0} for config in configs]

        return configs

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds 3dsampler after all dependencies have been procured
        """

        src_path = path.join(CONFIG.CACHE_DIR, STUB)
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        makedirs(exe_dir, exist_ok=True)
        shutil.copy2(src_path, exe_dir)
        chmod(path.join(exe_dir, STUB), 0o0777)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if 3dsampler is installed correctly"""

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)

        if path.exists(exe_path):
            call = via_subprocess(f"{exe_path}", rc = 1)
            
            if call.stderr.startswith("error: MissingPath"):
                return True
        
        return False

    @classmethod
    def get_installable(cls):
        """Generates the install package for 3dsampler"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                HttpDependency(target=f"{STUB}", url=URL_3dsampler, file="3dsampler"),
            ],
            cls=cls,
        )


USampler.register_plugin(DDDSampler, "3dsampler")
