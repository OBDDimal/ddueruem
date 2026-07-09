"""Meta class for #SAT solvers"""

from abc import ABC, abstractmethod
from os import path
from tempfile import NamedTemporaryFile

from formats import CNF, ensure_CNF2File

from util.plugins import Extendable
from util.runner import with_timeout


class Counter(ABC, Extendable):
    """Meta class for #SAT solvers"""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __new__(cls, *args, counter=None, **kwargs):
        """
        Constructor that triages :counter:

        :type counter: None or str or Counter
        """

        # forward, if just called via super().__new__(cls)
        if cls != Counter:
            return super().__new__(cls)

        if counter is None:
            counter = cls.get_default()

            if counter is None:
                raise ValueError("No counter specified and no default counter set.")

        if isinstance(counter, str):
            counter = cls.get_plugin(counter)

            if counter is None:
                raise ValueError(f"Counter {counter} not available.")

        if not issubclass(counter, Counter):
            raise TypeError(f"{counter} must inherit from Counter")

        return counter(*args, **kwargs)

    @classmethod
    @ensure_CNF2File
    def count(cls, file_in, timeout=None):
        """meta function to compute #SAT"""

        # TODO: Result format for counting? Expose Timeout?

        return with_timeout(cls._count, path.abspath(file_in), timeout=timeout).returncode

    @classmethod
    def cardinalities(cls, arg, timeout=None):
        kwargs = {}
        if timeout is not None:
            kwargs["timeout"] = timeout

        if isinstance(arg, CNF):
            cnf = arg
            with NamedTemporaryFile(suffix=".dimacs") as file_temp:
                cnf.to_file(file_temp.name)

                return cls._cardinalities(file_temp.name, **kwargs)
        else:
            filename = arg
            return cls._cardinalities(path.abspath(filename), **kwargs)

    @classmethod
    @abstractmethod
    def _count(cls, file_in, **kwargs):
        pass

    @classmethod
    @abstractmethod
    def _cardinalities(cls, file_in, **kwargs):
        pass
