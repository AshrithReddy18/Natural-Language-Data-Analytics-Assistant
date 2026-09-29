"""Test configuration. Environment is set before the app is imported so settings pick it up."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="datapilot-tests-"))
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{(_TMP / 'meta.db').as_posix()}",
        "DEMO_DATABASE_URL": f"sqlite:///{(_TMP / 'demo.db').as_posix()}",
        "LLM_PROVIDER": "none",
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "LOG_LEVEL": "WARNING",
        "SECRET_KEY": "test-secret",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.datasources.sqlalchemy_connector import SQLAlchemyConnector  # noqa: E402
from app.demo.seed import seed  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup() -> Iterator[None]:
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def demo_url() -> str:
    url = os.environ["DEMO_DATABASE_URL"]
    seed(url, if_empty=True)
    return url


@pytest.fixture(scope="session")
def connector(demo_url: str) -> Iterator[SQLAlchemyConnector]:
    c = SQLAlchemyConnector(demo_url)
    yield c
    c.dispose()


@pytest.fixture(scope="session")
def client(demo_url: str) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo_id(client: TestClient) -> str:
    sources = client.get("/api/datasets").json()
    return next(s["id"] for s in sources if s["is_demo"])
