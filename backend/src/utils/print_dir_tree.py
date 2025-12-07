# C:\git\1\mix-master\backend\src\utils\print_dir_tree.py

from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Hack de ruta para poder hacer "from utils.logger import logger"
THIS_DIR = Path(__file__).resolve().parent       # .../backend/src/utils
SRC_DIR = THIS_DIR.parent                        # .../backend/src

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger  # noqa: E402


# Directorio raíz cuyo árbol quieres imprimir (backend/)
ROOT_DIR = SRC_DIR.parent  # .../backend


def print_tree(path: Path, prefix: str = "") -> None:
    """
    Imprime recursivamente el árbol de directorios y ficheros
    a partir de 'path', usando 'prefix' para la indentación.
    """
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        logger.logger.info(prefix + "└── [PERMISO DENEGADO]")
        return
    except FileNotFoundError:
        logger.logger.info(prefix + f"[NO ENCONTRADO]: {path}")
        return

    total = len(entries)
    for index, entry in enumerate(entries):
        full_path = path / entry
        is_last = index == (total - 1)

        connector = "└── " if is_last else "├── "
        logger.logger.info(prefix + connector + entry)

        if full_path.is_dir():
            new_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(full_path, new_prefix)


if __name__ == "__main__":
    logger.logger.info(f"Árbol de: {ROOT_DIR}")
    print_tree(ROOT_DIR)
