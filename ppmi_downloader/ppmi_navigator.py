import inspect
import json
import os
import os.path as op
import shutil
import time
import urllib.parse
import zipfile
from typing import Any, Callable, Dict, List

import selenium.webdriver.support.expected_conditions as EC
import tqdm
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebElement
from selenium.webdriver.support.wait import WebDriverWait

import ppmi_downloader.ppmi_logger as logger

TIMEOUT = 5
TRIALS = 6
ppmi_main_webpage = "https://ida.loni.usc.edu/login.jsp?project=PPMI"
ppmi_home_webpage = "https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI"
ppmi_login_webpage = (
    "https://ida.loni.usc.edu/explore/jsp/common/login.jsp?project=PPMI"
)
ppmi_query_page = (
    "https://ida.loni.usc.edu/pages/access/search.jsp?project=PPMI&tab=advSearch"
)


class HTMLHelper:
    r"""
    HTML helper to interact with selenium


    Attributes
    ----------
    driver :  module selenium.webdriver.chrome.webdriver.Webdriver
        Selenium webdriver

    """

    def __init__(self, driver: ChromeWebDriver) -> None:
        r"""__init__ method

        Parameters
        ----------
        driver : selenium.webdriver.chrome.webdriver.WebDriver
            Selenium driver

        """
        self.driver = driver

    def __parser_caller(self, caller: inspect.FrameInfo) -> str:
        r"""Helper function to parse caller

        Parameters
        ----------
        caller : inspect.FrameInfo
            Caller information

        Returns
        -------
        str
            String representation of the caller

        """
        filename = os.path.basename(caller.filename)
        function = caller.function
        lineno = caller.lineno
        return f"{filename}:{lineno} {function}"

    def take_screenshot(self, function: str) -> None:
        r"""Take screenshot of the driver current page

        Parameters
        ----------
        function : str
            Name of the function
        """
        time_ns = time.time_ns()
        filename = f"error-{function}-{time_ns}"
        with open(f"{filename}.json", "w") as fo:
            json.dump(self.driver.capabilities, fo)
        self.driver.get_screenshot_as_file(f"{filename}.png")

    def wait_for_element_to_be_visible(
        self,
        field: str,
        BY: By = By.XPATH,
        timeout: float = TIMEOUT,
        debug_name: str = "",
        raise_exception: bool = False,
    ) -> WebElement:
        r"""Wait for element to be visible

        Parameters
        ----------
        field : str
            The field used to find the element
        BY : selenium.webdriver.common.by.By
            Locator strategy
        timeout : float
            Timeout after which WebDriverWait will raise a TimeoutError
        debug_name : str
            Debug name used by the logger

        Returns
        -------
        WebElement
            Element found by WebDriverWait
            An Exception is raised by WebDriverWait if not

        """
        try:
            logger.debug("Wait for element to be visible", field, BY, debug_name)
            predicate = EC.visibility_of_element_located((BY, field))
            element = WebDriverWait(self.driver, timeout, poll_frequency=1).until(
                predicate
            )
            return element
        except TimeoutException as e:
            if raise_exception:
                raise e
            self.take_screenshot("wait_for_element_visible")
            self.driver.quit()
            logger.error("wait for element to be visible times out")
        except Exception as e:
            if raise_exception:
                raise e
            self.take_screenshot("wait_for_element_visible")
            self.driver.quit()
            logger.error(f"Unknown exception {e}")

    def enter_data(
        self,
        field: str,
        data: str,
        BY: By = By.XPATH,
        debug_name: str = "",
        trials: int = TRIALS,
    ) -> None:
        r"""Enter data in the given field

        The function try to wait for the element to be clickable
        `trials` times. After `trials` attempt, the function
        quit the driver, takes a screenshot of the page
        and displays an error message.

        Parameters
        ----------
        field : str
            The field used to find the element
        data : str
            The data to send to the element
        BY : selenium.webdriver.common.by.By
            Locator strategy
        debug_name : str
            Debug name used by the logger
        trials : int
            Number of trials before quiting

        """
        if trials < 0:
            self.take_screenshot("enter_data")
            self.driver.quit()
            logger.error("Number of trials is exceeded")
        try:
            logger.debug("Enter data", field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            form = WebDriverWait(self.driver, TIMEOUT, poll_frequency=1).until(
                predicate
            )
            form.send_keys(data)
        except WebDriverException:
            self.enter_data(
                field=field, data=data, BY=BY, debug_name=debug_name, trials=trials - 1
            )

    def click_button(
        self, field: str, BY: By = By.XPATH, debug_name: str = "", trials: int = TRIALS
    ) -> None:
        r"""Click the button given by the field

        The function try to wait for the element to be clickable
        `trials` times. After `trials` attempt, the function
        quit the driver, takes a screenshot of the page
        and displays an error message.

        Parameters
        ----------
        field : str
            The field used to find the element
        data : str
            The data to send to the element
        BY : selenium.webdriver.common.by.By
            Locator strategy
        debug_name : str
            Debug name used by the logger
        trials : int
            Number of trials before quiting

        """
        stack = inspect.stack()
        caller = self.__parser_caller(stack[1]) if len(stack) > 1 else ""

        if trials < 0:
            self.take_screenshot("click_button")
            self.driver.quit()
            logger.error("Number of trials is exceeded")
        try:
            current_url = self.driver.current_url
            logger.debug("Click button", field, debug_name, caller, current_url)
            predicate = EC.element_to_be_clickable((BY, field))
            button = WebDriverWait(self.driver, TIMEOUT, poll_frequency=1).until(
                predicate
            )
            button.click()
        except WebDriverException:
            self.click_button(
                field=field, BY=BY, debug_name=debug_name, trials=trials - 1
            )

    def submit_button(
        self, field: str, BY: By = By.XPATH, debug_name: str = "", trials: int = TRIALS
    ) -> None:
        r"""Send submit to the button given by the field

        The function try to wait for the element to be clickable
        `trials` times. After `trials` attempt, the function
        quit the driver, takes a screenshot of the page
        and displays an error message.

        Parameters
        ----------
        field : str
            The field used to find the element
        BY : selenium.webdriver.common.by.By
            Locator strategy
        debug_name : str
            Debug name used by the logger
        trials : int
            Number of trials before quiting

        """
        if trials < 0:
            self.take_screenshot("submit_button")
            self.driver.quit()
            logger.error("Number of trials is exceeded")
        try:
            logger.debug("Submit button", field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            button = WebDriverWait(self.driver, TIMEOUT, poll_frequency=1).until(
                predicate
            )
            button.submit()
        except WebDriverException:
            self.submit_button(
                field=field, BY=BY, debug_name=debug_name, trials=trials - 1
            )

    def wait_for(self, predicate: Callable[..., Any]) -> Any:
        r"""Wrapper around WebDriverWait

        Wait until `predicate` is true.
        Return the object returned by `predicate`
        upon success.


        Parameters
        ----------
        predicate: Callable[..., Any]
            Predicate to check

        Returns
        -------
        Any
            Any value returned by `predicate`

        """
        return WebDriverWait(self.driver, TIMEOUT, poll_frequency=1).until(predicate)

    def click_button_by_text(self, text: str, debug_name: str = "") -> None:
        r"""Helper function to click a button labeled `text`

        Parameters
        ----------
        text : str
            Text of the button to search
        debug_name : str
            Debug name used by the logger

        """

        self.click_button(f"//*[text()='{text}']", debug_name=debug_name)

    def submit_button_by_text(self, text: str, debug_name: str = "") -> None:
        r"""Helper function to send a submit to a button labeled `text`

        Parameters
        ----------
        text : str
            Text of the button to search
        debug_name : str
            Debug name used by the logger

        """
        self.submit_button(f"//*[text()='{text}']", debug_name=debug_name)

    def validate_cookie_policy(self) -> None:
        r"""Helper function to validate cookie policy

        Function checks if the cookie are already accepted.
        If not, click on the Cookie Policy Accept button

        """
        self.driver.get(ppmi_main_webpage)
        if (cookie := self.driver.get_cookie("idaCookiePolicy")) is not None:
            if cookie["value"]:
                logger.debug("Cookie Policy already accepted")
                return

        try:
            self.click_button(
                "ida-cookie-policy-accept", BY=By.CLASS_NAME, debug_name="Cookie Policy"
            )
        except ElementClickInterceptedException:
            logger.debug("Cookie Policy already accepted")

    def find_all_anchors(self) -> List[WebElement]:
        r"""Helper function to find all anchors in the current page

        Returns
        -------
        List[WebElement]
            A list of all anchors
        """
        return self.driver.find_elements(By.TAG_NAME, "a")

    def find_all_checkboxes(self) -> List[WebElement]:
        r"""Find all checkboxes in the current page

        Returns
        -------
        List[WebElement]
            A list of all checkboxes
        """
        return self.driver.find_elements(By.XPATH, '//*[@type="checkbox"]')

    def login(self, email: str, password: str) -> None:
        r"""Help function to log to PPMI

        Function checks if user is already logged in.
        If not, enter email and password in the
        corresponding fields

        Parameters
        ----------
        email : str
            User's email
        password : str
            Users's password

        """
        self.validate_cookie_policy()
        self.driver.get(ppmi_login_webpage)
        try:
            self.wait_for_element_to_be_visible(
                "ida-menu-option.sub-menu.user", BY=By.CLASS_NAME, raise_exception=True
            )
            logger.debug("Already logged in")
            return
        except (NoSuchElementException, TimeoutException):
            pass

        self.wait_for_element_to_be_visible("userEmail", BY=By.NAME)
        self.enter_data("userEmail", email, BY=By.NAME, debug_name="Email")
        self.wait_for_element_to_be_visible("userPassword", BY=By.NAME)
        self.enter_data("userPassword", password, BY=By.NAME, debug_name="Password")
        self.wait_for_element_to_be_visible("button", BY=By.TAG_NAME)
        self.click_button("button", By.TAG_NAME, debug_name="Login button")

        try:
            self.driver.find_element(
                By.CLASS_NAME, "register-input-error-msg.invalid-login"
            )
            logger.error("Login Failed")
        except NoSuchElementException:
            logger.info("Login Successful")

    def unzip_file(self, filename: str, tempdir: str, destination_dir: str) -> None:
        r"""Helper function to unzip a file

        Function unzip `filename` into `tempdir` and
        copy the output in `destination_dir`

        Parameters
        ----------
        filename : str
            Name of the file to unzip
        tempdir : str
            Name of the directory where to extract `filename`
        destination_dir : str
            Name of the directory where to copy unzipped file
        """
        if filename.endswith(".zip"):
            # unzip file to cwd
            with zipfile.ZipFile(op.join(tempdir, filename), "r") as zip_ref:
                zip_ref.extractall(destination_dir)
                filesname = zip_ref.namelist()[:2]
                logger.info(f"Successfully downloaded files {filesname}...")
        else:
            source = op.join(tempdir, filename)
            target = op.join(destination_dir, filename)
            shutil.move(source, target)
            logger.info(f"Successfully downloaded file {filename}")

    def unzip_metadata(self, source_dir: str, destination_dir: str) -> None:
        r"""Helper function to unzip metadata

        Parameters
        ----------
        source_dir : str
            Name of the directory where metadata are located
        destination_dir : str
            Name of the directory where to copy files

        """
        i = 0
        is_metadata_ext = False
        # Do check since sometimes we still have the temporary name
        # used during downloading
        while not is_metadata_ext and i < 10:
            # Move file to cwd or extract zip file
            downloaded_files = os.listdir(source_dir)
            # we got either a csv or a zip file
            assert len(downloaded_files) == 1
            file_name = downloaded_files[0]
            is_metadata_ext = file_name.endswith((".zip", ".csv"))
            time.sleep(0.5)
            i += 1

        assert file_name.endswith((".zip", ".csv"))
        self.unzip_file(file_name, source_dir, destination_dir)
        return file_name

    def unzip_imaging_data(
        self, downloaded_files: List[str], tempdir: str, destination_dir: str
    ) -> None:
        r"""Helper function to unzip imaging data

        Parameters
        ----------
        downloaded_files : List[str]
            List of files to unzip
        tempdir : str
            Name of the directory where to extract `filename`
        destination_dir : str
            Name of the directory where to copy unzipped file

        """
        accepted_extension = (".zip", ".csv", ".dcm", ".xml")
        for filename in tqdm.tqdm(downloaded_files):
            assert filename.endswith(accepted_extension), filename
            self.unzip_file(filename, tempdir, destination_dir)
        return downloaded_files


class PPMINavigator(HTMLHelper):
    r"""Help class to navigate through webpage with selenium"""

    def click_chain_cleaner(self, action: str) -> str:
        r"""Clean action of action chain

        Clean action name to match function

        Parameters
        ----------
        action : str
            Name of the action to clean

        Returns
        -------
        str
            Cleaned action
        """
        return action.replace("(", "").replace(")", "").replace(" ", "")

    def click_button_chain(self, chain: List[str]) -> None:
        r"""Click on each action in the chain

        Allows for chaining multiple actions represented as a list of string.
        For example:
            ["Download","Study Data","ALL"]
        will click on Download then Study Data and finally ALL

        Parameters
        ----------
        chain : List[str]
            List of action to do

        """
        action = []
        for action_name in chain:
            action.append(self.click_chain_cleaner(action_name))
            getattr(self, "_".join(action))()

    def check_url_query(self, url: str, queries: Dict[str, str]) -> bool:
        r"""Checks that url has `queries`

        Parameters
        ----------
        url : str
            The url to check
        queries : Dict[str, str]
            A dict of query to check where
            key is the name of the query
            value is the expected value for the query

        Returns
        -------
        bool
            True if all queries are present else False

        """
        query = urllib.parse.parse_qs(url)
        logger.debug(queries)
        for field, expected in queries.items():
            actual = query.get(field, [""]).pop()
            logger.debug(field, expected, actual, expected == actual)
            if actual != expected:
                return False
        return True

    def is_element_active(self, class_name: str) -> bool:
        r"""Checks that element of class name `class_name` is active

        Parameters
        ----------
        class_name : str
            Class name of the element

        Returns
        -------
        bool
            True if the element is active else False

        """
        try:
            name = f"{class_name}.active"
            predicate = EC.presence_of_element_located((By.CLASS_NAME, name))
            WebDriverWait(self.driver, 2, poll_frequency=1).until(predicate)
        except (NoSuchElementException, TimeoutException):
            return False
        else:
            return True

    def has_HamburgerMenu(self) -> bool:
        r"""Checks that HamburgerMenu is present in the current page

        Returns
        -------
        bool:
            True if the current page has HamburgerMenu else False

        """
        try:
            return self.driver.find_element(
                By.CLASS_NAME, "ida-menu-hamburger"
            ).is_displayed()
        except NoSuchElementException:
            return False
        else:
            return True

    def HamburgerMenu(self) -> None:
        r"""Action to click on HamburgerMenu

        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            return self.is_element_active("ida-menu-main-options")

        while not postcondition():
            self.click_button(
                "ida-menu-hamburger", BY=By.CLASS_NAME, debug_name="Hamburger menu"
            )

    def HamburgerMenu_Download(self) -> None:
        r"""Action to click on "Download" in HamburgerMenu

        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            return self.is_element_active("ida-menu-option.sub-menu.download")

        while not postcondition():
            self.click_button(
                "ida-menu-option.sub-menu.download",
                BY=By.CLASS_NAME,
                debug_name="Download Hamburger submenu",
            )

    def HamburgerMenu_Search(self) -> None:
        r"""Action to click on "Download" in HamburgerMenu

        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            return self.is_element_active("ida-menu-option.sub-menu.search")

        while not postcondition():
            self.click_button(
                "ida-menu-option.sub-menu.search",
                BY=By.CLASS_NAME,
                debug_name="Search Hamburger submenu",
            )

    def Download(self) -> None:
        r"""Action to click on "Download"

        Action detects if HamburgerMenu is enabled or not
        to click on the correct Download button
        Click on button until postcondition is not met
        """
        if self.has_HamburgerMenu():
            self.HamburgerMenu()
            self.HamburgerMenu_Download()

        def postcondition() -> bool:
            return self.is_element_active("ida-menu-option.sub-menu.download")

        while not postcondition():
            self.click_button(
                "ida-menu-option.sub-menu.download",
                BY=By.CLASS_NAME,
                debug_name="Download",
            )

    def Download_StudyData(self) -> None:
        r"""Action to click on "Study Data" in "Download"

        Precondition: Download action
        Click on button until postcondition is not met
        """
        studydata_url = "https://ida.loni.usc.edu/pages/access/studyData.jsp"
        while not self.driver.current_url.startswith(studydata_url):
            self.click_button_by_text("Study Data", debug_name="Study Data")

    def Download_StudyData_ALL(self) -> None:
        r"""Action to click on "All" in "Study Data" in "Download"

        Precondition: StudyData action
        Click on button until postcondition is not met
        """
        studydata_url = "https://ida.loni.usc.edu/pages/access/studyData.jsp"
        while not self.driver.current_url == studydata_url:
            # Need to click on ALL tab first to be able to see all checkboxes
            # See screenshots_errors/Screenshot_error_ALL_06-12-2023.jpg
            self.click_button("ygtvlabelel77", BY=By.ID, debug_name="ALL tab")
        while not self.driver.current_url.startswith(studydata_url):
            self.click_button("sCatChkBox_312", BY=By.ID, debug_name="ALL checkbox")

    def Download_ImageCollections(self) -> None:
        r"""Action to click on "Image Collections" in "Download"

        Precondition: Download action
        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(
                self.driver.current_url,
                {"page": "DOWNLOADS", "subPage": "IMAGE_COLLECTIONS"},
            )

        while not postcondition():
            self.click_button_by_text(
                "Image Collections", debug_name="Image Collections"
            )

    def Download_GeneticData(self) -> None:
        r"""Action to click on "Genetic Data" in "Download"

        Precondition: Download action
        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(
                self.driver.current_url,
                {"page": "DOWNLOADS", "subPage": "GENETIC_DATA"},
            )

        while not postcondition():
            self.click_button_by_text("Genetic Data", debug_name="Generic Data")

    def Search(self) -> None:
        r"""Action to click on "Search"

        Click on button until postcondition is not met
        """
        if self.has_HamburgerMenu():
            self.HamburgerMenu()
            self.HamburgerMenu_Search()

        def postcondition() -> bool:
            try:
                name = "ida-menu-option.sub-menu.search.active"
                predicate = EC.presence_of_element_located((By.CLASS_NAME, name))
                WebDriverWait(self.driver, 2, poll_frequency=1).until(predicate)
            except (NoSuchElementException, TimeoutException):
                return False
            else:
                return True

        while not postcondition():
            self.click_button(
                "ida-menu-option.sub-menu.search", BY=By.CLASS_NAME, debug_name="Search"
            )

    def Search_SimpleImageSearch(self) -> None:
        r"""Action to click on "Simple Image Search" in Search

        Precondition: Search action
        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(
                self.driver.current_url, {"page": "SEARCH", "subPage": "SIMPLE_QUERY"}
            )

        while not postcondition():
            self.click_button_by_text(
                "Simple Image Search", debug_name="Simple Image Search"
            )

    def Search_AdvancedImageSearch(self) -> None:
        r"""Action to click on "Advanced Image Search" in Search

        Precondition: Search action
        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(
                self.driver.current_url, {"page": "SEARCH", "subPage": "ADV_QUERY"}
            )

        while not postcondition():
            self.click_button_by_text(
                "Advanced Image Search", debug_name="Advanced Image Search"
            )

    def Search_AdvancedImageSearchbeta(self) -> None:
        r"""Action to click on "Advanced Image Search (beta)" in Search

        Precondition: Search action
        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            time.sleep(1)
            try:
                return (
                    self.driver.find_element(By.ID, "advSearchTabId").get_attribute(
                        "title"
                    )
                    == "active"
                )
            except NoSuchElementException:
                return False

        while not postcondition():
            try:
                predicate = EC.presence_of_element_located((By.ID, "advResultTabId"))
                self.wait_for(predicate)
                text = "Advanced Search (beta)"
            except TimeoutException:
                text = "Advanced Image Search (beta)"

            logger.debug(not postcondition())
            self.click_button_by_text(text, debug_name=text)

    def Search_AdvancedImageSearchbeta_SelectAll(self) -> None:
        r"""Action to click on "Select All" in "Advanced Image Search (beta)"

        Precondition: "Advanced Image Search (beta)" action
        Click on button until postcondition is not met
        """

        def predicate(driver) -> bool:
            select_all = driver.find_element(By.ID, "advResultSelectAll")
            add_to_collection = driver.find_element(By.ID, "advResultAddCollectId")
            logger.debug(select_all, select_all.is_selected())
            logger.debug(add_to_collection, add_to_collection.is_enabled())
            return select_all.is_selected() and add_to_collection.is_enabled()

        def postcondition() -> bool:
            try:
                WebDriverWait(self.driver, 2, poll_frequency=1).until(predicate)
            except (NoSuchElementException, TimeoutException):
                return False
            else:
                return True

        while not postcondition():
            logger.debug(not postcondition())
            self.click_button("advResultSelectAll", By.ID, debug_name="Select All")

    def Search_AdvancedImageSearchbeta_AddToCollection_OK(self) -> None:
        r"""Action to click on "OK" in "Add to collection" in "Advanced Image Search (beta)"

        Precondition: "Advanced Image Search (beta)" action
        Click on button until postcondition is not met
        """

        def postcondition() -> bool:
            # Check that the dialog panel has disappeared
            try:
                return not self.driver.find_element(
                    By.ID, "regroupDialog"
                ).is_displayed()
            except NoSuchElementException:
                return True
            else:
                return False

        while not postcondition():
            logger.debug(not postcondition())
            ok = None
            for elt in self.driver.find_elements(By.TAG_NAME, "button"):
                if elt.text == "OK":
                    ok = elt
            try:
                ok.click()
            except AttributeError:
                continue
            except StaleElementReferenceException:
                break
