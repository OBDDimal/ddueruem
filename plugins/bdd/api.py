from abc import ABC, abstractmethod
from enum import IntEnum

from util.plugins import Extendable


class BDD_API(ABC, Extendable):

    class DVO(IntEnum):
        """ Meta Enum to register DVO heuristics in the wrapper\
            classes of inheriting BDD wrapper classes """

        @classmethod
        def get(cls, value):
            """Helper method to get enum values from both values and str representation"""
            if isinstance(value, int):
                return cls(value)

            return cls[value.upper()]

        @classmethod
        def default(cls):
            """The default DVO heuristic to use when no heuristic is specified"""
            return None

        def __str__(self):
            return self.name

    @abstractmethod
    def to_index(self, varid):
        """
        converts variable ids to the format used by the BDD library (e.g., 0-based or 1-based)
        """

    # -----------------------------------------------------------------------------
    # Constants and Primitives

    @abstractmethod
    def zero(self):
        """returns a BDD for `false`"""

    @abstractmethod
    def one(self):
        """returns a BDD for `true`"""

    @abstractmethod
    def ithvar(self, var):
        """returns a BDD for a decision for variable `var`"""

    @abstractmethod
    def nithvar(self, var):
        """return a BDD for an inverse decision for variable `var`"""

    # -----------------------------------------------------------------------------
    # Unary Operations

    @abstractmethod
    def not_(self, bdd):
        """returns a BDD for the negation of `bdd`"""

    # -----------------------------------------------------------------------------
    # Binary Operations

    @abstractmethod
    def and_(self):
        """computes the conjunction of two BDDs"""

    @abstractmethod
    def or_(self):
        """computes the disjunction of two BDDs"""

    @abstractmethod
    def intersect(self):
        """computes the intersecion of two BDDS"""

    # -----------------------------------------------------------------------------
    # Meta Operations

    @abstractmethod
    def ite(self, x, y, z):
        """computes the ternary operation if-then-else"""

    # -----------------------------------------------------------------------------
    # Variable Ordering

    @abstractmethod
    def get_order(self, bdd):
        """returns the current variable order in the BDD manager as list"""

    @abstractmethod
    def set_order(self, bdd):
        """sets the variable order for the BDD manager"""

    @abstractmethod
    def reorder(self):
        """runs DVO"""

    @abstractmethod
    def available_dvo_heuristics(self):
        """returns a list of available DVO heuristics"""

    @abstractmethod
    def enable_dvo(self, dvo):
        """enables DVO with heuristic `dvo`"""

    @abstractmethod
    def disable_dvo(self):
        """disables DVO in the manager"""

    # -----------------------------------------------------------------------------
    # Queries

    @abstractmethod
    def size(self, bdd):
        """returns the number of nodes in the BDD"""

    @abstractmethod
    def has_model(self, bdd):
        """return True if the BDD != False"""

    @abstractmethod
    def count_models(self, bdd, variable_support=None):
        """returns the number of valid variable assignments"""

    # -----------------------------------------------------------------------------
    # Import / Export

    @abstractmethod
    def import_(self, file):
        """imports a BDD from file"""

    @abstractmethod
    def export_(self, roots):
        """expors a BDD to file"""
