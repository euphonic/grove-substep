from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth import current_user_id
from app.config import Settings, get_settings
from app.main import create_app
from app.memory.store import get_profile


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[current_user_id] = lambda: "user-a"
    with TestClient(app) as c:
        yield c


def test_lists_traditions_from_packs(api: TestClient) -> None:
    ids = {t["id"] for t in api.get("/traditions").json()}
    assert ids == {"mindfulness", "buddhist", "christian", "yogic", "raja-yoga"}


def test_onboarding_flow(api: TestClient) -> None:
    assert api.get("/profile").json()["onboarded"] is False
    resp = api.put("/profile", json={"default_tradition": "raja-yoga", "display_name": " Sam "})
    assert resp.status_code == 200
    body = api.get("/profile").json()
    assert body["onboarded"] is True
    assert body["default_tradition"] == "raja-yoga" and body["display_name"] == "Sam"


async def _store_profile(api: TestClient) -> str | None:
    rt = api.app.state.runtime  # type: ignore[attr-defined]
    return (await get_profile(rt.store, "user-a")).default_tradition


def test_onboarding_writes_companion_memory(api: TestClient) -> None:
    api.put("/profile", json={"default_tradition": "buddhist"})
    assert api.portal.call(_store_profile, api) == "buddhist"  # type: ignore[union-attr]


def test_unknown_tradition_rejected(api: TestClient) -> None:
    assert api.put("/profile", json={"default_tradition": "made-up"}).status_code == 422
