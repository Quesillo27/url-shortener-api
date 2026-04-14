"""
Tests para url-shortener-api.
Usa TestClient de FastAPI (httpx) — sin servidor externo.
"""

import os
import pytest

# Use in-memory DB for tests
os.environ["DB_PATH"] = ":memory:"
os.environ["BASE_URL"] = "http://testserver"

import main as app_module
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Fresh client + DB for each test."""
    app_module.reset_conn()  # close any previous connection
    with TestClient(app_module.app) as c:
        yield c


# ─── Health ──────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── Create URLs ─────────────────────────────────────────────────────────────

def test_create_url_auto_alias(client):
    r = client.post("/shorten", json={"url": "https://example.com"})
    assert r.status_code == 201
    data = r.json()
    assert data["original"] == "https://example.com"
    assert "alias" in data
    assert data["alias"] in data["short_url"]
    assert data["click_count"] == 0


def test_create_url_custom_alias(client):
    r = client.post("/shorten", json={"url": "https://github.com", "alias": "gh-test"})
    assert r.status_code == 201
    assert r.json()["alias"] == "gh-test"


def test_create_url_duplicate_alias_returns_409(client):
    client.post("/shorten", json={"url": "https://example.com", "alias": "dup-test"})
    r = client.post("/shorten", json={"url": "https://other.com", "alias": "dup-test"})
    assert r.status_code == 409


def test_create_url_invalid_alias_chars(client):
    r = client.post("/shorten", json={"url": "https://example.com", "alias": "bad alias!"})
    assert r.status_code == 422


def test_create_url_alias_too_short(client):
    r = client.post("/shorten", json={"url": "https://example.com", "alias": "ab"})
    assert r.status_code == 422


def test_create_url_no_scheme_returns_422(client):
    r = client.post("/shorten", json={"url": "example.com"})
    assert r.status_code == 422


def test_create_url_with_expiry(client):
    r = client.post("/shorten", json={
        "url": "https://example.com",
        "expires_at": "2099-12-31T23:59:59Z"
    })
    assert r.status_code == 201
    assert r.json()["expires_at"] is not None


def test_create_url_expired_date_returns_422(client):
    r = client.post("/shorten", json={
        "url": "https://example.com",
        "expires_at": "2000-01-01T00:00:00Z"
    })
    assert r.status_code == 422


# ─── Redirect ────────────────────────────────────────────────────────────────

def test_redirect_works(client):
    client.post("/shorten", json={"url": "https://example.com", "alias": "ex-test"})
    r = client.get("/ex-test", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com"


def test_redirect_increments_click_count(client):
    client.post("/shorten", json={"url": "https://example.com", "alias": "clk-test"})
    client.get("/clk-test", follow_redirects=False)
    client.get("/clk-test", follow_redirects=False)
    r = client.get("/api/urls/clk-test")
    assert r.json()["click_count"] == 2


def test_redirect_nonexistent_returns_404(client):
    r = client.get("/doesnotexist-xyz", follow_redirects=False)
    assert r.status_code == 404


def test_redirect_expired_url_returns_410(client):
    """URLs with past expiry should return 410 Gone."""
    # Insert expired URL via the shared connection
    with app_module.db() as conn:
        conn.execute(
            "INSERT INTO urls (alias, original, created_at, expires_at) VALUES (?, ?, ?, ?)",
            ("expired-test", "https://example.com",
             "2020-01-01T00:00:00+00:00", "2020-01-02T00:00:00+00:00")
        )
    r = client.get("/expired-test", follow_redirects=False)
    assert r.status_code == 410


# ─── List & Get ──────────────────────────────────────────────────────────────

def test_list_urls_empty(client):
    r = client.get("/api/urls")
    assert r.status_code == 200
    assert r.json()["meta"]["total"] == 0


def test_list_urls_pagination(client):
    for i in range(5):
        client.post("/shorten", json={"url": f"https://example{i}.com"})
    r = client.get("/api/urls?page=1&limit=2")
    assert r.status_code == 200
    data = r.json()
    assert len(data["urls"]) == 2
    assert data["meta"]["total"] == 5
    assert data["meta"]["pages"] == 3


def test_get_url_by_alias(client):
    client.post("/shorten", json={"url": "https://example.com", "alias": "info-test"})
    r = client.get("/api/urls/info-test")
    assert r.status_code == 200
    assert r.json()["alias"] == "info-test"


def test_get_url_not_found(client):
    r = client.get("/api/urls/notfound-xyz")
    assert r.status_code == 404


# ─── Stats ───────────────────────────────────────────────────────────────────

def test_stats_initial_zero_clicks(client):
    client.post("/shorten", json={"url": "https://stats.com", "alias": "st-test"})
    r = client.get("/api/urls/st-test/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_clicks"] == 0
    assert data["clicks_by_day"] == []


def test_stats_records_click(client):
    client.post("/shorten", json={"url": "https://stats.com", "alias": "stc-test"})
    client.get("/stc-test", follow_redirects=False)
    r = client.get("/api/urls/stc-test/stats")
    assert r.json()["total_clicks"] == 1
    assert len(r.json()["recent_clicks"]) == 1


def test_global_stats(client):
    client.post("/shorten", json={"url": "https://example.com"})
    r = client.get("/api/stats/global")
    assert r.status_code == 200
    data = r.json()
    assert data["total_urls"] >= 1
    assert "top_urls" in data


# ─── Delete ──────────────────────────────────────────────────────────────────

def test_deactivate_url(client):
    client.post("/shorten", json={"url": "https://example.com", "alias": "del-test"})
    r = client.delete("/api/urls/del-test")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # Redirect should now 404
    r2 = client.get("/del-test", follow_redirects=False)
    assert r2.status_code == 404


def test_deactivate_nonexistent_returns_404(client):
    r = client.delete("/api/urls/ghost-xyz")
    assert r.status_code == 404
