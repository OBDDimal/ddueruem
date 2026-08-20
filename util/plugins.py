import gzip
import os
import re
import shutil
import subprocess
import tarfile
import zipfile
from abc import ABC, abstractmethod
from os import path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import config as CONFIG
from util.cli import cli, formatting
from util.cli.formatting import bad, h
from util.io import hash_file
from util.runner import via_subprocess


class Extendable:

    _default = None
    _libraries = None
    _synonyms = None

    @classmethod
    def register_plugin(cls, plugin, *synonyms, set_default=False):

        # Ensure that the plug-in is a subclass

        if not issubclass(plugin, cls):
            raise TypeError(
                f"{plugin.__name__} needs to inherit from {cls.__name__} to be registrable as plug-in."
            )

        name = plugin.__name__.lower()

        if cls._libraries is None:
            cls._libraries = dict()

        if cls._synonyms is None:
            cls._synonyms = dict()

        cls._libraries[name] = plugin

        for syn in synonyms:
            cls._synonyms[syn] = plugin

        if set_default:
            if cls._default is not None:
                raise ValueError(
                    f"{cls._default} has already been set as default for {cls.__name__}, cannot set to {name}."
                )

            cls._default = name

        cls.on_plugin_registered(plugin)

    @classmethod
    def get_default(cls):
        return cls._default

    @classmethod
    def get_plugin(cls, stub):
        return cls._libraries.get(stub.lower(), cls._synonyms.get(stub.lower()))

    @classmethod
    def get_plugin_stubs(cls):
        return sorted([f"{x}" for x, y in set(cls._libraries.items()).union(cls._synonyms.items())])

    @classmethod
    def get_plugins(cls, check_health=False):
        return [y for x, y in cls._libraries.items() if not check_health or y.check()]

    @classmethod
    def get_plugins_dict(cls, check_health=False):

        return {
            x: y
            for x, y in set(cls._libraries.items()).union(cls._synonyms.items())
            if not check_health or y.check()
        }

    @classmethod
    def on_plugin_registered(cls, plugin):
        pass

    @classmethod
    def description(cls) -> str:
        return "Hello world!"


class Executable:

    @classmethod
    @abstractmethod
    def plain(cls, args):
        raise NotImplementedError()


class Installable(ABC):
    """A class that inherits from Installable can be installed from third-party by request"""

    _installables = dict()

    @classmethod
    def register(cls, stub, **kwargs):

        if (hit := cls._installables.get(stub)) is not None:
            raise ValueError(
                f"Cannot register {cls.__name__} under {stub} as it is already used by {hit}"
            )

        cls._installables[stub] = cls

    @classmethod
    def check(cls):
        raise NotImplementedError()

    @classmethod
    def get_installable(cls):
        raise NotImplementedError()

    @classmethod
    def install(cls):
        if not cls.check():
            pkg = cls.get_installable()
            pkg.install()


class Install(ABC):

    def __init__(
        self, stub, full=None, dependencies=None, build=None, check=None, cls=None
    ):

        self.stub = stub
        self.full = full if full else stub
        self.dependencies = dependencies

        if all([x is None for x in [build, check, cls]]):
            raise ValueError("Either build and check or cls need to be specified.")

        self.build = build if build is not None else cls.build
        self.check = check if check is not None else cls.check
        self.cls = cls

    def install(self):

        cli.say(formatting.bold("Installing"), h(self.full))

        if self.check and self.check():
            cli.say(f"{h(self.full)} is already installed, skipping")
            return True

        cli.subsay(formatting.bold("Acquiring dependencies"))

        for dep in self.dependencies:
            status = dep.get()

            if status:
                cli.subsay(formatting.check(), dep)
            else:
                cli.subsay(bad("\u274c"), dep)
                return False

        status = self.check() if self.check else True

        if self.build:
            cli.subsay(formatting.bold("Building..."))
            status = self.build()

        return status and self.check()


class Dependency(ABC):

    def __init__(self, target):
        self.target = target

    def __str__(self):
        return self.target

    @abstractmethod
    def verify():
        pass

    @abstractmethod
    def get():
        pass


class LibraryDependency(Dependency):

    def verify(self):

        with open("/etc/ld.so.cache", "r", errors="ignore") as cachefile:
            content = cachefile.read()

        return self.target in content

    def __str__(self):
        return f"{formatting.h(self.target)} is available"

    def get(self):

        if self.verify():
            return True

        cli.warn(
            f"Shared library dependency {h(self.target)} not found on your system, exiting."
        )
        return False


class ToolDependency(Dependency):

    def verify(self):

        try:
            cmd = re.split(r"\s", f"which {self.target}")
            call = subprocess.run(cmd, capture_output=True)

            return call.returncode == 0
        except FileNotFoundError as fnfe:
            print('Default tool "which" not found in path, is it installed?')
            print(fnfe)
            exit(1)

    def __str__(self):
        return f"{formatting.h(self.target)} is available"

    def get(self):

        if self.verify():
            return True

        cli.warn(
            f"Build dependency {h(self.target)} not found on your system, exiting."
        )


class DockerDependency(Dependency):
    def __init__(self, target, tag, *args, **kwargs):
        super().__init__(target, *args, **kwargs)

        self.tag = tag

    def verify(self):
        call = via_subprocess(f"docker images -q {self.target}:{self.tag}")

        return call.stdout.strip() != ""

    def __str__(self):
        return f"{formatting.h(self.target)} (Docker) pulled"

    def get(self):

        if self.verify():
            return True

        call = via_subprocess(f"docker pull {self.target}:{self.tag}")

        return not call.stdout.strip().endswith("denied")


class HttpDependency(Dependency):

    def __init__(self, file, url, md5=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = path.join(CONFIG.CACHE_DIR, self.target)
        self.file = path.join(CONFIG.CACHE_DIR, file)
        self.url = url
        self.md5 = md5

    def __str__(self):
        return f"{formatting.h(self.url)} downloaded (to {self.target})"

    def verify(self):
        return path.exists(self.target)

    def get(self):

        if self.verify():
            return True

        if not path.exists(self.file) or (
            self.md5 and self.md5 != hash_file(self.file)
        ):

            if path.exists(self.file):
                cli.subsay(f"Could not verify md5 checksum for {h(self.file)}")

            try:
                with urlopen(self.url) as req:
                    if req.status == 200:
                        with open(self.file, "wb") as file:
                            file.write(req.read())
                    else:
                        cli.warn(
                            f"Downloading {h(self.url)} failed with status code {h(req.status)}."
                        )
                        return False
            except (HTTPError, URLError) as e:
                cli.warn(f"Downloading {h(self.url)} failed with error {h(e)}.")
                return False

        if self.md5 and self.md5 != hash_file(self.file):
            return False

        return True


class ArchiveDependency(Dependency):

    def __init__(self, archive, url, md5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = path.join(CONFIG.CACHE_DIR, self.target)
        self.archive = path.join(CONFIG.CACHE_DIR, archive)
        self.url = url
        self.md5 = md5

    def __str__(self):
        return f"{formatting.h(self.url)} downloaded and extracted (to {self.target})"

    def verify(self):
        return path.exists(self.target)

    def get(self):

        if self.verify():
            return True

        if not path.exists(self.archive) or (
            self.md5 and self.md5 != hash_file(self.archive)
        ):

            if path.exists(self.archive):
                cli.subsay(f"Could not verify md5 checksum for {h(self.archive)}")

            try:
                with urlopen(self.url) as req:
                    if req.status == 200:
                        with open(self.archive, "wb") as file:
                            file.write(req.read())
                    else:
                        cli.warn(
                            f"Downloading {h(self.url)} failed with status code {h(req.status)}."
                        )
                        return False

            except (HTTPError, URLError) as e:
                cli.warn(f"Downloading {h(self.url)} failed with error {h(e)}.")
                return False

        if self.md5 and self.md5 != hash_file(self.archive):
            return False

        status = self.extract()

        return status

    def extract(self):
        if tarfile.is_tarfile(self.archive):
            with tarfile.open(self.archive) as archive:
                if hasattr(tarfile, "data_filter"):
                    archive.extractall(path=self.target, filter="data")
                else:
                    print("FIXME in the future")
                    archive.extractall(path=self.target)
        elif zipfile.is_zipfile(self.archive):
            with zipfile.ZipFile(self.archive, "r") as zip_fp:
                zip_fp.extractall(path=self.target)
        elif self.archive.endswith("gz"):
            with gzip.open(self.archive, "rb") as fp_in:
                with open(self.target, "wb") as fp_out:
                    shutil.copyfileobj(fp_in, fp_out)
        else:
            cli.warn("Archive is not .zip | .gz | .tar | .tar.gz - unsupported")
            return False

        return True


class GitDependency(Dependency):
    def __init__(self, url, commit=None, recursive=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = path.join(CONFIG.CACHE_DIR, self.target)
        self.url = url
        self.commit = commit
        self.recursive = recursive

    def __str__(self):
        return f"{formatting.h(self.url)} pulled (to {self.target})"

    def get(self):

        if self.verify():
            return True

        if not path.exists(self.target) or not os.listdir(self.target):
            via_subprocess(
                f"git clone{' --recursive' if self.recursive else ''} {self.url} {self.target}"
            )

            if self.commit is not None:
                via_subprocess(f"git checkout {self.commit}", cwd=self.target)

            return True

        return True

    def verify(self):
        return path.exists(self.target) and os.listdir(self.target)


class VenvDependency(Dependency):
    def __init__(self, parent, *args, install=None, from_requirements=False, **kwargs):
        super().__init__(*args, target="Setting up Virtual Environment", **kwargs)

        self.parent = path.join(CONFIG.CACHE_DIR, parent)

        self.pip_path = path.abspath(path.join(self.parent, ".venv", "bin", "pip"))

        self.install = install
        self.fron_requirements = from_requirements

    def get(self):

        if self.verify():
            return True

        via_subprocess("python -m venv .venv", cwd=self.parent)

        if self.install:
            for pkg in self.install:
                via_subprocess(f"{self.pip_path} install {pkg}")

        if self.fron_requirements:
            call = via_subprocess(
                f'{self.pip_path} install -r {path.join(self.parent, "requirements.txt")}'
            )
            print(call.stdout)

        return True

    def verify(self):
        if not path.exists(self.pip_path):
            return False

        out = via_subprocess(f"{self.pip_path} freeze").stdout

        if self.install:
            for pkg in self.install:
                if pkg not in out:
                    return False

        return True
