import os

# Ruta del directorio raíz que quieres analizar
ROOT_DIR = r"C:\mix-master"  # Cambia esto por la ruta que quieras


def print_tree(path: str, prefix: str = "") -> None:
    """
    Imprime recursivamente el árbol de directorios y ficheros
    a partir de 'path', usando 'prefix' para la indentación.
    """
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        print(prefix + "└── [PERMISO DENEGADO]")
        return
    except FileNotFoundError:
        print(prefix + f"[NO ENCONTRADO]: {path}")
        return

    total = len(entries)
    for index, entry in enumerate(entries):
        full_path = os.path.join(path, entry)
        is_last = index == (total - 1)

        connector = "└── " if is_last else "├── "
        print(prefix + connector + entry)

        if os.path.isdir(full_path):
            # Si es directorio, continuar recursivamente
            new_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(full_path, new_prefix)


if __name__ == "__main__":
    # Imprimir el nombre del directorio raíz
    print(ROOT_DIR)
    print_tree(ROOT_DIR)