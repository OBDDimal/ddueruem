import re
import shutil
from os import chmod, makedirs, path
from tempfile import NamedTemporaryFile

from formats import CNF

import config as CONFIG
from util.plugins import ArchiveDependency, Executable, Install, Installable
from util.runner import via_subprocess

STUB = "ddnnife"
FULL = "DDNNIFE"

EXE_NAME = "ddnnife"
URL_D4 = (
    "https://github.com/SoftVarE-Group/d4v2/releases/download/2.3.2/d4-x86_64-linux.zip"
)
URL_DDNNIFE = "https://github.com/SoftVarE-Group/d-dnnf-reasoner/releases/download/0.10.0/ddnnife-x86_64-linux.zip"

REP_COUNT = re.compile(r"(?P<count>\d+)")
REP_COUNT_FEATURES = re.compile(r"(?P<feature>\d+),(?P<count>\d+)")


class DDNNIFE_base(Installable, Executable):

    @classmethod
    def plain(cls, args):
        cls.run_ddnnife(cmd=args, rc=None, debug=True)

    @classmethod
    def run_d4(cls, file_in, file_out, **kwargs):

        exe = path.join(CONFIG.TOOLS_DIR, STUB, "d4")
        lib = path.abspath(path.join(CONFIG.CACHE_DIR, "d4", "lib"))

        return via_subprocess(
            f"{exe} --input {file_in} --method ddnnf-compiler --dump-ddnnf {file_out}",
            env=dict(LD_LIBRARY_PATH=lib),
            **kwargs,
        )

    @classmethod
    def run_ddnnife(
        cls,
        file_in=None,
        file_out=None,
        file_nnf=None,
        cmd=None,
        implicit_ddnnf_compilation=True,
        **kwargs,
    ):
        """Executes ddnnife"""

        with NamedTemporaryFile(suffix=".nnf") as ntf:
            if file_in and not file_in.endswith(".nnf"):
                call1 = cls.cnf2ddnnf(file_in, file_nnf=ntf.name, **kwargs)
                file_tmp = ntf.name
            else:
                call1 = None
                file_tmp = file_in

            exe = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)
            call_cmd = (
                f"{exe}"
                f'{f" --input {file_tmp}" if file_tmp is not None else ""}'
                f'{f" --output {file_out}" if file_out is not None else ""}'
                f'{f" --save-ddnnf {file_nnf}" if file_nnf is not None else ""}'
                f'{f" {cmd}" if cmd is not None else ""}'
            )

            call = via_subprocess(call_cmd, **kwargs)

        if call1:
            call.times["time_kc"] = call1.times["time"]

        return call

    @classmethod
    def cnf2ddnnf(cls, file_in, file_nnf=None, **kwargs):
        return cls.run_d4(file_in, file_nnf, **kwargs)

    # Uniform Sampling

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size, seed=None, **kwargs):
        return cls.run_ddnnife(
            file_in,
            file_out,
            cmd=f"urs -n {size}{f' --seed {seed}' if seed is not None else ''}",
            **kwargs,
        )

    @classmethod
    def format_uniform(cls, _file_in, file_out):

        with open(file_out, "r", encoding="utf-8") as fp:
            raw = fp.readlines()

        confs = []
        for line in raw:
            line = line.strip()

            config = re.split(r"\s+", line)
            config = {int(x) for x in config if int(x) > 0}
            confs.append(config)

        return confs

    # t-wise Sampling

    @classmethod
    def _sample_twise(cls, file_in, file_out, t=2, **kwargs):
        # Workaround for https://github.com/SoftVarE-Group/d-dnnf-reasoner/issues/87

        cnf = CNF(from_file=file_in)
        print(cnf.nv)
        return cls.run_ddnnife(
            file_in, file_out, cmd=f"--total-features {cnf.nv} t-wise -t {t}", **kwargs
        )
        # return cls.run_ddnnife(file_in, file_out, cmd = f"t-wise -t {t}", **kwargs)

    @classmethod
    def format_twise(cls, *args, **kwargs):
        return cls.format_uniform(*args, **kwargs)

    # Counting  FIXME: Wrap in reworked result type

    @classmethod
    def _count(cls, file_in, **kwargs):
        call = cls.run_ddnnife(file_in, cmd="count", **kwargs)

        out = call.stdout

        if m := REP_COUNT.match(out):
            return int(m["count"])

    @classmethod
    def _cardinalities(cls, file_in, **kwargs):

        with NamedTemporaryFile() as ntf:
            cls.run_ddnnife(file_in, ntf.name, cmd="count-features", **kwargs)

            with open(ntf.name, "r", encoding="utf-8") as fp:
                raw = fp.readlines()

        counts = {}

        for line in raw:
            line = line.strip()

            if m := REP_COUNT_FEATURES.match(line):
                counts[int(m["feature"])] = int(m["count"])

        return counts

    # Atomic Sets

    @classmethod
    def compute_atomic_sets(cls, file_in, **kwargs):
        with NamedTemporaryFile() as ntf:
            cls.run_ddnnife(file_in, ntf.name, cmd="atomic-sets", **kwargs)

            with open(ntf.name, "r", encoding="utf-8") as fp:
                raw = fp.readlines()

            sets = []

            for line in raw:
                line = line.strip()

                ats = re.split(r"\s+", line)
                ats = {int(x) for x in ats}
                sets.append(ats)

        return sets

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds ddnnife after all dependencies have been procured
        """

        src_dir = path.join(CONFIG.CACHE_DIR, STUB, "bin")
        src_dir_d4 = path.join(CONFIG.CACHE_DIR, "d4", "bin")
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        makedirs(exe_dir, exist_ok=True)

        shutil.copy2(path.join(src_dir, EXE_NAME), exe_dir)
        shutil.copy2(path.join(src_dir_d4, "d4"), exe_dir)
        chmod(path.join(exe_dir, "d4"), 0o0777)
        chmod(path.join(exe_dir, EXE_NAME), 0o0777)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if ddnnife is installed correctly"""

        exe = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)

        if not path.exists(exe):
            return False

        call = via_subprocess(exe, rc=2)

        return call.stderr.startswith("Usage: ddnnife [OPTIONS] [COMMAND]")

    @classmethod
    def get_installable(cls):
        """Generates the install package for DDNNIFE"""

        return Install(
            stub=STUB,
            full=FULL,
            dependencies=[
                ArchiveDependency(
                    target=STUB,
                    archive="ddnnife.zip",
                    url=URL_DDNNIFE,
                    md5="e230e4cb5ca775b6030043360f6714a8",
                ),
                ArchiveDependency(
                    target="d4",
                    archive="d4.zip",
                    url=URL_D4,
                    md5="ecfcde093be7f26382039dafeba6af3d",
                ),
            ],
            cls=cls,
        )
