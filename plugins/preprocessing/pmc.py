import shutil
from os import chmod, makedirs, path

from formats import CNF, ensure_CNF2File

import config as CONFIG
from util.plugins import Executable, HttpDependency, Install, Installable
from util.runner import via_subprocess

STUB = "pmc"
FULL = ""

URL_PMC = "https://www.cril.univ-artois.fr/kc/ressources/pmc_linux"


class PMC(Installable, Executable):
    # -----------------------------------------------------------------------------
    # Installable #
    # -----------------------------------------------------------------------------

    @classmethod
    @ensure_CNF2File
    def run(
        cls, file_in, file_out=None, preserve_equivalence=True, flags=None, cmd=None
    ):
        """Executes PMC, either with preserving equaltiy or without.
        Source: https://www.cril.univ-artois.fr/kc/pmc.html
        """
        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)

        file_in = path.abspath(file_in)

        if cmd:
            cmd = f"{path_exe} {cmd} {file_in}"
        else:
            if preserve_equivalence:
                cmd = f"{path_exe} -vivification -eliminateLit -litImplied -iterate=10 {flags if flags else ''} {file_in}"
            else:
                cmd = f"{path_exe} -vivification -eliminateLit -litImplied -iterate=10 -equiv -orGate -affine {flags if flags else ''} {file_in}"

        call = via_subprocess(cmd)

        cnf_old = CNF(from_file=file_in)
        cnf_new = CNF(from_string=call.stdout)
        cnf_new.nv = cnf_old.nv
        cnf_new.comments = cnf_old.comments

        if file_out is not None:
            cnf_new.to_file(file_out)

        return cnf_new

    @classmethod
    def plain(cls, args):
        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{path_exe} {args}", debug=True, rc=None)

    @classmethod
    def build(cls):
        """
        Implements build from Installable, as PMC is provided as a binary we just copy PMC and set the permissions
        """

        path_download = path.join(CONFIG.CACHE_DIR, "pmc")
        dir_exe = path.join(CONFIG.TOOLS_DIR, STUB)
        path_exe = path.join(dir_exe, STUB)

        makedirs(dir_exe, exist_ok=True)

        shutil.copy2(path_download, path_exe)
        chmod(path_exe, 0o0777)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if PMC is installed correctly"""

        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)

        if not path.exists(path_exe):
            return False

        call = via_subprocess(f"{path_exe} --help")

        return "USAGE:" in call.stderr

    @classmethod
    def get_installable(cls):
        """Generates the install package for PMC"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[HttpDependency(target=f"{STUB}", file="pmc", url=URL_PMC)],
            cls=cls,
        )
