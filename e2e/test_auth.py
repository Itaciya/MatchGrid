from selenium.webdriver.common.by import By

from e2e.conftest import PASSWORD
from e2e.pages.auth_page import unique_email, wait_visible


def test_register_login_and_logout(driver, auth):
    email = unique_email("player")
    auth.open()
    auth.register(email, PASSWORD, "player")
    auth.login(email, PASSWORD)
    auth.wait_signed_in(email)
    assert "player" in driver.find_element(*auth.USER_BADGE).text
    auth.sign_out()
    assert not driver.find_elements(*auth.USER_BADGE)


def test_wrong_password_shows_error(driver, auth):
    email = unique_email("player")
    auth.open()
    auth.register(email, PASSWORD, "player")
    auth.login(email, "Wrong-Passw0rd!")
    wait_visible(driver, auth.ERROR)
    assert not driver.find_elements(*auth.USER_BADGE)


def test_unknown_email_cannot_login(driver, auth):
    auth.open()
    auth.login(unique_email("ghost"), PASSWORD)
    wait_visible(driver, auth.ERROR)
    assert not driver.find_elements(*auth.USER_BADGE)


def test_signed_out_user_cannot_see_protected_nav(driver, auth):
    auth.open()
    nav = driver.find_elements(By.XPATH, "//aside//button[contains(@class,'nav-item')]")
    labels = [n.text for n in nav]
    assert "Create tournament" not in labels
    assert "Scoring" not in labels
