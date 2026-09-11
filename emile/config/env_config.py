import os
from pathlib import Path

def get_data_dir() -> Path:
    env_dir = os.getenv("EMILE_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    
    # Fallback default -- resolu en absolu MAINTENANT (a l'import de ce
    # module, donc avant tout os.chdir() ulterieur, ex. emile/run_all.py qui
    # change de repertoire vers une sortie temporaire avant d'appeler
    # module.main() des moteurs). Un Path relatif non resolu casse silen-
    # cieusement des qu'un appelant change de cwd apres l'import : trouve
    # par audit (test_run_all.py::test_real_run_only_base_and_v4), pas une
    # supposition.
    default_dir = Path("data/processed").resolve()
    if default_dir.exists():
        return default_dir
        
    raise FileNotFoundError(
        "Data directory not found. Please set EMILE_DATA_DIR env var "
        "or ensure 'data/processed' exists at project root."
    )

DATA_DIR = get_data_dir()
