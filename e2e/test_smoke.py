from selenium.webdriver.common.by import By


def test_frontend_loads(driver, frontend_url):
    driver.get(frontend_url)
    brand = driver.find_element(By.CSS_SELECTOR, ".brand-copy strong")
    assert brand.text == "MatchGrid"


def test_backend_docs_load(driver, api_url):
    driver.get(api_url + "/docs")
    assert "FastAPI" in driver.title or "MatchGrid" in driver.title or "Swagger" in driver.title
