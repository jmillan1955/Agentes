import sys

from poker.normalizer import normalize_observation
from poker.question_builder import build_question
from storage.run_storage import save_run
from vision.hand_reader import HandReader


def validate_critical_data(
    observation,
) -> list[str]:

    errors = []

    heroes = [
        player
        for player in observation.players
        if player.is_hero
    ]

    if len(heroes) != 1:
        errors.append(
            f"Se esperaba 1 Hero y se detectaron "
            f"{len(heroes)}."
        )

        return errors

    hero = heroes[0]

    if not hero.cards:
        errors.append(
            "No se han podido detectar "
            "las cartas de Hero."
        )

    if hero.stack_chips is None:
        errors.append(
            "No se ha podido detectar "
            "el stack de Hero."
        )

    if len(observation.players) < 2:
        errors.append(
            "No se han detectado suficientes jugadores."
        )

    return errors


def analyze_image(
    image_path: str,
):

    print()
    print("=" * 60)
    print("AGENTE_POKER - HAND READER")
    print("=" * 60)

    # ==================================================
    # 1. VISIÓN
    # ==================================================

    reader = HandReader()

    try:
        observation = reader.read_image(
            image_path
        )

    except Exception as exc:

        print()
        print("[ERROR DE VISIÓN]")
        print(str(exc))

        return None

    print()
    print("RAW_OBSERVATION")
    print("-" * 60)

    print(
        observation.model_dump_json(
            indent=2
        )
    )

    # ==================================================
    # 2. VALIDACIÓN CRÍTICA
    # ==================================================

    errors = validate_critical_data(
        observation
    )

    if errors:

        print()
        print("DATOS CRÍTICOS INCOMPLETOS")
        print("-" * 60)

        for error in errors:
            print(
                f"- {error}"
            )

        print()
        print(
            "No se genera HAND_STATE "
            "para evitar inventar información."
        )

        return None

    # ==================================================
    # 3. NORMALIZACIÓN
    # ==================================================

    print()
    print("NORMALIZANDO...")
    print()

    try:
        hand_state = normalize_observation(
            observation
        )

    except Exception as exc:

        print()
        print("[ERROR DE NORMALIZACIÓN]")
        print(str(exc))

        return None

    print("HAND_STATE")
    print("-" * 60)

    print(
        hand_state.model_dump_json(
            indent=2
        )
    )

    # ==================================================
    # 4. GENERAR PREGUNTA
    # ==================================================

    question = build_question(
        hand_state
    )

    print()
    print("PREGUNTA GENERADA")
    print("-" * 60)

    print(question)

    # ==================================================
    # 5. GUARDAR RUN
    # ==================================================

    run_dir = save_run(
        image_path=image_path,

        provider=reader.provider,

        model=reader.model,

        elapsed_seconds=(
            reader.last_elapsed_seconds
            or 0
        ),

        observation=observation,

        hand_state=hand_state,

        question=question,
    )

    print()
    print("RESULTADO")
    print("-" * 60)

    print(
        f"Proveedor : {reader.provider}"
    )

    print(
        f"Modelo    : {reader.model}"
    )

    print(
        f"Tiempo    : "
        f"{reader.last_elapsed_seconds:.2f} s"
    )

    print(
        f"Guardado  : {run_dir}"
    )

    print()
    print("=" * 60)

    return hand_state


def main():

    if len(sys.argv) != 2:

        print(
            "Uso:\n"
            "python -m pipeline.analyze_image "
            "test_images\\test_001.png"
        )

        raise SystemExit(1)

    analyze_image(
        sys.argv[1]
    )


if __name__ == "__main__":
    main()