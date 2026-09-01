from app.verification import VerificationPolicy


def test_automatic_policy_detects_current_queries() -> None:
    policy = VerificationPolicy("automatic")

    assert policy.requires_web(
        "Comprueba la documentación actual de Home Assistant"
    )
    assert policy.requires_web(
        "¿Cuál es el precio de la electricidad hoy?"
    )


def test_automatic_policy_ignores_stable_queries() -> None:
    policy = VerificationPolicy("automatic")

    assert not policy.requires_web(
        "Explica qué es una función de Python"
    )


def test_on_demand_policy_never_routes_automatically() -> None:
    policy = VerificationPolicy("on_demand")

    assert not policy.requires_web(
        "Busca las últimas noticias"
    )
