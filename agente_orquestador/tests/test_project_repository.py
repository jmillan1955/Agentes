from app.context import (
    ContextDatabase,
    ProjectRepository,
)


def test_saves_and_recovers_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = ProjectRepository(
            database
        )

        saved = repository.save(
            name="Agente Orquestador",
            root_path=(
                "C:/Python_Proyectos/Agentes/"
                "agente_orquestador"
            ),
            git_repository=(
                "https://github.com/"
                "jmillan1955/Agentes.git"
            ),
        )

        recovered = repository.get_by_id(
            saved.id
        )

        assert recovered == saved
        assert recovered is not None
        assert recovered.active


def test_updates_existing_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = ProjectRepository(
            database
        )

        original = repository.save(
            name="Agente Orquestador",
            root_path="ruta-anterior",
        )

        updated = repository.save(
            name="Agente Orquestador",
            root_path="ruta-nueva",
            git_repository="repositorio-git",
        )

        assert updated.id == original.id
        assert updated.root_path == "ruta-nueva"
        assert (
            updated.git_repository
            == "repositorio-git"
        )


def test_lists_only_active_projects() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = ProjectRepository(
            database
        )

        repository.save(
            name="Proyecto activo",
            root_path="ruta-activa",
            active=True,
        )

        repository.save(
            name="Proyecto inactivo",
            root_path="ruta-inactiva",
            active=False,
        )

        projects = repository.list_active()

        assert len(projects) == 1
        assert projects[0].name == "Proyecto activo"


def test_returns_none_for_unknown_project() -> None:
    with ContextDatabase(
        ":memory:"
    ) as database:
        repository = ProjectRepository(
            database
        )

        result = repository.get_by_name(
            "Proyecto inexistente"
        )

        assert result is None