from frameworks import Dimagic

from svo import SVO, svo


class Mince(SVO):
    @classmethod
    def run(cls, *args):

        cnf, _, _ = svo.args_triage(*args)

        return Dimagic.run(cnf, cmd="-c mince -v mince")


class ReMince(SVO):
    @classmethod
    def run(cls, *args):

        cnf, _, _ = svo.args_triage(*args)

        return Dimagic.run(cnf, cmd="-c remince -v remince")


SVO.register_plugin(Mince)
SVO.register_plugin(ReMince)
