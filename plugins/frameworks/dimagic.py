import os
import shutil
from os import makedirs, path
from tempfile import NamedTemporaryFile

from formats import CNF, ensure_CNF2File
from preprocessing import PMC

import config as CONFIG
from util.cli import cli
from util.plugins import (
    ArchiveDependency,
    Executable,
    GitDependency,
    Install,
    Installable,
    ToolDependency,
)
from util.runner import via_subprocess

STUB = "dimagic"
EXE_NAME = "dimagic"
URL = "https://zenodo.org/records/15583680/files/src.zip?download=1"


class Dimagic(Installable, Executable):

    @classmethod
    @ensure_CNF2File
    def run(cls, file_in, file_out=None, cmd=None, for_oxidd=False, timeout=None):

        exe_path = path.abspath(path.join(CONFIG.TOOLS_DIR, STUB))

        if cmd is None:
            cmd = "--help"

        with NamedTemporaryFile(suffix=".nnf" if for_oxidd else ".dimacs") as file:
            file_in = path.abspath(file_in)
            file_tmp = file.name

            call_cmd = f"{path.join(exe_path, STUB)} {cmd}  --var-kahypar-preset kahypar.ini --clause-kahypar-preset kahypar.ini {file_in} {file_tmp}"

            call = via_subprocess(
                call_cmd,
                cwd=exe_path,
                env={"LD_LIBRARY_PATH": exe_path, "PATH": exe_path},
                timeout=timeout,
            )

            if file_out:
                shutil.copy2(file_tmp, file_out)

            if not for_oxidd:
                return CNF.get_order_in_file(file_tmp)

        return call

    @classmethod
    def plain(cls, args):
        exe_path = path.abspath(path.join(CONFIG.TOOLS_DIR, STUB))
        via_subprocess(
            f"{path.join(exe_path, STUB)} {args}",
            env={"LD_LIBRARY_PATH": exe_path, "PATH": exe_path},
            debug=True,
            rc=None,
        )

    @classmethod
    def build(cls):

        cli.subsay("Installing pmc...")
        PMC.install()

        # build kahypar
        cli.subsay("Building kahypar...")
        source_path_kahypar = path.join(CONFIG.CACHE_DIR, "kahypar")
        build_path_kahypar = path.join(source_path_kahypar, "build")
        makedirs(build_path_kahypar, exist_ok=True)

        build_path_dimagic = path.join(CONFIG.CACHE_DIR, STUB)

        # Important: Disable Testing to save plenty of time
        via_subprocess(
            "cmake .. -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=RELEASE",
            cwd=build_path_kahypar,
        )
        via_subprocess("make", cwd=build_path_kahypar)

        shutil.copy2(
            path.join(build_path_kahypar, "lib", "libkahypar.so"), build_path_dimagic
        )
        shutil.copy2(
            path.join(CONFIG.CACHE_DIR, "kahypar", "include", "libkahypar.h"),
            build_path_dimagic,
        )

        cli.subsay("Installing dimagic...")
        via_subprocess(
            "cargo install --path dimagic --features kahypar",
            cwd=build_path_dimagic,
            env=os.environ
            | {
                "C_INCLUDE_PATH": f"{build_path_dimagic}",
                "LIBRARY_PATH": f"{build_path_dimagic}",
            },
        )

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB)
        makedirs(exe_path, exist_ok=True)

        shutil.copy2(path.join(build_path_dimagic, "target", "release", STUB), exe_path)
        shutil.copy2(path.join(build_path_dimagic, "kahypar.ini"), exe_path)
        shutil.copy2(path.join(build_path_dimagic, "libkahypar.so"), exe_path)
        shutil.copy2(
            path.join(
                CONFIG.CACHE_DIR, "mince", "Mince_Linux_v01", "MetaPlacerTest0.exeS"
            ),
            exe_path,
        )
        shutil.copy2(
            path.join(path.dirname(__file__), "res", "libstdc++-libc6.1-2.so.3"),
            exe_path,
        )

        os.symlink(
            path.join(CONFIG.TOOLS_DIR, "pmc", "pmc"),
            path.join(exe_path, "pmc"),
            target_is_directory=False,
        )

    @classmethod
    def check(cls):

        exe_path = path.join(CONFIG.TOOLS_DIR, STUB)

        if not path.exists(path.join(exe_path, STUB)):
            return False

        call = via_subprocess(
            f"{path.join(exe_path, STUB)} --help",
            env={"LD_LIBRARY_PATH": path.abspath(exe_path)},
            rc=None,
        )

        return call.stdout.startswith("Usage:")

    @classmethod
    def get_installable(cls):
        return Install(
            stub=STUB,
            full=STUB,
            dependencies=[
                ToolDependency("cargo"),
                GitDependency(
                    target="kahypar",
                    url="https://github.com/kahypar/kahypar",
                    commit=None,
                    recursive=True,
                ),
                ArchiveDependency(
                    target="mince",
                    archive="mince.tar.gz",
                    url="http://www.aloul.net/Tools/mince/Mince_Linux_v01.tar.gz",
                    md5="28d27eb3ee42168b9f6fad9c0a68d9f4",
                ),
                ArchiveDependency(
                    target="dimagic",
                    archive="dimagic.zip",
                    url=URL,
                    md5="ea6ad8eeddca636171e295ca635cedc1",
                ),
            ],
            cls=cls,
        )
