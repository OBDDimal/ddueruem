import shutil
import glob
from os import chmod, makedirs, path

import config as CONFIG
from util.plugins import ArchiveDependency, Executable, Install, Installable, LibraryDependency
from util.runner import via_subprocess


STUB = "uvl2dimacs"
URL = "https://github.com/rheradio/uvl2dimacs/archive/refs/tags/v.1.0.2.zip"

EXE_PATH = path.join(CONFIG.TOOLS_DIR, STUB, STUB)


class UVL2DIMACS(Installable, Executable):

    @classmethod
    def plain(cls, args):

        via_subprocess(
            f"{EXE_PATH} {args}",
            debug = True,
            rc = None
        )


    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds uvl2dimacs after all dependencies have been procured
        """

        source_dir = path.join(CONFIG.CACHE_DIR, STUB)
        source_dir = path.dirname(glob.glob(path.join(source_dir, "*", "Makefile"), recursive = True)[0])

        via_subprocess("make", cwd = source_dir)

        tool_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        makedirs(tool_dir, exist_ok = True)
        shutil.copy2(path.join(source_dir, "build", "uvl2dimacs"), tool_dir)


    @classmethod
    def check(cls):
        """Implements check from Installable, tests if uvl2dimacs is installed correctly"""

        if not path.exists(EXE_PATH):
            return False

        call = via_subprocess(EXE_PATH, rc = 1)

        return call.stderr.startswith("#######################")

    @classmethod
    def get_installable(cls):
        """Generates the install package for uvl2dimacs"""

        return Install(
            stub=STUB,
            dependencies=[
                ArchiveDependency(
                    target=STUB,
                    archive="uvl2dimacs.zip",
                    url=URL,
                    md5 = "35176bcfb2baf542c26619381a32f49c"
                ),
                LibraryDependency("libz")
            ],
            cls=cls,
        )
