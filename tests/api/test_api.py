from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_app_starts():
    response = client.get("/docs")
    assert response.status_code == 200

def test_openapi_schema():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()
