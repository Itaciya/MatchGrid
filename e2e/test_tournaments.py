from datetime import datetime, timedelta
import uuid

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from e2e.pages.auth_page import wait_visible
from e2e.pages.tournament_page import TournamentPage, nav_item


def _dt(days):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def test_organiser_sees_create_tournament_nav(driver, make_user):
    make_user("organiser")
    wait_visible(driver, nav_item("Create tournament"))


def test_spectator_does_not_see_create_tournament_nav(driver, make_user):
    make_user("spectator")
    wait_visible(driver, nav_item("Tournaments"))
    assert not driver.find_elements(*nav_item("Create tournament"))


def test_organiser_can_create_tournament(driver, make_user):
    make_user("organiser")
    page = TournamentPage(driver)
    name = f"E2E Cup {uuid.uuid4().hex[:6]}"

    page.open_create_form()
    page.create(name, "Created by Selenium", _dt(30), _dt(40))

    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(page.detail_heading(name))
    )


def test_created_tournament_appears_in_list_and_search(driver, make_user):
    make_user("organiser")
    page = TournamentPage(driver)
    name = f"E2E Search {uuid.uuid4().hex[:6]}"

    page.open_create_form()
    page.create(name, "Search me", _dt(30), _dt(40))
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(page.detail_heading(name))
    )

    page.open_list()
    page.search(name)
    link = (By.XPATH, f"//button[contains(@class,'table-link')][normalize-space()='{name}']")
    wait_visible(driver, link)


def test_end_date_before_start_date_is_rejected(driver, make_user):
    make_user("organiser")
    page = TournamentPage(driver)
    name = f"E2E Bad Dates {uuid.uuid4().hex[:6]}"

    page.open_create_form()
    page.create(name, "Invalid dates", _dt(40), _dt(30))

    end_input = driver.find_element(*page.END)
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return arguments[0].validity.rangeUnderflow", end_input)
    )
    assert not driver.find_elements(*page.detail_heading(name))

