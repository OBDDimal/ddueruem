import glob
import re
import shutil
import subprocess
from os import makedirs, path
from tempfile import NamedTemporaryFile

from formats import CNF, ensure_CNF2File
from pysat.solvers import Solver

import config as CONFIG
from util.plugins import Executable, GitDependency, Install, Installable, ToolDependency
from util.runner import via_subprocess

STUB = "featjar"
FULL = "FeatJar"

URL_YASA = "https://github.com/FeatureIDE/FeatJAR"

EXE_PATH = path.join(CONFIG.TOOLS_DIR, STUB, "featjar.jar")


class FeatJar(Installable, Executable):

    @classmethod
    def plain(cls, args):

        cmd = f"java -jar {EXE_PATH} {args}"
        via_subprocess(cmd, rc=None, debug=True)

    @classmethod
    @ensure_CNF2File
    def _sample_twise(
        cls, file, file_out, t=2, n=None, seed=None, iterations=1, **kwargs
    ):

        file_abs = path.abspath(file)

        cmd = f"java -jar {EXE_PATH} yasa --input {file_abs} --output {file_out} --t {t} --i {iterations} --overwrite"

        if kwargs.get("timeout") is not None:
            cmd += f' --timeout {kwargs["timeout"]}'

        if n is not None:
            cmd += f" --n {n}"

        if seed is not None:
            cmd += f" --seed {seed}"

        call = via_subprocess(cmd, rc=None)

        if "[ERROR] Could not compute result" in call.stderr:
            raise subprocess.TimeoutExpired(
                "YASA timeouted in workaround", kwargs["timeout"]
            )

        return call

    @classmethod
    @ensure_CNF2File
    def _count_twise(cls, file_in, t=2, iterations=0, **kwargs):

        file_in = path.abspath(file_in)

        with NamedTemporaryFile(suffix=".csv") as ntf:
            file_out = path.abspath(ntf.name)

            call = cls._sample_twise(
                file_in, file_out, t=t, iterations=iterations, **kwargs
            )

            if call.returncode != 0:
                raise subprocess.TimeoutExpired("YASA timeouted", kwargs.get("timeout"))

            cmd = f"java -jar {EXE_PATH} t-wise-coverage --quiet --input {file_out} --t {t} --count-only --fm {file_in} --overwrite"

            call = via_subprocess(cmd, rc=None)

            ints = int(re.split(r"[\n\s]+", call.stdout)[0].strip())
            ints += int(re.split(r"[\n\s]+", call.stdout)[1].strip())

        return ints

    @classmethod
    def _compute_coverage(cls, file_in, sample, t=2):

        with NamedTemporaryFile(suffix=".csv") as ntf:
            file = path.abspath(ntf.name)

            cls.store_sample(file_in, sample, file)

            cmd = f"java -jar {EXE_PATH} t-wise-coverage --quiet --input {file} --t {t}"

            call = via_subprocess(cmd, rc=None)

            print(call.stdout)

    @classmethod
    def format_twise(cls, file_in, file_out):

        return cls.parse_featjar_sample_format(file_in, file_out)

    @classmethod
    def parse_featjar_sample_format(cls, file_in, file_sample, ommit_leading_columns=1):

        cnf = CNF(from_file=file_in)

        with open(file_sample, "r") as file:
            lines = file.readlines()

        confs = [re.split(r";", line.strip()) for line in lines]

        header = confs[0][ommit_leading_columns:]

        yasa2normal = {}

        for i, name in enumerate(header):

            # workaround for https://github.com/FeatureIDE/FeatJAR/issues/11
            if name.isdigit():
                yasa2normal[i] = int(name.strip())
            else:
                yasa2normal[i] = cnf.names2var[name.strip()]

        # remove header
        confs = confs[1:]

        # remove leading conf id
        confs = [conf[ommit_leading_columns:] for conf in confs]

        confs_clean = []

        for conf in confs:
            conf_clean = set()

            for i, x in enumerate(conf):
                var = yasa2normal[i]

                if x == "+":
                    conf_clean.add(var)
                elif x == "-":
                    conf_clean.add(-var)

            # complete via SAT solver due to zeros
            with Solver(bootstrap_with=cnf.clauses) as solver:
                solver.solve(conf_clean)
                conf_clean = set(solver.get_model())

            confs_clean.append(conf_clean)

        return confs_clean

    @classmethod
    def compute_atomic_sets(cls, file_in, crossover=False, timeout=None):

        file_abs = path.abspath(file_in)

        with NamedTemporaryFile() as file:
            cmd = f"java -jar {EXE_PATH} atomic-sets-sat4j --input {file_abs} --output {file.name} --overwrite"

            if timeout:
                cmd += f" --timeout {timeout}"

            call = via_subprocess(cmd, rc=None)

            if call.returncode == 1:
                if f"Timeout of {timeout}s was reached" in call.stderr:
                    raise subprocess.TimeoutExpired(cmd, timeout)

            cnf = CNF(from_file=file.name)

            # With workaround for https://github.com/FeatureIDE/FeatJAR-formula-analysis-sat4j/issues/7
            sets = [ls for ls in cnf.clauses if len(ls) > 1]

            if crossover:
                return sets

            sets_final = []

            # work around criss-crossing
            for ats in sets:

                lower = {abs(x) for x in ats if x < 0}
                higher = {x for x in ats if x > 0}

                if len(lower) > 1:
                    sets_final.append(lower)

                if len(higher) > 1:
                    sets_final.append(higher)

        return sets_final

    @classmethod
    def compute_slice(cls, file_in, file_out, slice_by_vars, timeout=None):

        file_abs = path.abspath(file_in)

        cnf = CNF(from_file=file_in)

        slice_by_names = [cnf.var2names[var] for var in slice_by_vars]

        with NamedTemporaryFile() as file:
            cmd = f"java -jar {EXE_PATH} projection-sat4j --input {file_abs} --output {file.name} --slice {','.join(slice_by_names)}"

            if timeout:
                cmd += f" --timeout {timeout}"

            via_subprocess(cmd, rc=None)

            clauses = cls.parse_featjar_sample_format(
                file_in, file.name, ommit_leading_columns=2
            )

        cnf2 = CNF(from_clauses=clauses, comments=cnf.comments)
        cnf2.rebase(slice_by_vars)

        return cnf2

    # ------------------------------------------------------------------------------------------- #
    # Installable #
    # -----------------------------------------------------------------------------
    # #

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds FeatJar after all dependencies have been procured
        """

        src_dir = path.join(CONFIG.CACHE_DIR, STUB)

        # with open(path.join(src_dir, "scripts", "repo.txt"), "w+") as fp:
        #     fp.write("https://github.com/FeatureIDE/FeatJAR-base.git base\n")
        #     fp.write("https://github.com/FeatureIDE/FeatJAR-formula.git formula\n")
        #     fp.write(
        #         "https://github.com/FeatureIDE/FeatJAR-formula-analysis-sat4j.git formula-analysis-sat4j\n"
        #     )

        # via_subprocess("./scripts/clone.bat", cwd=src_dir, shell=True)

        # # Workaround for https://github.com/FeatureIDE/FeatJAR-formula-analysis-sat4j/issues/5#issuecomment-2981753979
        # # via_subprocess("git checkout aae98ff13f08598668851f85e0dabaf751a23b34", cwd = path.join(src_dir, "base"))
        # # via_subprocess("git checkout 9ce6df5c1dd28afc9296b19cd291b7539fa46450", cwd = path.join(src_dir, "formula"))
        # # via_subprocess("git checkout ", cwd = path.join(src_dir, "base"))
        # via_subprocess(
        #     "git checkout 0fbf80a02705f04cc2c69fc344f891c2782d82aa",
        #     cwd=path.join(src_dir, "formula"),
        # )
        # via_subprocess(
        #     "git checkout 8e4aacf0911b340e5b5e90da4f74ce191dc3b0ca",
        #     cwd=path.join(src_dir, "formula-analysis-sat4j"),
        # )

        via_subprocess("./gradlew assemble", cwd=path.join(src_dir, "all"))

        makedirs(path.join(CONFIG.TOOLS_DIR, STUB), exist_ok=True)

        jars = glob.glob(path.join(src_dir, "all", "build", "libs", "*-all.jar"))

        for jar in jars:
            shutil.copy2(jar, path.join(CONFIG.TOOLS_DIR, STUB, f"{STUB}.jar"))

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if FeatJar is installed correctly"""

        return path.exists(EXE_PATH)

    @classmethod
    def get_installable(cls):
        """Generates the install package for Spur"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ToolDependency("java"),
                GitDependency(
                    target=f"{STUB}",
                    url=URL_YASA,
                    commit=None,  # "3a3c17ebdac1a2f1712f0193aeb58d0f7381a488"
                ),
            ],
            cls=cls,
        )
