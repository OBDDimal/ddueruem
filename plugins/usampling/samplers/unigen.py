"""Contains code related to the uniform sampler Unigen"""

import re
import shutil
from os import chmod, makedirs, path

import config as CONFIG
from util.plugins import ArchiveDependency, Executable, Install, Installable
from util.runner import via_subprocess

from ..usampler import USampler

# =========================================================================== #

REP_CONFIG = re.compile(r"(?P<rolls>\d+),(?P<conf>[01*]+)")

STUB = "unigen"
FULL = "unigen"

EXE_NAME = "unigen"
URL_UNIGEN = "https://github.com/meelgroup/unigen/releases/download/release/2.7.0/unigen-linux-amd64.zip"


class Unigen(USampler, Installable, Executable):
    """Wraps the uniform sampler Unigen (https://github.com/meelgroup/unigen), with support for:
    * Installing Unigen [Installable]
    * Uniform Sampling [USample]
    """

    @classmethod
    def plain(cls, args):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{exe_path} {args}", debug=True, rc=None)

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size=1024, seed=None, **kwargs):
        """
        Computes a sample with Quicksampler via subprocess \
        - intended to be called with USampler.sample
        """

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        file_abs = path.abspath(file_in)

        call = via_subprocess(
            f"{exe_path} {f' --seed {seed}' if seed is not None else ''} --samples {size} --sampleout {file_out} {file_abs}",
            rc=0,
            **kwargs,
        )

        return call

    @classmethod
    def cleanup(cls, _file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of Quicksampler into the common format"""

        with open(file_out) as fp:
            raw = fp.readlines()

        confs = [re.split(r"\s", line.strip()) for line in raw]
        confs = [[int(x) for x in conf if x != "0"] for conf in confs]

        return confs

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds Unigen after all dependencies have been procured
        """

        src_exe = path.join(CONFIG.CACHE_DIR, STUB, EXE_NAME)
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        path_exe = path.join(exe_dir, EXE_NAME)

        makedirs(exe_dir, exist_ok=True)

        shutil.copy2(src_exe, path_exe)
        chmod(path_exe, 0o0777)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if Unigen is installed correctly"""

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)

        if not path.exists(exe_path):
            return False

        call = via_subprocess(f"{exe_path} -h", rc=None)
        return call.stdout.startswith("Usage: unigen")

    @classmethod
    def get_installable(cls):
        """Generates the install package for Unigen"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ArchiveDependency(
                    target=f"{STUB}",
                    archive="unigen-linux-amd64.gz",
                    url=URL_UNIGEN,
                    md5="19f60b03cd1288fabbadd95b97789ee6",
                )
            ],
            cls=cls,
        )


USampler.register_plugin(Unigen)
