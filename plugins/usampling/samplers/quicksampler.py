"""Contains code related to the uniform sampler Quicksampler"""

import re
import shutil
from os import makedirs, path
from tempfile import TemporaryDirectory

from formats import CNF
from pysat.solvers import Solver

import config as CONFIG
from util.plugins import Executable, GitDependency, Install, Installable, ToolDependency
from util.runner import via_subprocess

from ..usampler import USampler

# =========================================================================== #


# =========================================================================== #

REP_CONFIG = re.compile(r"(?P<rolls>\d+),(?P<conf>[01*]+)")

STUB = "quicksampler"
FULL = "Quicksampler"

EXE_NAME = "quicksampler"
URL_QS = "https://github.com/OBDDimal/quicksampler"


class Quicksampler(USampler, Installable, Executable):
    """Wraps the uniform sampler Quicksampler (https://github.com/RafaelTupynamba/quicksampler), with support for:
    * Installing Quicksampler [Installable]
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

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        file_abs = path.abspath(file_in)

        with TemporaryDirectory(delete=False) as dir_tmp:
            file_tmp = shutil.copy2(file_abs, dir_tmp)

            cmd = f"./{EXE_NAME} -n {size} {file_tmp}"
            call = via_subprocess(cmd, cwd=exe_dir, **kwargs)

            shutil.copy2(f"{file_tmp}.samples", file_out)

        return call

    @classmethod
    def cleanup(cls, _file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of Quicksampler into the common format"""

        with open(file_out) as fp:
            raw = fp.readlines()

        variables = [int(x) for x in re.split(r"\s+", raw[0].strip())]

        confs = [re.split(r"[:]", line)[1].strip() for line in raw[1:]]
        confs = [
            [
                (variables[i]) if x == "1" else -(variables[i])
                for i, x in enumerate(line)
            ]
            for line in confs
        ]

        confs_final = []

        cnf = CNF(from_file=_file_in)
        with Solver(bootstrap_with=cnf.clauses) as solver:
            for conf in confs:
                if solver.solve(conf):
                    confs_final.append(solver.get_model())
                else:
                    confs_final.append(conf)

        return confs_final

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds Quicksampler after all dependencies have been procured
        """

        src_dir = path.join(CONFIG.CACHE_DIR, STUB)
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        # with open(path.join(src_dir, "quicksampler.cpp")) as fp:
        #     lines = fp.readlines()

        # # Find the line with results_file.open
        # patch_lines = '''        // Write independent support variables as first line
        #         for (size_t i = 0; i < ind.size(); ++i) {
        #             results_file << ind[i];
        #             if (i < ind.size() - 1)
        #                 results_file << " ";
        #         }
        #         results_file << '\\n';
        # '''

        # patched_lines = []
        # for line in lines:
        #     patched_lines.append(line)
        #     if 'results_file.open(input_file + ".samples")' in line:
        #         patched_lines.append(patch_lines)

        # with open(path.join(src_dir, "quicksampler.cpp"), "w") as fp:
        #     fp.writelines(patched_lines)

        via_subprocess("make", cwd=src_dir)

        makedirs(exe_dir, exist_ok=True)
        shutil.copy2(path.join(src_dir, EXE_NAME), exe_dir)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if Quicksampler is installed correctly"""

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        exe_path = path.join(exe_dir, EXE_NAME)

        if not path.exists(exe_path):
            return False

        call = via_subprocess(f"{exe_path}", rc=None)

        return call.returncode == -6

    @classmethod
    def get_installable(cls):
        """Generates the install package for Quicksampler"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ToolDependency("g++"),
                ToolDependency("make"),
                GitDependency(target=f"{STUB}", url=URL_QS, commit=None),
            ],
            cls=cls,
        )


USampler.register_plugin(Quicksampler)
