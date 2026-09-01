import json
import shutil
from datetime import datetime
from pathlib import Path

from models.hand_state import HandState
from models.raw_observation import RawTableObservation


# Raíz real de agente_poker/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

RUNS_DIR = PROJECT_ROOT / "runs"


def save_run(
    image_path: str,
    provider: str,
    model: str,
    elapsed_seconds: float,
    observation: RawTableObservation,
    hand_state: HandState,
    question: str,
) -> Path:

    # --------------------------------------------------
    # CREAR DIRECTORIO RUNS
    # --------------------------------------------------

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    run_dir = RUNS_DIR / timestamp

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    # --------------------------------------------------
    # RESOLVER IMAGEN ORIGINAL
    # --------------------------------------------------

    source_image = Path(image_path)

    if not source_image.is_absolute():
        source_image = (
            PROJECT_ROOT / source_image
        ).resolve()

    if not source_image.exists():
        raise FileNotFoundError(
            f"No existe la imagen que se intenta guardar: "
            f"{source_image}"
        )

    # --------------------------------------------------
    # COPIAR IMAGEN
    # --------------------------------------------------

    extension = (
        source_image.suffix.lower()
        or ".png"
    )

    destination_image = (
        run_dir / f"image{extension}"
    )

    shutil.copy2(
        source_image,
        destination_image,
    )

    # --------------------------------------------------
    # METADATA
    # --------------------------------------------------

    metadata = {
        "timestamp": timestamp,
        "source_image": str(source_image),
        "provider": provider,
        "model": model,
        "elapsed_seconds": round(
            elapsed_seconds,
            3,
        ),
        "question": question,
    }

    (
        run_dir / "metadata.json"
    ).write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # RAW OBSERVATION
    # --------------------------------------------------

    (
        run_dir / "raw_observation.json"
    ).write_text(
        observation.model_dump_json(
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # HAND STATE
    # --------------------------------------------------

    (
        run_dir / "hand_state.json"
    ).write_text(
        hand_state.model_dump_json(
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # PREGUNTA
    # --------------------------------------------------

    (
        run_dir / "question.txt"
    ).write_text(
        question,
        encoding="utf-8",
    )

    return run_dir