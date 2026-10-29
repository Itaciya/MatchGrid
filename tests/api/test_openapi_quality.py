import warnings
from fastapi.testclient import TestClient
from app.main import app

def test_no_duplicate_operation_ids():
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        TestClient(app).get("/openapi.json")
    dupes = [str(w.message) for w in caught if "Duplicate Operation ID" in str(w.message)]
    assert not dupes, dupes
