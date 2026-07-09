from os import path, makedirs

WORKING_DIR = path.abspath(path.join("_cache"))
CACHE_DIR = path.join(WORKING_DIR, "cache")
RESULTS_DIR = path.join(WORKING_DIR, "out")
TOOLS_DIR = path.join(WORKING_DIR, "tools")

makedirs(WORKING_DIR, exist_ok=True)
makedirs(CACHE_DIR, exist_ok=True)
makedirs(RESULTS_DIR, exist_ok=True)
makedirs(TOOLS_DIR, exist_ok=True)
