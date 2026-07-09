from formats import CNF


def args_triage(*args):

    if len(args) == 1:
        cnf = args[0]

        if not isinstance(cnf, CNF):
            cnf = CNF(from_file=cnf)

        clauses = cnf.clauses
        nv = cnf.nv
    elif len(args) == 2:
        clauses, nv = args
        cnf = CNF(from_clauses=clauses, nv=nv)
    else:
        raise ValueError(
            f"SVO heuristics accept either CNF, DIMACS file, or clauses, nv, given: {args}"
        )

    return cnf, clauses, nv
