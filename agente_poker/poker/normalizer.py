from models.hand_state import (
    Blinds,
    DataOrigin,
    HandState,
    HeroState,
    PlayerState,
    Position,
    PotState,
    Street,
)
from models.raw_observation import (
    RawPlayerObservation,
    RawTableObservation,
)


RANK_ORDER = "23456789TJQKA"
VALID_SUITS = {"c", "d", "h", "s"}


# ============================================================
# CONVERSIONES
# ============================================================

def chips_to_bb(
    chips: int | None,
    big_blind: int,
) -> float | None:
    """
    Convierte fichas a big blinds.

    Ejemplo:
        340 chips con BB=20 -> 17.0 bb
    """

    if chips is None:
        return None

    if big_blind <= 0:
        raise ValueError(
            "La big blind debe ser mayor que 0."
        )

    return round(
        chips / big_blind,
        2,
    )


# ============================================================
# NORMALIZACIÓN DE CARTAS
# ============================================================

def normalize_hand_class(
    cards: list[str],
) -> str:
    """
    Convierte las dos cartas de Hero a notación estándar.

    Ejemplos:
        ["Jc", "Qh"] -> "QJo"
        ["As", "Ks"] -> "AKs"
        ["7d", "7c"] -> "77"
    """

    if len(cards) != 2:
        raise ValueError(
            "Hero debe tener exactamente dos cartas."
        )

    card1, card2 = cards

    if len(card1) != 2 or len(card2) != 2:
        raise ValueError(
            f"Formato de cartas inválido: {cards}"
        )

    rank1 = card1[0].upper()
    rank2 = card2[0].upper()

    suit1 = card1[1].lower()
    suit2 = card2[1].lower()

    if rank1 not in RANK_ORDER:
        raise ValueError(
            f"Rango de carta inválido: {rank1}"
        )

    if rank2 not in RANK_ORDER:
        raise ValueError(
            f"Rango de carta inválido: {rank2}"
        )

    if suit1 not in VALID_SUITS:
        raise ValueError(
            f"Palo de carta inválido: {suit1}"
        )

    if suit2 not in VALID_SUITS:
        raise ValueError(
            f"Palo de carta inválido: {suit2}"
        )

    # Pareja
    if rank1 == rank2:
        return f"{rank1}{rank2}"

    # Carta más alta primero
    if (
        RANK_ORDER.index(rank1)
        > RANK_ORDER.index(rank2)
    ):
        high = rank1
        low = rank2
    else:
        high = rank2
        low = rank1

    suffix = (
        "s"
        if suit1 == suit2
        else "o"
    )

    return f"{high}{low}{suffix}"


# ============================================================
# INFERENCIA DE CIEGAS
# ============================================================

def infer_blinds_from_committed(
    observation: RawTableObservation,
) -> tuple[int | None, int | None]:
    """
    Intenta inferir SB y BB usando únicamente las fichas
    comprometidas visibles.

    Esta primera versión está diseñada principalmente para
    situaciones PREFLOP SIN acción previa.

    Ejemplo:

        BTN committed = 0
        SB  committed = 10
        BB  committed = 20

    Resultado:

        SB = 10
        BB = 20

    La inferencia es deliberadamente conservadora.
    """

    committed_values = [
        player.committed_chips
        for player in observation.players
        if (
            player.committed_chips is not None
            and player.committed_chips > 0
        )
    ]

    # Eliminamos duplicados y ordenamos
    unique_values = sorted(
        set(committed_values)
    )

    # Para esta primera versión queremos exactamente
    # dos cantidades positivas distintas.
    if len(unique_values) != 2:
        return None, None

    sb_candidate = unique_values[0]
    bb_candidate = unique_values[1]

    # Estructura estándar SB = 1/2 BB
    if bb_candidate == sb_candidate * 2:
        return (
            sb_candidate,
            bb_candidate,
        )

    return None, None


def resolve_blinds(
    observation: RawTableObservation,
) -> tuple[int, int, bool, bool]:
    """
    Resuelve las ciegas.

    Prioridad:

    1. Valores observados directamente por visión.
    2. Inferencia a partir de committed_chips.

    Devuelve:

        sb
        bb
        sb_was_inferred
        bb_was_inferred
    """

    sb = observation.sb_chips
    bb = observation.bb_chips

    sb_inferred = False
    bb_inferred = False

    inferred_sb, inferred_bb = (
        infer_blinds_from_committed(
            observation
        )
    )

    if sb is None:
        sb = inferred_sb

        if sb is not None:
            sb_inferred = True

    if bb is None:
        bb = inferred_bb

        if bb is not None:
            bb_inferred = True

    if sb is None:
        raise ValueError(
            "No se ha podido determinar la small blind."
        )

    if bb is None:
        raise ValueError(
            "No se ha podido determinar la big blind."
        )

    if bb <= sb:
        raise ValueError(
            f"Ciegas incoherentes: SB={sb}, BB={bb}"
        )

    return (
        sb,
        bb,
        sb_inferred,
        bb_inferred,
    )


# ============================================================
# INFERENCIA DE POSICIONES
# ============================================================

def infer_position(
    player: RawPlayerObservation,
    sb: int,
    bb: int,
) -> Position:
    """
    Inferencia inicial de posiciones para Spin & Go
    3-handed preflop.

    Prioridad:

    1. Dealer button -> BTN
    2. committed == SB -> SB
    3. committed == BB -> BB
    """

    if player.has_dealer_button:
        return Position.BTN

    committed = player.committed_chips

    if committed == sb:
        return Position.SB

    if committed == bb:
        return Position.BB

    raise ValueError(
        f"No se pudo inferir la posición "
        f"del asiento '{player.seat}'. "
        f"Committed={committed}, SB={sb}, BB={bb}"
    )


# ============================================================
# CONSTRUCCIÓN DE JUGADORES
# ============================================================

def build_player(
    raw_player: RawPlayerObservation,
    position: Position,
    big_blind: int,
) -> PlayerState:
    """
    Construye un PlayerState a partir de una observación visual.
    """

    stack_chips = (
        raw_player.stack_chips
    )

    committed_chips = (
        raw_player.committed_chips
        if raw_player.committed_chips is not None
        else 0
    )

    total_chips = None

    if stack_chips is not None:
        total_chips = (
            stack_chips
            + committed_chips
        )

    return PlayerState(
        position=position,

        # Stack todavía detrás
        stack_chips=stack_chips,

        stack_bb=chips_to_bb(
            stack_chips,
            big_blind,
        ),

        # Fichas ya comprometidas
        committed_chips=committed_chips,

        committed_bb=(
            chips_to_bb(
                committed_chips,
                big_blind,
            )
            or 0.0
        ),

        # Stack total de la situación
        total_chips=total_chips,

        total_bb=chips_to_bb(
            total_chips,
            big_blind,
        ),

        active=True,
    )


def build_hero(
    raw_player: RawPlayerObservation,
    position: Position,
    big_blind: int,
) -> HeroState:
    """
    Construye HeroState y normaliza automáticamente
    sus cartas.
    """

    if not raw_player.cards:
        raise ValueError(
            "Hero no tiene cartas detectadas."
        )

    stack_chips = (
        raw_player.stack_chips
    )

    committed_chips = (
        raw_player.committed_chips
        if raw_player.committed_chips is not None
        else 0
    )

    total_chips = None

    if stack_chips is not None:
        total_chips = (
            stack_chips
            + committed_chips
        )

    return HeroState(
        position=position,

        stack_chips=stack_chips,

        stack_bb=chips_to_bb(
            stack_chips,
            big_blind,
        ),

        committed_chips=committed_chips,

        committed_bb=(
            chips_to_bb(
                committed_chips,
                big_blind,
            )
            or 0.0
        ),

        total_chips=total_chips,

        total_bb=chips_to_bb(
            total_chips,
            big_blind,
        ),

        cards=raw_player.cards,

        hand_class=normalize_hand_class(
            raw_player.cards
        ),

        active=True,
    )


# ============================================================
# NORMALIZADOR PRINCIPAL
# ============================================================

def normalize_observation(
    observation: RawTableObservation,
) -> HandState:
    """
    Convierte:

        RawTableObservation

    en:

        HandState

    La capa de visión describe lo que ve.
    Esta función aplica conocimiento y matemáticas de poker.
    """

    if not observation.players:
        raise ValueError(
            "No existen jugadores en la observación."
        )

    # --------------------------------------------------------
    # 1. Resolver ciegas
    # --------------------------------------------------------

    (
        sb,
        bb,
        sb_inferred,
        bb_inferred,
    ) = resolve_blinds(
        observation
    )

    # --------------------------------------------------------
    # 2. Encontrar Hero
    # --------------------------------------------------------

    hero_candidates = [
        player
        for player in observation.players
        if player.is_hero
    ]

    if len(hero_candidates) != 1:
        raise ValueError(
            "Debe existir exactamente un Hero. "
            f"Detectados: {len(hero_candidates)}"
        )

    raw_hero = hero_candidates[0]

    # --------------------------------------------------------
    # 3. Inferir posición de Hero
    # --------------------------------------------------------

    hero_position = infer_position(
        player=raw_hero,
        sb=sb,
        bb=bb,
    )

    # --------------------------------------------------------
    # 4. Construir Hero
    # --------------------------------------------------------

    hero = build_hero(
        raw_player=raw_hero,
        position=hero_position,
        big_blind=bb,
    )

    # --------------------------------------------------------
    # 5. Construir rivales
    # --------------------------------------------------------

    villains: list[PlayerState] = []

    for raw_player in observation.players:

        if raw_player.is_hero:
            continue

        position = infer_position(
            player=raw_player,
            sb=sb,
            bb=bb,
        )

        player = build_player(
            raw_player=raw_player,
            position=position,
            big_blind=bb,
        )

        villains.append(
            player
        )

    # --------------------------------------------------------
    # 6. Pot
    # --------------------------------------------------------

    pot = None

    if observation.pot_chips is not None:

        pot = PotState(
            chips=observation.pot_chips,

            bb=chips_to_bb(
                observation.pot_chips,
                bb,
            ),
        )

    # --------------------------------------------------------
    # 7. Número de jugadores
    # --------------------------------------------------------

    players_remaining = (
        observation.players_visible
        if observation.players_visible is not None
        else len(observation.players)
    )

    # --------------------------------------------------------
    # 8. Confidence
    # --------------------------------------------------------

    confidence: dict[str, float] = {
        "hero.cards":
            raw_hero.confidence,

        "hero.stack_chips":
            raw_hero.confidence,
    }

    for player in observation.players:
        confidence[
            f"player.{player.seat}"
        ] = player.confidence

    # --------------------------------------------------------
    # 9. Origen de datos
    # --------------------------------------------------------

    data_origin: dict[str, DataOrigin] = {
        "hero.cards":
            DataOrigin.OBSERVED,

        "hero.stack_chips":
            DataOrigin.OBSERVED,

        "hero.stack_bb":
            DataOrigin.CALCULATED,

        "hero.hand_class":
            DataOrigin.CALCULATED,

        "hero.position":
            DataOrigin.INFERRED,

        "pot.bb":
            DataOrigin.CALCULATED,
    }

    if sb_inferred:
        data_origin[
            "blinds.sb"
        ] = DataOrigin.INFERRED
    else:
        data_origin[
            "blinds.sb"
        ] = DataOrigin.OBSERVED

    if bb_inferred:
        data_origin[
            "blinds.bb"
        ] = DataOrigin.INFERRED
    else:
        data_origin[
            "blinds.bb"
        ] = DataOrigin.OBSERVED

    # --------------------------------------------------------
    # 10. Incertidumbres
    # --------------------------------------------------------

    uncertainties = (
        observation.uncertainties.copy()
    )

    # Ya que hemos resuelto las ciegas mediante inferencia,
    # añadimos información explícita sobre ello.
    if sb_inferred or bb_inferred:
        uncertainties.append(
            f"Ciegas inferidas a partir de fichas "
            f"comprometidas: SB={sb}, BB={bb}."
        )

    # --------------------------------------------------------
    # 11. HAND_STATE
    # --------------------------------------------------------

    return HandState(
        players_remaining=players_remaining,

        street=Street.PREFLOP,

        blinds=Blinds(
            sb=sb,
            bb=bb,
        ),

        hero=hero,

        villains=villains,

        board=observation.board,

        pot=pot,

        # Temporal:
        # esta versión sigue orientada a nuestro caso
        # preflop first-in.
        hero_to_act=True,

        confidence=confidence,

        data_origin=data_origin,

        uncertainties=uncertainties,
    )


# ============================================================
# TEST MANUAL
# ============================================================

if __name__ == "__main__":

    # Simulamos precisamente el caso en el que la visión
    # NO consigue leer directamente las ciegas,
    # pero sí detecta 10 y 20 fichas comprometidas.

    observation = RawTableObservation(
        players_visible=3,

        sb_chips=None,
        bb_chips=None,

        pot_chips=30,

        board=[],

        players=[
            RawPlayerObservation(
                seat="top_right",

                stack_chips=340,
                committed_chips=0,

                cards=[
                    "Jc",
                    "Qh",
                ],

                has_dealer_button=True,
                is_hero=True,

                confidence=0.99,
            ),

            RawPlayerObservation(
                seat="bottom",

                stack_chips=910,
                committed_chips=10,

                cards=None,

                has_dealer_button=False,
                is_hero=False,

                confidence=0.95,
            ),

            RawPlayerObservation(
                seat="top_left",

                stack_chips=220,
                committed_chips=20,

                cards=None,

                has_dealer_button=False,
                is_hero=False,

                confidence=0.98,
            ),
        ],

        uncertainties=[
            (
                "Small blind y big blind no son "
                "legibles directamente en la captura."
            )
        ],
    )

    hand = normalize_observation(
        observation
    )

    print(
        hand.model_dump_json(
            indent=2
        )
    )