from app.resources import health


def test_ping_without_token(client, monkeypatch):
    monkeypatch.setattr(health, "_instance_id", "i-test")
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "status": "ok",
        "version": health.read_version(),
        "instance_id": "i-test",
    }


def test_version_comes_from_file():
    assert health.read_version() == health.VERSION_FILE.read_text().strip()
