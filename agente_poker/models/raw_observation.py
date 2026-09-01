from pydantic import BaseModel, Field


class RawPlayerObservation(BaseModel):
    seat: str

    stack_chips: int | None = Field(
        default=None,
        ge=0,
    )

    committed_chips: int | None = Field(
        default=None,
        ge=0,
    )

    cards: list[str] | None = None

    has_dealer_button: bool = False

    is_hero: bool = False

    confidence: float = Field(
        default=1.0,
        ge=0,
        le=1,
    )


class RawTableObservation(BaseModel):
    source: str = "image"

    players_visible: int | None = Field(
        default=None,
        ge=2,
    )

    sb_chips: int | None = Field(
        default=None,
        gt=0,
    )

    bb_chips: int | None = Field(
        default=None,
        gt=0,
    )

    pot_chips: int | None = Field(
        default=None,
        ge=0,
    )

    board: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    players: list[RawPlayerObservation] = Field(
        default_factory=list,
    )

    uncertainties: list[str] = Field(
        default_factory=list,
    )

if __name__ == "__main__":
    observation = RawTableObservation(
        players_visible=3,

        sb_chips=10,
        bb_chips=20,
        pot_chips=30,

        players=[
            RawPlayerObservation(
                seat="top_right",
                stack_chips=340,
                committed_chips=0,
                cards=["Jc", "Qh"],
                has_dealer_button=True,
                is_hero=True,
                confidence=0.99,
            ),

            RawPlayerObservation(
                seat="bottom",
                stack_chips=910,
                committed_chips=10,
                confidence=0.98,
            ),

            RawPlayerObservation(
                seat="top_left",
                stack_chips=220,
                committed_chips=20,
                confidence=0.98,
            ),
        ],
    )

    print(
        observation.model_dump_json(
            indent=2,
        )
    )