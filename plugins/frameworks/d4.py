import shutil
from os import chmod, makedirs, path

import config as CONFIG
from util.plugins import ArchiveDependency, Executable, Install, Installable
from util.runner import via_subprocess

URL_D4 = (
    "https://github.com/SoftVarE-Group/d4v2/releases/download/2.3.2/d4-x86_64-linux.zip"
)

STUB = "d4"


class D4(Installable, Executable):

    @classmethod
    def plain(cls, args):

        exe = path.join(CONFIG.TOOLS_DIR, STUB, "d4")
        lib = path.abspath(path.join(CONFIG.CACHE_DIR, "d4", "lib"))

        via_subprocess(
            f"{exe} {args}",
            env=dict(LD_LIBRARY_PATH=lib),
            debug = True,
            rc = None
        )


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
    def cnf2ddnnf(cls, file_in, file_nnf=None, **kwargs):
        return cls.run_d4(file_in, file_nnf, **kwargs)

    @classmethod
    def build(cls):
        """
        Implements build from Installable, builds ddnnife after all dependencies have been procured
        """

        src_dir_d4 = path.join(CONFIG.CACHE_DIR, "d4", "bin")
        exe_dir = path.join(CONFIG.TOOLS_DIR, STUB)

        makedirs(exe_dir, exist_ok=True)

        shutil.copy2(path.join(src_dir_d4, "d4"), exe_dir)
        chmod(path.join(exe_dir, "d4"), 0o0777)

    @classmethod
    def check(cls):
        """Implements check from Installable, tests if ddnnife is installed correctly"""

        exe = path.join(CONFIG.TOOLS_DIR, STUB, "d4")
        lib = path.abspath(path.join(CONFIG.CACHE_DIR, "d4", "lib"))

        call = via_subprocess(
            f"{exe}",
            env=dict(LD_LIBRARY_PATH=lib),
            rc = 1
        )
        return call.stdout.startswith("Some parameters are missing")

    @classmethod
    def get_installable(cls):
        """Generates the install package for DDNNIFE"""

        return Install(
            stub=STUB,
            dependencies=[
                ArchiveDependency(
                    target="d4",
                    archive="d4.zip",
                    url=URL_D4,
                    md5="ecfcde093be7f26382039dafeba6af3d",
                ),
            ],
            cls=cls,
        )
