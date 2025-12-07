from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import numpy as np
import tempfile
import shutil

@dataclass
class PipelineContext:
    """
    Contexto de ejecución del pipeline.
    Reemplaza el uso de argumentos de línea de comandos y variables de entorno dispersas.
    Mantiene el estado del audio en memoria y resultados de análisis.
    """
    stage_id: str
    job_id: Optional[str] = None

    # Audio Data Storage (In-Memory)
    audio_stems: Dict[str, np.ndarray] = field(default_factory=dict)
    audio_mixdown: Optional[np.ndarray] = None
    sample_rate: int = 44100
    metadata: Dict[str, Any] = field(default_factory=dict)

    # In-memory storage for analysis results
    analysis_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # In-memory storage for stage timings
    pipeline_timings: List[Dict[str, Any]] = field(default_factory=list)

    # Final Report Data (S11)
    report: Optional[Dict[str, Any]] = None

    # Generated Artifacts (filename -> bytes)
    generated_artifacts: Dict[str, bytes] = field(default_factory=dict)

    _transient_temp: Optional[Path] = None

    def get_stage_dir(self, stage_id: Optional[str] = None) -> Path:
        """
        Returns a transient temporary directory for legacy file operations (e.g. plotting).
        """
        if self._transient_temp is None:
             self._transient_temp = Path(tempfile.mkdtemp(prefix=f"mix_job_{self.job_id}_"))

        target = self._transient_temp / (stage_id or self.stage_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def cleanup_transient(self):
        if self._transient_temp and self._transient_temp.exists():
            shutil.rmtree(self._transient_temp, ignore_errors=True)
            self._transient_temp = None
