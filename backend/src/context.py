from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class PipelineContext:
    """
    Contexto de ejecución del pipeline.
    Reemplaza el uso de argumentos de línea de comandos y variables de entorno dispersas.
    """
    stage_id: str
    job_id: Optional[str] = None
    temp_root: Optional[Path] = None

    # Puedes agregar más campos si es necesario, como configuración global,
    # logger configurado, etc.

    def get_stage_dir(self, stage_id: Optional[str] = None) -> Path:
        """
        Devuelve el directorio temporal para un stage.
        Si stage_id es None, usa el del contexto actual.
        """
        target_id = stage_id if stage_id else self.stage_id
        if self.temp_root:
            return self.temp_root / target_id

        # Fallback si no hay temp_root definido (comportamiento legacy o local)
        # Esto debería coincidir con la lógica de _get_job_temp_root en stage.py
        # o get_temp_dir en analysis_utils.py si se quiere mantener compatibilidad total,
        # pero idealmente el temp_root debe venir seteado.
        raise ValueError("temp_root no está definido en PipelineContext")
