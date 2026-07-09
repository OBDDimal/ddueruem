import math
import os
import re
import shutil
from os import makedirs, path

from formats import CNF, ensure_CNF2File

import config as CONFIG
from util.plugins import ArchiveDependency, Executable, Install, Installable
from util.runner import via_subprocess

STUB = "arjun"
FULL = "Arjun"

URL_ARJUN = "https://github.com/meelgroup/arjun/releases/download/release/2.6.1/arjun-linux-amd64.zip"

EXE_PATH = path.join(CONFIG.TOOLS_DIR, STUB, STUB)


class Arjun(Installable, Executable):
    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def plain(cls, args):
        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{path_exe} {args}", rc = None, debug = True)

    @classmethod
    @ensure_CNF2File
    def run(cls, file_in, file_out, preserve_count=False, flags=None):
        """Runs Arjun with default flags, additional flags can be provided via flags"""

        if flags is None:
            flags = "--renumber 0"

        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)

        file_in = path.abspath(file_in)

        cmd = f'{path_exe}{f" {flags}" if flags else ""} {file_in} {file_out}'

        call = via_subprocess(cmd)

        if preserve_count:
            cnf = CNF(from_file=file_out)

            m = re.match(r"c MUST MULTIPLY BY (?P<factor>\d+)", cnf.comments[-1])

            if m:
                factor = int(m["factor"])
                exp = int(math.log(factor, 2))

                print(
                    f"Adding {exp} free variables to preserve #SAT (factor: {factor})"
                )

                cnf.nv += exp

                cnf.to_file(file_out)

        return call

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds Spur after all dependencies have been procured
        """

        makedirs(path.join(CONFIG.TOOLS_DIR, STUB), exist_ok=True)
        shutil.copy2(
            path.join(CONFIG.CACHE_DIR, "arjun", "arjun"),
            path.join(CONFIG.TOOLS_DIR, STUB),
        )

        os.chmod(EXE_PATH, 0o755)

        # src_dir = path.join(CONFIG.CACHE_DIR, STUB)
        return cls.check()

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if PMC is installed correctly"""

        if not path.exists(EXE_PATH):
            return False

        call = via_subprocess(f"{EXE_PATH}", rc=None)
        return call.returncode == 255 and call.stdout.startswith("c o Arjun SHA1")

    @classmethod
    def get_installable(cls):
        """Generates the install package for Arjun"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ArchiveDependency(
                    target="arjun", archive="arjun.tar.gz", url=URL_ARJUN, md5=None
                )
            ],
            cls=cls,
        )
