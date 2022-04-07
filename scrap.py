from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time

EMAIL = "your_ppmi@email.com"
PASSWORD = "PPMI_PASSWORD"

def enterData(field,data):
    try:
        driver.find_element_by_xpath(field).send_keys(data)
        pass
    except Exception:
        time.sleep(1)
        enterData(field,data)

def clickButton(xpath):
    try:
        driver.find_element_by_xpath(xpath).click()
        pass
    except Exception:
        time.sleep(1)
        clickButton(xpath)

def downloadMetadata():
    clickButton("//div[contains(@class,'header-login-button-inside')]")
    clickButton("//a[text()='Download']")
    clickButton("//a[text()='Study Data']")
    clickButton('//*[@id="ygtvlabelel56"]')

    # Click all document checkboxes
    for checkbox in driver.find_elements_by_xpath("//input[@type='checkbox']")[0:2]:
        checkbox.click()

    clickButton('//*[@id="downloadBtn"]')

def login(email, password):
    emailField='//*[@id="userEmail"]'
    passwordField = '//*[@id="userPassword"]'
    loginButton = '//button[text()="LOGIN"]'
    enterData(emailField, email)
    enterData(passwordField, password)


driver = webdriver.Chrome("./chromedriver")
driver.get('https://ida.loni.usc.edu/login.jsp?project=PPMI')

login(EMAIL, PASSWORD)
downloadMetadata()
