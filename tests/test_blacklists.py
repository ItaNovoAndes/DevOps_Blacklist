import logging
import uuid

from app.extensions import db
from app.models import Blacklist

APP_UUID = str(uuid.uuid4())


def post(client, headers, **body):
    return client.post("/blacklists", json=body, headers=headers)


def test_post_adds_email(client, auth):
    resp = post(client, auth, email="user@example.com", app_uuid=APP_UUID, blocked_reason="spam")
    assert resp.status_code == 201
    assert resp.get_json() == {"msg": "Email agregado a la lista negra"}

    entry = db.session.execute(db.select(Blacklist)).scalar_one()
    assert entry.email == "user@example.com"
    assert str(entry.app_uuid) == APP_UUID
    assert entry.blocked_reason == "spam"
    assert entry.request_ip == "127.0.0.1"
    assert entry.created_at is not None


def test_post_without_reason(client, auth):
    resp = post(client, auth, email="a@example.com", app_uuid=APP_UUID)
    assert resp.status_code == 201


def test_post_normalizes_email_and_rejects_duplicates(client, auth):
    assert post(client, auth, email="  User@Example.COM ", app_uuid=APP_UUID).status_code == 201
    resp = post(client, auth, email="user@example.com", app_uuid=APP_UUID)
    assert resp.status_code == 409


def test_post_validation_errors(client, auth):
    cases = [
        {"email": "no-es-email", "app_uuid": APP_UUID},
        {"email": "a@example.com", "app_uuid": "no-es-uuid"},
        {"email": "a@example.com"},
        {"app_uuid": APP_UUID},
        {"email": "a@example.com", "app_uuid": APP_UUID, "blocked_reason": "x" * 256},
    ]
    for body in cases:
        resp = client.post("/blacklists", json=body, headers=auth)
        assert resp.status_code == 400, body
        assert "errors" in resp.get_json()


def test_post_requires_json_body(client, auth):
    resp = client.post("/blacklists", data="hola", headers=auth)
    assert resp.status_code == 400


def test_post_reason_of_255_chars_is_valid(client, auth):
    resp = post(client, auth, email="a@example.com", app_uuid=APP_UUID, blocked_reason="x" * 255)
    assert resp.status_code == 201


def test_endpoints_require_token(client):
    assert client.post("/blacklists", json={}).status_code == 401
    assert client.get("/blacklists/a@example.com").status_code == 401


def test_invalid_token_returns_401(client):
    for header in ("Bearer abc.def.ghi", "Bearer nope", "Basic xyz"):
        headers = {"Authorization": header}
        assert client.get("/blacklists/a@example.com", headers=headers).status_code == 401
        assert client.post("/blacklists", json={}, headers=headers).status_code == 401


def test_token_signed_with_other_secret_returns_401(client):
    import jwt as pyjwt

    token = pyjwt.encode({"sub": "x", "type": "access", "fresh": False, "jti": "1"}, "otro-secreto-de-al-menos-32-bytes-xx")
    resp = client.get("/blacklists/a@example.com", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_get_blacklisted_email(client, auth):
    post(client, auth, email="user@example.com", app_uuid=APP_UUID, blocked_reason="spam")
    resp = client.get("/blacklists/USER@example.com", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == {
        "email": "user@example.com",
        "is_blacklisted": True,
        "blocked_reason": "spam",
    }


def test_get_not_blacklisted_email(client, auth):
    resp = client.get("/blacklists/nadie@example.com", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == {
        "email": "nadie@example.com",
        "is_blacklisted": False,
        "blocked_reason": None,
    }


def test_ip_comes_from_trusted_proxies(client, auth, caplog):
    # Cliente falsifica el primer valor; ALB agrega la IP real y nginx la del ALB.
    caplog.set_level(logging.INFO)
    headers = {**auth, "X-Forwarded-For": "6.6.6.6, 200.1.2.3, 10.0.0.5"}
    post(client, headers, email="ip@example.com", app_uuid=APP_UUID)
    entry = db.session.execute(db.select(Blacklist)).scalar_one()
    assert entry.request_ip == "200.1.2.3"
    assert "x_forwarded_for='6.6.6.6, 200.1.2.3, 10.0.0.5'" in caplog.text
