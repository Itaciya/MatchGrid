import uuid

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

TIMEOUT = 10


def unique_email(prefix="user"):
    return f"e2e_{prefix}_{uuid.uuid4().hex[:10]}@example.com"


def wait_visible(driver, locator, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))


def wait_clickable(driver, locator, timeout=TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))


def set_value(driver, element, value):
    driver.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        const proto = el.tagName === 'TEXTAREA'
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        value,
    )


class AuthPage:
    TOPBAR_SIGN_IN = (By.XPATH, "//header[contains(@class,'topbar')]//button[normalize-space()='Sign in']")
    TOPBAR_REGISTER = (By.XPATH, "//header[contains(@class,'topbar')]//button[normalize-space()='Register']")
    TOPBAR_SIGN_OUT = (By.XPATH, "//header[contains(@class,'topbar')]//button[normalize-space()='Sign out']")
    EMAIL = (By.ID, "auth-email")
    PASSWORD = (By.ID, "auth-password")
    ROLE = (By.ID, "auth-role")
    SUBMIT = (By.CSS_SELECTOR, "button.auth-submit")
    USER_BADGE = (By.CSS_SELECTOR, ".user-badge")
    ERROR = (By.CSS_SELECTOR, ".notice-error")
    SUCCESS = (By.CSS_SELECTOR, ".notice-success")

    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url

    def open(self):
        self.driver.get(self.base_url)
        wait_visible(self.driver, (By.CSS_SELECTOR, "header.topbar"))

    def _type(self, element, text):
        element.send_keys(Keys.CONTROL, 'a')
        element.send_keys(Keys.DELETE)
        element.send_keys(text)

    def _fill(self, email, password):
        self._type(wait_visible(self.driver, self.EMAIL), email)
        self._type(self.driver.find_element(*self.PASSWORD), password)

    def register(self, email, password, role="player"):
        wait_clickable(self.driver, self.TOPBAR_REGISTER).click()
        self._fill(email, password)
        Select(self.driver.find_element(*self.ROLE)).select_by_value(role)
        self.driver.find_element(*self.SUBMIT).click()
        wait_visible(self.driver, self.SUCCESS)

    def login(self, email, password):
        if self.driver.find_elements(*self.TOPBAR_SIGN_IN):
            wait_clickable(self.driver, self.TOPBAR_SIGN_IN).click()
        self._fill(email, password)
        self.driver.find_element(*self.SUBMIT).click()

    def wait_signed_in(self, email):
        WebDriverWait(self.driver, TIMEOUT).until(
            EC.text_to_be_present_in_element(self.USER_BADGE, email)
        )

    def sign_out(self):
        wait_clickable(self.driver, self.TOPBAR_SIGN_OUT).click()
        WebDriverWait(self.driver, TIMEOUT).until(
            EC.text_to_be_present_in_element(self.SUCCESS, "signed out")
        )
