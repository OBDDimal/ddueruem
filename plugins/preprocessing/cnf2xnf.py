import re
import shutil
from copy import deepcopy
from os import makedirs, path
from tempfile import NamedTemporaryFile

from formats import ensure_CNF2File

import config as CONFIG
from util.plugins import Executable, GitDependency, Install, Installable, ToolDependency
from util.runner import via_subprocess

STUB = "cnf2xnf"
FULL = ""

URL = "https://github.com/arminbiere/cnf2xnf"


class cnf2xnf(Installable, Executable):
    # -----------------------------------------------------------------------------
    # Installable #
    # -----------------------------------------------------------------------------

    @classmethod
    def run(cls, file_in, file_out=None, preserve_equivalence=True, flags=None):
        pass

    @classmethod
    def plain(cls, args):

        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{path_exe} {args}", debug=True, rc=None)

    @classmethod
    @ensure_CNF2File
    def identify_xor_groups(cls, file_in):

        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)

        file_in = path.abspath(file_in)

        with NamedTemporaryFile() as file:
            file_tmp = file.name
            via_subprocess(f"{path_exe} {file_in} {file_tmp} --no-eliminate")

            with open(file_tmp) as fp:
                lines = fp.readlines()

        clauses_rem = []
        xor_groups = []

        for line in lines:
            line = line.strip()
            if line.startswith("x"):
                group = {
                    int(x)
                    for x in re.split(r"\s+", line[1:].strip())
                    if x and abs(int(x)) > 0
                }
                xor_groups.append(group)

            elif line.startswith("c") or line.startswith("p"):
                continue
            else:
                clauses_rem.append(
                    sorted(
                        [
                            int(x)
                            for x in re.split(r"\s+", line[:-1].strip())
                            if abs(int(x)) > 0
                        ],
                        key=abs,
                    )
                )

        # clauses_rem = [clause for clause in clauses_rem if clause]

        xor_groups_raw = sorted(deepcopy(xor_groups), key=len, reverse=True)
        xor_groups = sorted(
            [{abs(x) for x in group} for group in xor_groups], key=len, reverse=True
        )
        merged = True

        while merged:
            var2xor = dict()
            merged = False

            for i, group in enumerate(xor_groups):
                for x in group:
                    if x in var2xor:
                        merged = True
                        ind = var2xor[x]

                        xor_groups[ind].update(group)

                        for y in group:
                            var2xor[y] = ind

                        xor_groups[i] = None
                        break
                    else:
                        var2xor[x] = i

            xor_groups = [g for g in xor_groups if g is not None]

        xor_variables = set(var2xor)

        return xor_variables, xor_groups, xor_groups_raw, clauses_rem

    @classmethod
    def build(cls):
        """
        Implements build from Installable, as PMC is provided as a binary we just copy PMC and set the permissions
        """

        build_path = path.join(CONFIG.CACHE_DIR, STUB)

        via_subprocess("./configure", cwd=build_path)
        via_subprocess("make", cwd=build_path)

        dir_exe = path.join(CONFIG.TOOLS_DIR, STUB)

        makedirs(dir_exe, exist_ok=True)

        shutil.copy2(path.join(build_path, "cnf2xnf"), dir_exe)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if PMC is installed correctly"""

        path_exe = path.join(CONFIG.TOOLS_DIR, STUB, STUB)

        if not path.exists(path_exe):
            return False

        call = via_subprocess(f"{path_exe} --help")

        return "usage: cnf2xnf" in call.stdout

    @classmethod
    def get_installable(cls):
        """Generates the install package for PMC"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ToolDependency("make"),
                GitDependency(target=f"{STUB}", url=URL, commit=None),
            ],
            cls=cls,
        )
