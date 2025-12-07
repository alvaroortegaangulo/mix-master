from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict
import numpy as np

@dataclass
class PipelineContext:
    """
    Contexto de ejecución del pipeline.
    Reemplaza el uso de argumentos de línea de comandos y variables de entorno dispersas.
    Ahora también mantiene el estado del audio en memoria para evitar I/O de disco.
    """
    stage_id: str
    job_id: Optional[str] = None
    temp_root: Optional[Path] = None

    # Audio Data Storage (In-Memory)
    # Stems: { "stem_name.wav": np.ndarray (shape=(samples, channels), float32) }
    audio_stems: Dict[str, np.ndarray] = field(default_factory=dict)

    # Mixdown (Full Song): np.ndarray (shape=(samples, channels), float32)
    audio_mixdown: Optional[np.ndarray] = None

    # Global Sample Rate (assumed constant for the session)
    sample_rate: int = 44100

    # Metadata persistence (replacing session_config.json, etc if needed,
    # though JSONs are small enough to keep on disk for now, but we can cache them here)
    metadata: Dict[str, any] = field(default_factory=dict)

    def get_stage_dir(self, stage_id: Optional[str] = None) -> Path:
        """
        Devuelve el directorio temporal para un stage.
        Si stage_id es None, usa el del contexto actual.
        """
        target_id = stage_id if stage_id else self.stage_id
        if self.temp_root:
            return self.temp_root / target_id

        # Fallback
        raise ValueError("temp_root no está definido en PipelineContext")
