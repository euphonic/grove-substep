import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import auth


def test_health_reports_mock_adapters(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["adapters"]["llm_main"] == "mock"
    assert body["adapters"]["storage"] == "local"


def test_me_requires_token(client: TestClient) -> None:
    assert client.get("/me").status_code == 401


def test_me_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get("/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


@pytest.fixture
def signing_key(monkeypatch: pytest.MonkeyPatch) -> rsa.RSAPrivateKey:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk: dict[str, Any] = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-kid", alg="RS256", use="sig")
    keyset = jwt.PyJWKSet.from_dict({"keys": [jwk]})
    monkeypatch.setattr(auth, "fetch_jwks", lambda _url: keyset)
    return key


def _token(key: rsa.RSAPrivateKey, **overrides: Any) -> str:
    claims = {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 60}
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-kid"})


def test_me_accepts_valid_jwks_token(client: TestClient, signing_key: rsa.RSAPrivateKey) -> None:
    resp = client.get("/me", headers={"Authorization": f"Bearer {_token(signing_key)}"})
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "user-123"}


def test_me_rejects_expired_token(client: TestClient, signing_key: rsa.RSAPrivateKey) -> None:
    token = _token(signing_key, exp=int(time.time()) - 10)
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_me_rejects_wrong_audience(client: TestClient, signing_key: rsa.RSAPrivateKey) -> None:
    token = _token(signing_key, aud="anon")
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
