import pytest
from fastapi.testclient import TestClient

from factory import review
from factory.webapp import create_app

from test_publish import ready  # fixture réutilisée


@pytest.fixture
def client(ready, tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    return TestClient(app)


def test_index_shows_pending_render(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "File de validation" in resp.text
    assert "/video/1" in resp.text


def test_video_endpoint_serves_mp4(client):
    resp = client.get("/video/1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert client.get("/video/999").status_code == 404


def test_approve_then_queue_empty(client, ready):
    resp = client.post("/approve/1", follow_redirects=False)
    assert resp.status_code == 303
    assert review.pending(ready) == []
    assert "File vide" in client.get("/").text


def test_reject_with_note(client, ready):
    resp = client.post("/reject/1", data={"note": "hook faible"},
                       follow_redirects=False)
    assert resp.status_code == 303
    row = ready.execute(
        "SELECT review_status, review_note FROM renders WHERE id=1"
    ).fetchone()
    assert row["review_status"] == "rejected"
    assert row["review_note"] == "hook faible"


def test_publish_via_web_dryrun(client, ready):
    resp = client.post(
        "/publish/1",
        data={"account": "@compte", "platforms": ["tiktok", "instagram"]},
    )
    assert resp.status_code == 200
    assert "dryrun" in resp.text
    assert ready.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 2
    # le clic Publier a valu approbation G4
    assert ready.execute(
        "SELECT review_status FROM renders WHERE id=1"
    ).fetchone()[0] == "approved"


def test_publish_duplicate_conflict(client):
    client.post("/publish/1", data={"account": "@c", "platforms": ["tiktok"]})
    resp = client.post("/publish/1", data={"account": "@c", "platforms": ["tiktok"]})
    assert resp.status_code == 409
    assert "doublon" in resp.json()["detail"]
