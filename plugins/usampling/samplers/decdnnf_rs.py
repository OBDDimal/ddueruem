import re
import shutil
from os import makedirs, path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from frameworks import D4

import config as CONFIG
from util.plugins import Executable, Install, Installable, ToolDependency
from util.runner import via_subprocess

from ..usampler import USampler

STUB = "decdnnf_rs"
EXE_NAME = "decdnnf_rs"

# Paper: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SAT.2026.38
# https://github.com/crillab/decdnnf_rs

class Decdnnf_rs(USampler, Installable, Executable):

    @classmethod
    def plain(cls, args):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, STUB)
        via_subprocess(f"{exe_path} {args}", debug=True, rc=None)

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size=1024, seed=None, **kwargs):
        """
        Computes a sample with decdnnf_rs via subprocess \
        - intended to be called with USampler.sample

        runs CNF -> d-dnnf compilation with D4
        """

        with NamedTemporaryFile(suffix=".nnf") as ntf:
            if file_in and not file_in.endswith(".nnf"):
                call1 = D4.cnf2ddnnf(file_in, file_nnf=ntf.name, **kwargs)
                file_tmp = ntf.name
            else:
                call1 = None
                file_tmp = file_in

            exe = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)
            call_cmd = (
                f"{exe} sampling"
                f'{f" --input {file_tmp}" if file_tmp is not None else ""}'
                f'{f" --seed {seed}" if seed is not None else ""}'
                f'{f" -l {size}" if size is not None else ""}'
            )

            call = via_subprocess(call_cmd, **kwargs)

        if call1:
            call.times["time_kc"] = call1.times["time"]

        sample_raw = call.stdout

        with open(file_out, "w+") as fp:
            fp.write(sample_raw)

        return call

    @classmethod
    def cleanup(cls, _file_in):
        pass

    @classmethod
    def format_uniform(cls, _file_in, file_out):
        """Parses the output of Spur into the common format"""

        with open(file_out, "r", encoding="utf-8") as fp:
            raw = fp.readlines()

        configs = []

        for line in raw:
            line = line.strip()
            if line.startswith("v"):
                config = re.split(r"\s+", line)[1:-1]
                config = [int(x) for x in config]
                config = {x for x in config if x > 0}
                configs.append(config)
        
        return configs


    @classmethod
    def build(cls):

        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)
        makedirs(exe_dir, exist_ok=True)

        with TemporaryDirectory() as workdir:

            via_subprocess(f"cargo install decdnnf_rs --root {workdir}")
            shutil.copy2(path.join(workdir, "bin", EXE_NAME), exe_dir)

    @classmethod
    def check(cls):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB, EXE_NAME)
        return path.exists(exe_path)

    @classmethod
    def get_installable(cls):
        return Install(
            stub="oxidd",
            full="OxiDD",
            dependencies=[
                ToolDependency("cargo"),
            ],
            cls=cls,
        )


USampler.register_plugin(Decdnnf_rs)
