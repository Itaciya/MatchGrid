def test_backend_docs_page(driver):
    driver.get("http://127.0.0.1:8000/docs")
    assert "Swagger UI" in driver.title

def test_openapi_json_loads(driver):
    driver.get("http://127.0.0.1:8000/openapi.json")
    assert "openapi" in driver.page_source
