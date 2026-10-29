import os
import pytest
from selenium import webdriver

from e2e.pages.auth_page import AuthPage, unique_email

FRONTEND_URL = os.environ.get("E2E_FRONTEND_URL", "http://localhost:5173")
API_URL = os.environ.get("E2E_API_URL", "http://127.0.0.1:8000")
PASSWORD = "E2e-Passw0rd!"


@pytest.fixture(scope="session")
def frontend_url():
    return FRONTEND_URL


@pytest.fixture(scope="session")
def api_url():
    return API_URL


@pytest.fixture
def driver():
    options = webdriver.ChromeOptions()
    if os.environ.get("E2E_HEADLESS") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    drv = webdriver.Chrome(options=options)
    yield drv
    drv.quit()


@pytest.fixture
def auth(driver, frontend_url):
    return AuthPage(driver, frontend_url)


@pytest.fixture
def make_user(auth):
    def _make(role):
        email = unique_email(role)
        auth.open()
        auth.register(email, PASSWORD, role)
        auth.login(email, PASSWORD)
        return email, role

    return _make
