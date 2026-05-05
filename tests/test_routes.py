"""PLG App — route tests with mocked services."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "plg-app"


def test_generate_leads_missing_website():
    response = client.post("/generate-leads", json={
        "company_name": "Test Co",
        "website": "",
    })
    # Pydantic min_length=1 validation returns 422
    assert response.status_code == 422


def test_generate_leads_missing_company():
    response = client.post("/generate-leads", json={
        "website": "https://test.com",
    })
    # company_name is required
    assert response.status_code == 422


@patch("app.routes.generate.QualificationPipeline")
def test_generate_leads_valid_input(mock_pipeline_class):
    """Test with mocked pipeline to avoid hitting real APIs."""
    mock_pipeline = MagicMock()
    mock_pipeline.run = MagicMock()

    # Make the async mock return properly
    import asyncio
    future = asyncio.Future()
    future.set_result(("https://docs.google.com/spreadsheets/d/test/edit", 50))
    mock_pipeline.run.return_value = future

    mock_pipeline_class.return_value = mock_pipeline

    response = client.post("/generate-leads", json={
        "company_name": "Test Co",
        "website": "https://test.com",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert "job_id" in data
    assert data["leads_count"] == 50
    assert "google.com/spreadsheets" in data["sheet_url"]
