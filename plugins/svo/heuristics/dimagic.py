from frameworks import Dimagic

from svo import SVO, svo


class Mince(SVO):
    @classmethod
    def run(cls, *args, seed = None):

        cnf, _, _ = svo.args_triage(*args)

        return Dimagic.run(cnf, cmd=f"-c prev -v mince --threads 1 {f'--seed {seed}' if seed is not None else ''}".strip())


class ReMince(SVO):
    @classmethod
    def run(cls, *args, seed = None):

        cnf, _, _ = svo.args_triage(*args)

        return Dimagic.run(cnf, cmd=f"-c prev -v remince --threads 1 {f'--seed {seed}' if seed is not None else ''}".strip())


SVO.register_plugin(Mince)
SVO.register_plugin(ReMince)
