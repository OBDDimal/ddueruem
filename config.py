from os import path, makedirs

from pathlib import Path

# Fixme: Better ideas?
p = Path(__file__).resolve()

if path.exists(path.join(p, "ddueruem.jpg")):
    root = p
else:
    while not (p.parent / "ddueruem.jpg").exists():
        p = p.parent

    root = p.parent

WORKING_DIR = path.abspath(path.join(root, "_cache"))
CACHE_DIR = path.join(WORKING_DIR, "cache")
RESULTS_DIR = path.join(WORKING_DIR, "out")
TOOLS_DIR = path.join(WORKING_DIR, "tools")

makedirs(WORKING_DIR, exist_ok=True)
makedirs(CACHE_DIR, exist_ok=True)
makedirs(RESULTS_DIR, exist_ok=True)
makedirs(TOOLS_DIR, exist_ok=True)
