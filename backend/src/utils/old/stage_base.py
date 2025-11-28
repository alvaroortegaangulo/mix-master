from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, List, TypeVar

RowT = TypeVar("RowT")
ResultT = TypeVar("ResultT")


@dataclass
class BaseCorrectionStage(ABC, Generic[RowT, ResultT]):
    """
    Plantilla base reutilizable para etapas de corrección.

    Patrón:
      1) load_rows()  -> lista de filas del json de análisis.
      2) process_row  -> corrige un único archivo y devuelve un resultado.
      3) write_log    -> escribe el json de log a partir de todos los resultados.

    El método run() orquesta el flujo completo.
    """

    analysis_json_path: Path
    input_media_dir: Path
    output_media_dir: Path

    @abstractmethod
    def load_rows(self) -> List[RowT]:
        """Carga las filas del json de análisis."""
        raise NotImplementedError

    @abstractmethod
    def process_row(self, row: RowT) -> ResultT:
        """Aplica la corrección a un único elemento y devuelve un resultado."""
        raise NotImplementedError

    @abstractmethod
    def write_log(self, results: List[ResultT]) -> Path:
        """Escribe el log de corrección y devuelve la ruta al json generado."""
        raise NotImplementedError

    def process_all_rows(self) -> List[ResultT]:
        """Carga todas las filas y ejecuta process_row sobre cada una."""
        rows = self.load_rows()
        results: List[ResultT] = []
        for row in rows:
            results.append(self.process_row(row))
        return results

    def run(self) -> Path:
        """Ejecuta la etapa completa y devuelve la ruta al json de log."""
        results = self.process_all_rows()
        return self.write_log(results)
