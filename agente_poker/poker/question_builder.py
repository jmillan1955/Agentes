from models.hand_state import HandState, Position


def format_stack(player) -> str:
    """
    Representación legible del stack.

    Preferimos total_bb si existe, porque incluye
    las fichas ya comprometidas.
    """

    if player.total_bb is not None:
        return f"{player.total_bb:g}bb"

    if player.stack_bb is not None:
        return f"{player.stack_bb:g}bb"

    return "stack desconocido"


def build_question(hand: HandState) -> str:
    """
    Convierte HAND_STATE en una pregunta legible
    para el futuro motor Spin & Go.
    """

    hero = hand.hero

    villains_by_position = {
        villain.position: villain
        for villain in hand.villains
    }

    parts = []

    # Formato
    parts.append(
        f"Spin & Go {hand.players_remaining}-handed"
    )

    # Blinds
    parts.append(
        f"blinds {hand.blinds.sb}/{hand.blinds.bb}"
    )

    # Hero
    hero_stack = format_stack(hero)

    parts.append(
        f"Hero {hero.position.value} con "
        f"{hero.hand_class} y {hero_stack}"
    )

    # Rivales
    sb = villains_by_position.get(Position.SB)

    if sb is not None:
        parts.append(
            f"SB tiene {format_stack(sb)}"
        )

    bb = villains_by_position.get(Position.BB)

    if bb is not None:
        parts.append(
            f"BB tiene {format_stack(bb)}"
        )

    # Situación actual
    if (
        hand.street.value == "preflop"
        and hero.position == Position.BTN
        and hand.hero_to_act
    ):
        parts.append(
            "Hero es first-in preflop"
        )

    question = ". ".join(parts)

    question += (
        ". ¿Cuál es la estrategia GTO preflop?"
    )

    return question