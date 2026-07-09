import re
import shutil
from os import makedirs, path
from tempfile import TemporaryDirectory

from formats import ensure_CNF2File

import config as CONFIG
from util.plugins import (
    GitDependency,
    Install,
    Installable,
    ToolDependency,
)
from util.runner import via_subprocess

STUB = "divkc"
EXE_NAME = "divkc"
URL = "https://github.com/serval-uni-lu/divkc"


class DivKC(Installable):

    @classmethod
    @ensure_CNF2File
    def compile(cls, file_in, folder_out):

        path_src = path.join(CONFIG.CACHE_DIR, STUB)

        exe_splitter = path.join(path_src, "splitter", "build", "splitter")
        exe_projection = path.join(path_src, "projection", "build", "projection")
        exe_d4 = path.join(path_src, "D4", "d4", "d4")

        if not path.exists(folder_out):
            makedirs(folder_out)

        with TemporaryDirectory(delete=True) as tmpdir:

            file_in = path.abspath(file_in)
            file_proj = path.join(tmpdir, f"{path.basename(file_in)}.proj")

            with open(file_proj, "w+") as fp_proj, open(file_in) as fp_in:
                call_split = via_subprocess(
                    f"{exe_splitter} --cnf {file_in} --nb 4", cwd=tmpdir, stdout=fp_proj
                )
                raw_in = fp_in.read()
                fp_proj.write(raw_in)

            # project
            call_proj = via_subprocess(
                f"{exe_projection} --cnf {file_proj}", cwd=tmpdir
            )

            # compile with D4
            call_kc1 = via_subprocess(
                f"{exe_d4} -dDNNF {file_proj}.p -out={path.basename(file_in)}.pnnf",
                cwd=tmpdir,
            )
            call_kc2 = via_subprocess(
                f"{exe_d4} -dDNNF {file_proj}.pup -out={path.basename(file_in)}.unnf",
                cwd=tmpdir,
            )

            shutil.copy2(file_in, folder_out)
            shutil.copy2(
                path.join(tmpdir, f"{path.basename(file_in)}.proj.log"), folder_out
            )
            shutil.copy2(
                path.join(tmpdir, f"{path.basename(file_in)}.pnnf"), folder_out
            )
            shutil.copy2(
                path.join(tmpdir, f"{path.basename(file_in)}.unnf"), folder_out
            )

    @classmethod
    @ensure_CNF2File
    def count_approximate(cls, file_in):

        path_src = path.join(CONFIG.CACHE_DIR, STUB)
        exe_appmc = path.join(path_src, "cppddnnf", "build", "appmc")

        with TemporaryDirectory() as tmpdir:

            cls.compile(file_in, tmpdir)

            call = via_subprocess(
                f"{exe_appmc} --cnf {path.join(tmpdir, path.basename(file_in))}",
                cwd=tmpdir,
            )

            return int(float(re.split(r",?[\n\s]+", call.stdout.strip())[2]))

    @classmethod
    def _sample_uniform(cls, file_in, file_out, size, **kwargs):

        path_src = path.join(CONFIG.CACHE_DIR, STUB)
        exe_appmc = path.join(path_src, "cppddnnf", "build", "sampler")

        with TemporaryDirectory() as tmpdir:

            cls.compile(file_in, tmpdir)

            call = via_subprocess(
                f"{exe_appmc} --cnf {path.join(tmpdir, path.basename(file_in))} --nb {size} --k {100}",
                cwd=tmpdir,
            )

            with open(file_out, "w+") as fp:
                fp.write(call.stdout)

        return call

    @classmethod
    def format_uniform(cls, _file_in, file_out):

        with open(file_out, "r", encoding="utf-8") as fp:
            raw = fp.readlines()

        confs = []
        for line in raw:
            line = line.strip()
            if not line.endswith("0"):
                continue

            config = re.split(r"\s+", line)
            config = {int(x) for x in config if int(x) != 0}
            confs.append(config)

        return confs

    @classmethod
    def build(cls):

        path_src = path.join(CONFIG.CACHE_DIR, STUB)
        path_cppddnnf = path.join(path_src, "cppddnnf")
        path_splitter = path.join(path_src, "splitter")
        path_projection = path.join(path_src, "projection")
        path_d4 = path.join(path_src, "D4", "d4")

        # build cppddnnf
        via_subprocess("g++ gen.cpp -o gen", cwd=path_cppddnnf)
        via_subprocess("./gen", cwd=path_cppddnnf)
        via_subprocess("ninja clean", cwd=path_cppddnnf)
        via_subprocess("ninja", cwd=path_cppddnnf)

        # build splitter
        via_subprocess("g++ gen.cpp -o gen", cwd=path_splitter)
        via_subprocess("./gen", cwd=path_splitter)
        via_subprocess("ninja clean", cwd=path_splitter)
        via_subprocess("ninja", cwd=path_splitter)

        # build projection
        via_subprocess("g++ gen.cpp -o gen", cwd=path_projection)
        via_subprocess("./gen", cwd=path_projection)
        via_subprocess("ninja clean", cwd=path_projection)
        via_subprocess("ninja", cwd=path_projection)

        # build D4
        via_subprocess("make clean", cwd=path_d4)
        via_subprocess("make -j", cwd=path_d4)

    @classmethod
    def check(cls):

        path_src = path.join(CONFIG.CACHE_DIR, STUB)

        exe_splitter = path.join(path_src, "splitter", "build", "splitter")
        exe_projection = path.join(path_src, "projection", "build", "projection")
        exe_d4 = path.join(path_src, "D4", "d4", "d4")

        if path.exists(exe_splitter):
            call = via_subprocess(exe_splitter, rc=None)

            if call.returncode == 1 and not call.stderr.startswith(
                "ERROR: cnf option not set"
            ):
                return False
        else:
            return False

        if path.exists(exe_projection):
            call = via_subprocess(exe_projection, rc=None)

            if not call.stderr.startswith("ERROR: cnf option not set"):
                return False
        else:
            return False

        if path.exists(exe_d4):
            call = via_subprocess(exe_d4, rc=None)

            if not call.stdout.strip().startswith("c"):
                return False
        else:
            return False

        return True

    @classmethod
    def get_installable(cls):
        return Install(
            stub=STUB,
            full=STUB,
            dependencies=[
                ToolDependency("g++"),
                ToolDependency("ninja"),
                GitDependency(target="divkc", url=URL, commit=None, recursive=True),
            ],
            cls=cls,
        )
