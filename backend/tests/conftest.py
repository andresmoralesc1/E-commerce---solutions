"""Conftest — fixtures compartidos."""
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def env_setup():
    """Asegurar DATABASE_URL antes de importar la app."""
    os.environ.setdefault(
        "DATABASE_URL",
        os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://brain:braindemo123@localhost:5432/brain",
        ),
    )
    os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-32chars")
    os.environ.setdefault("LLM_PROVIDER", "mock")


@pytest.fixture
def anyio_backend():
    return "asyncio"