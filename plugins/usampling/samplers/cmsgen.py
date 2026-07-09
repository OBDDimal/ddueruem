"""Contains code related to the uniform-like sampler CMSGen"""

import re
import shutil
from os import chmod, makedirs, path

import config as CONFIG
from util.plugins import ArchiveDependency, Executable, Install, Installable
from util.runner import via_subprocess

from ..usampler import USampler

# =========================================================================== #


# =========================================================================== #

REP_CONFIG = re.compile(r"(?P<rolls>\d+),(?P<conf>[01*]+)")

STUB = "cmsgen"
FULL = "CMSGen"

EXE_NAME = "cmsgen"
URL_CMSGen = "https://github.com/meelgroup/cmsgen/releases/download/release/6.1.1/cmsgen-linux-amd64.zip"


class CMSGen(USampler, Installable, Executable):
    """Wraps the uniform-like sampler CMSGen (https://github.com/meelgroup/cmsgen), with support for:
    * Installing Quicksampler [Installable]
    * Uniform Sampling [USample]
    """

    @classmethod
    def plain(cls, args):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{exe_path} {args}", rc=None, debug=True)

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size=1024, seed=None, **kwargs):
        """
        Computes a uniform sample with CMSGen via subprocess \
        - intended to be called with USampler.sample
        """

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        file_abs = path.abspath(file_in)

        call = via_subprocess(
            f"./{EXE_NAME}{f' --seed {seed}' if seed is not None else ''} --samples {size} --samplefile {file_out} {file_abs}",
            cwd=exe_dir,
            rc=10,
            **kwargs,
        )

        return call

    @classmethod
    def cleanup(cls, _file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of CMSGen into the common format"""

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
        CMSGen is provided as binary, so build only moves it to the respective tool directory
        """

        src_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        path_exe = path.join(exe_dir, STUB)

        makedirs(exe_dir, exist_ok=True)

        shutil.copy2(path.join(src_dir, EXE_NAME), exe_dir)
        chmod(path_exe, 0o0777)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if CMSGen is installed correctly"""

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)

        if not path.exists(exe_path):
            return False

        call = via_subprocess(f"{exe_path} -h", rc=None)

        return call.stdout.startswith("Usage: cmsgen")

    @classmethod
    def get_installable(cls):
        """Generates the install package for CMSGen"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ArchiveDependency(
                    target=f"{STUB}",
                    archive="cmsgen-linux-amd64.zip",
                    url=URL_CMSGen,
                    md5="60cc0392f49a75cecc4e746d83fdb78a",
                )
            ],
            cls=cls,
        )


USampler.register_plugin(CMSGen)
