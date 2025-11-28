from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Any, Sequence, Callable


def iter_csv_rows(csv_path: Path) -> Iterator[dict[str, str]]:
    """
    Itera sobre un CSV devolviendo cada fila como dict[str, str].

    Lanza FileNotFoundError si el fichero no existe.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Tipo explícito para ayudar al tipado.
            yield dict(row)  # type: ignore[arg-type]


def parse_float(value: str | None, default: float = 0.0) -> float:
    """
    parse_float(" 1.23 ") -> 1.23
    parse_float("") -> default
    parse_float("no es número") -> default
    """
    if value is None:
        return default

    v = value.strip()
    if not v:
        return default

    try:
        return float(v)
    except ValueError:
        return default


def parse_bool(value: str | None, default: bool = False) -> bool:
    """
    parse_bool("1"), parse_bool("true"), parse_bool("YES"), parse_bool("sí") -> True
    parse_bool("0"), parse_bool("false"), parse_bool("no") -> False
    parse_bool("", None) -> default
    """
    if value is None:
        return default

    v = value.strip().lower()
    if not v:
        return default

    if v in {"1", "true", "t", "yes", "y", "si", "sí"}:
        return True
    if v in {"0", "false", "f", "no", "n"}:
        return False

    # Último intento:  int("2") -> True, int("0") -> False
    try:
        return bool(int(v))
    except ValueError:
        return default


def write_rows(
    csv_path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Any],
    row_to_dict: Callable[[Any], Mapping[str, Any]],
) -> None:
    """
    Helper genérico para escribir un CSV a partir de una colección de objetos.

    Cada fila se construye llamando a `row_to_dict(row)` y se escribe como DictWriter.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row_to_dict(row))
