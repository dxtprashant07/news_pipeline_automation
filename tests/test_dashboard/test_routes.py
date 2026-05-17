"""Tests for dashboard API routes — uses FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from dashboard.app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@patch("dashboard.routes.articles.get_session")
def test_list_articles_empty(mock_session):
    mock_repo = MagicMock()
    mock_repo.get_pending_review.return_value = []
    with patch("dashboard.routes.articles.DraftRepository", return_value=mock_repo):
        resp = client.get("/articles/")
    assert resp.status_code == 200
    assert resp.json() == []


@patch("dashboard.routes.articles.get_session")
def test_approve_nonexistent_returns_404(mock_get_session):
    def override_session():
        session = MagicMock()
        session.get.return_value = None
        yield session

    app.dependency_overrides = {}
    from dashboard.routes.articles import get_session as real_get_session
    app.dependency_overrides[real_get_session] = override_session

    resp = client.post("/articles/999/approve", json={})
    assert resp.status_code == 404

    app.dependency_overrides = {}
