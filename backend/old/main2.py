from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Importamos el pipeline “orquestador”
from src.pipeline import run_full_pipeline


def create_temp_root(base_dir: Path) -> Path:
    """
    Crea una carpeta temporal con timestamp, por ejemplo:
    /app/temp/temp_20.11.2025-22.50.04
    """
    timestamp = datetime.now().strftime("%d.%m.%Y-%H.%M.%S")
    temp_root = base_dir / "temp" / f"temp_{timestamp}"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def main() -> None:
    # Raíz del proyecto (la carpeta donde está main.py)
    project_root = Path(__file__).resolve().parent

    # Carpeta de entrada con los stems crudos
    media_dir = project_root / "media"

    # Carpeta temporal para este “run”
    temp_root = create_temp_root(project_root)

    # Ejecutar todo el pipeline
    result = run_full_pipeline(
        project_root=project_root,
        media_dir=media_dir,
        temp_root=temp_root,
    )

    # Pequeño resumen por consola
    print("\n=== Pipeline completado ===")
    print(f"Temp root:        {temp_root}")
    print(f"Full song final:  {result.full_song_path}")

    m = result.metrics
    print(f"Tempo:            {m.tempo_bpm:.2f} BPM (conf {m.tempo_confidence:.3f})")
    print(f"Tonalidad:        {m.key} {m.scale} (strength {m.key_strength:.3f})")
    print(f"RMS final:        {m.final_rms_dbfs:.2f} dBFS")
    print(f"Peak final:       {m.final_peak_dbfs:.2f} dBFS")
    print(
        f"Vocal shift (semi): min {m.vocal_shift_min:+.2f}, "
        f"max {m.vocal_shift_max:+.2f}, mean {m.vocal_shift_mean:+.2f}"
    )


if __name__ == "__main__":
    main()
