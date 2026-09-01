from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class Position(str, Enum):
    BTN = "BTN"
    SB = "SB"
    BB = "BB"


class DataOrigin(str, Enum):
    OBSERVED = "observed"
    CALCULATED = "calculated"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class Blinds(BaseModel):
    sb: int = Field(gt=0)
    bb: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_blinds(self):
        if self.bb <= self.sb:
            raise ValueError("La BB debe ser mayor que la SB.")
        return self


class PlayerState(BaseModel):
    position: Position

    # Fichas que todavía tiene delante
    stack_chips: int | None = Field(
        default=None,
        ge=0,
    )

    stack_bb: float | None = Field(
        default=None,
        ge=0,
    )

    # Fichas que ya ha puesto en el bote en la calle actual
    committed_chips: int = Field(
        default=0,
        ge=0,
    )

    committed_bb: float = Field(
        default=0.0,
        ge=0,
    )

    # Stack total disponible al inicio de la situación
    total_chips: int | None = Field(
        default=None,
        ge=0,
    )

    total_bb: float | None = Field(
        default=None,
        ge=0,
    )

    active: bool = True
class HeroState(PlayerState):
    cards: list[str] = Field(
        min_length=2,
        max_length=2,
    )

    hand_class: str | None = None


class PotState(BaseModel):
    chips: int | None = Field(default=None, ge=0)
    bb: float | None = Field(default=None, ge=0)


class HandState(BaseModel):
    schema_version: str = "0.1"

    source: str = "image"

    game: str = "texas_holdem"
    module: str = "spin_and_go"

    players_remaining: int = Field(
        ge=2,
        le=3,
    )

    street: Street

    blinds: Blinds

    hero: HeroState

    villains: list[PlayerState]

    board: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    pot: PotState | None = None

    hero_to_act: bool | None = None

    confidence: dict[str, float] = Field(
        default_factory=dict,
    )

    data_origin: dict[str, DataOrigin] = Field(
        default_factory=dict,
    )

    uncertainties: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_hand(self):

        # Hero + rivales debe coincidir con jugadores restantes
        total_players = 1 + len(self.villains)

        if total_players != self.players_remaining:
            raise ValueError(
                "players_remaining no coincide con Hero + villains."
            )

        # Confianza siempre entre 0 y 1
        for name, value in self.confidence.items():
            if not 0 <= value <= 1:
                raise ValueError(
                    f"Confidence inválida en {name}: {value}"
                )

        # Board coherente con la calle
        expected_board_cards = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5,
        }

        expected = expected_board_cards[self.street]

        if len(self.board) != expected:
            raise ValueError(
                f"{self.street.value} requiere "
                f"{expected} cartas de board; "
                f"recibidas: {len(self.board)}."
            )

        return self

    
if __name__ == "__main__":

    hand = HandState(
        players_remaining=3,
        street=Street.PREFLOP,

        blinds=Blinds(
            sb=10,
            bb=20,
        ),

        hero=HeroState(
            position=Position.BTN,
            cards=["Jc", "Qh"],
            hand_class="QJo",
            stack_chips=340,
            stack_bb=17.0,
        ),

        villains=[
            PlayerState(
                position=Position.SB,
                stack_chips=910,
                stack_bb=45.5,
            ),
            PlayerState(
                position=Position.BB,
                stack_chips=220,
                stack_bb=11.0,
            ),
        ],

        pot=PotState(
            chips=30,
            bb=1.5,
        ),

        hero_to_act=True,

        confidence={
            "hero.cards": 0.99,
            "hero.stack_chips": 0.99,
            "hero.position": 0.98,
            "blinds": 0.99,
        },

        data_origin={
            "hero.cards": DataOrigin.OBSERVED,
            "hero.stack_chips": DataOrigin.OBSERVED,
            "hero.stack_bb": DataOrigin.CALCULATED,
            "hero.position": DataOrigin.INFERRED,
            "pot.bb": DataOrigin.CALCULATED,
        },
    )

    print(
        hand.model_dump_json(
            indent=2,
        )
    )