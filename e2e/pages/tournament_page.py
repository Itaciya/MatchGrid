from selenium.webdriver.common.by import By

from e2e.pages.auth_page import set_value, wait_clickable, wait_visible


def nav_item(label):
    return (
        By.XPATH,
        f"//aside[contains(@class,'sidebar')]//button[contains(@class,'nav-item')][normalize-space()='{label}']",
    )


class TournamentPage:
    NAME = (By.ID, "tournament-name")
    DESCRIPTION = (By.ID, "tournament-description")
    START = (By.ID, "start-date")
    END = (By.ID, "end-date")
    SUBMIT = (By.CSS_SELECTOR, "form.form-card button[type='submit']")
    SEARCH = (By.CSS_SELECTOR, "input[type='search']")

    def __init__(self, driver):
        self.driver = driver

    def open_create_form(self):
        wait_clickable(self.driver, nav_item("Create tournament")).click()
        wait_visible(self.driver, self.NAME)

    def create(self, name, description, start, end):
        self.driver.find_element(*self.NAME).send_keys(name)
        self.driver.find_element(*self.DESCRIPTION).send_keys(description)
        set_value(self.driver, self.driver.find_element(*self.START), start)
        set_value(self.driver, self.driver.find_element(*self.END), end)

        submit = self.driver.find_element(*self.SUBMIT)

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            submit,
        )

        self.driver.execute_script("arguments[0].click();", submit)

    def detail_heading(self, name):
        return (
            By.XPATH,
            f"//div[contains(@class,'detail-card')]//h2[normalize-space()='{name}']",
        )

    def open_list(self):
        wait_clickable(self.driver, nav_item("Tournaments")).click()
        wait_visible(self.driver, self.SEARCH)

    def search(self, text):
        box = wait_visible(self.driver, self.SEARCH)
        box.clear()
        box.send_keys(text)
