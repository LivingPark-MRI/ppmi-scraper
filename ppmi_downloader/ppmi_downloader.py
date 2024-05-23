import getpass
import json
import os
import os.path as op
import signal
import socket
import string
import tempfile
from configparser import ConfigParser
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pkg_resources
import tqdm
from bs4 import BeautifulSoup
from packaging import version
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import ppmi_downloader.ppmi_logger as logger
from ppmi_downloader.ppmi_navigator import (
    PPMINavigator,
    ppmi_home_webpage,
    ppmi_main_webpage,
    ppmi_query_page,
)

from .utils import cohort_id


class fileMatchingError(Exception):
    pass


def get_ip_hostname():
    return socket.gethostbyname(socket.gethostname()) + ":4444"


@contextmanager
def timeout_manager(timeout):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(timeout)

    try:
        yield
    except TimeoutError:
        pass
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


def raise_timeout(signum, frame):
    raise TimeoutError


def get_driver(headless: bool, tempdir: str, remote: Optional[str] = None):
    r"""Smart constructor for WebDriver

    Parameters
    ----------
    headless : bool
        Run the driver in headless mode
    tempdir : str
        Name of the directory to store downloads
    remote : Optional[str]
        If set, specifies the url of the selenium grid to connect on

    Returns
    -------
    WebDriver
    """
    # Create Chrome webdriver
    manager = ChromeDriverManager(driver_version="114.0.5735.90")
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": tempdir,
        "download.prompt_for_download": False,
    }

    options.add_experimental_option("prefs", prefs)
    if headless:
        try:
            # https://www.selenium.dev/blog/2023/headless-is-going-away/
            if version.parse(
                manager.driver.get_latest_release_version()
            ) < version.parse("109"):
                options.add_argument("--headless")
            else:
                options.add_argument("--headless=new")
        except:
            # `manager.driver.get_browser_version()` sometimes fails.
            # In that case, assume version prior to 109.
            options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")

    if remote is None:
        driver = webdriver.Chrome(options=options)
    else:
        if remote == "hostname":
            remote = get_ip_hostname()

        options.add_argument("--ignore-ssl-errors=yes")
        options.add_argument("--ignore-certificate-errors")
        driver = None
        with timeout_manager(30):
            driver = webdriver.Remote(remote, options=options)
        if driver is None:
            logger.error("Unable to reach Remote selenium webdriver")

    driver.set_window_size(1920, 1080)
    driver.maximize_window()
    return driver


class PPMIDownloader:
    """
    A downloader of PPMI metadata. Requires a PPMI account.
    See function download_metadata for usage.
    """

    file_ids_default_path = "study_data_to_checkbox_id.json"

    def __init__(
        self,
        config_file: str = ".ppmi_config",
        headless: bool = True,
        tempdir: str = "/tmp/",
        remote: Optional[str] = None,
    ) -> None:
        """Initialized PPMI downloader

        Set PPMI credentials by
        (1) looking in config file (default: .ppmi_config in current working directory),
        (2) looking in environment variables PPMI_LOGIN and PPMI_PASSWORD,
        (3) prompting the user.

        Optionally, the `PPMI_SINGULARITY_SELENIUM_REMOTE` environment variable can be
        set has a fallback for `remote`. The value should be set to "hostname".
        See also, `selenium_grid_utils::run` for more details.

        Parameters
        ----------
        config_file : str
            Name of the configuration file
        headless : bool
            Run the driver in headless mode
        tempdir : str
            Name of temporary directory for downloads
        remote : Optional[str]
            If set, specifies the url of the selenium grid to connect on

        """
        self.remote = remote
        if self.remote is None:
            self.remote = os.getenv("PPMI_SINGULARITY_SELENIUM_REMOTE")
        self.__set_credentials(config_file)
        self.tempdir = tempfile.TemporaryDirectory(dir=os.path.abspath(tempdir))
        self.driver = get_driver(
            headless=headless, tempdir=self.tempdir.name, remote=self.remote
        )
        self.html = PPMINavigator(self.driver)

        logger.debug(self.driver.capabilities)
        logger.debug(self.tempdir)

        # Load real metadata names
        self._get_real_name()

        # Ids of the download checkboxes in the PPMI metadata download page
        self.file_ids_path = Path(__file__).parent.joinpath(self.file_ids_default_path)
        if not self.file_ids_path.exists():
            self.crawl_study_data(cache_file=self.file_ids_path)

        with open(self.file_ids_path, "r", encoding="utf-8") as fin:
            self.file_ids = json.load(fin)

        logger.debug(self.config_file, config_file)

    def quit(self) -> None:
        r"""Quits the driver and removes temporary files"""
        self.tempdir.cleanup()
        self.driver.delete_all_cookies()
        self.driver.quit()

    def __del__(self):
        try:
            self.quit()
        except Exception:
            pass

    def __set_credentials(self, config_file: str) -> None:
        """Set PPMI credentials

        Set PPMI credentials by
        (1) looking in config file (default: .ppmi_config in current working directory)
        (2) looking in environment variables PPMI_LOGIN and PPMI_PASSWORD
        (3) prompting the user.

        Parameters
        ----------
        config_file : str
            Name of the configuration file
        """

        self.config_file = config_file

        # These variables will be set by the configuration
        login = None
        password = None

        read_config = False  # will set to True if credentials are read from config file

        # look in config file
        if op.exists(self.config_file):
            config = ConfigParser()
            config.read(self.config_file)
            login = config.get("ppmi", "login")
            password = config.get("ppmi", "password")
            read_config = True

        if login is None or password is None:
            # read environment variables
            login = os.environ.get("PPMI_LOGIN")
            password = os.environ.get("PPMI_PASSWORD")

        if login is None or password is None:
            # prompt user
            login = input("PPMI login: ")
            password = getpass.getpass("PPMI password: ")

        if not read_config:
            # write config file
            config = ConfigParser()
            config.read(self.config_file)
            config.add_section("ppmi")
            config.set("ppmi", "login", login)
            config.set("ppmi", "password", password)
            with open(self.config_file, "w") as f:
                config.write(f)

        self.email = login
        self.password = password

    def _get_real_name(self) -> None:
        """
        Initialize the attribute mapping guessed names from
        crawling PPMI to actual downloaded files.
        """
        cache_file = pkg_resources.resource_filename(
            "ppmi_downloader", "guessed_to_real.json"
        )

        with open(cache_file, "r", encoding="utf-8") as fi:
            self.guessed_to_real = json.load(fi)
            self.real_to_guessed = {v: k for k, v in self.guessed_to_real.items()}

    def init_and_log(self) -> None:
        """
        Initialize a driver, a ppmi navigator
        and login to ppmi portal
        """
        self.html.login(self.email, self.password)

    def crawl_checkboxes_id(self, soup):
        r"""Crawl for checboxes id and name

        Crawl the current page for checkboxes and associated name
        Print a warning if no checkbox is found
        """
        label_to_checkboxes_id = {}
        for checkbox in soup.find_all(type="checkbox"):
            if (checkbox_id := checkbox.get("id")) is not None:
                if (href := checkbox.findNext()) is not None:
                    name = href.text
                    if name == "" or name is None:
                        logger.warning(f"Found checkbox with no name {checkbox}")
                    else:
                        label_to_checkboxes_id[name.strip()] = checkbox_id
        return label_to_checkboxes_id

    def crawl_study_data(self, cache_file: str = "study_data_to_checkbox_id.json"):
        """
        Creates a mapping between Study data checkbox's name
        and their corresponding checkbox id
        """
        self.init_and_log()
        self.html.click_button_chain(["Download", "Study Data", "ALL"])
        soup = BeautifulSoup(self.driver.page_source, features="lxml")
        study_name_to_checkbox = self.crawl_checkboxes_id(soup)

        def clean_name(name):
            to_replace = {
                ord(c): "_"
                for c in (string.whitespace + string.punctuation).replace("-", "")
            }
            return str.translate(name, to_replace) + ".csv"

        study_name_to_checkbox_clean = {}
        for name, checkbox in study_name_to_checkbox.items():
            if checkbox.isdigit() and "Archived" not in name:
                study_name_to_checkbox_clean[clean_name(name)] = checkbox

        with open(cache_file, "w", encoding="utf-8") as fo:
            json.dump(study_name_to_checkbox_clean, fo, indent=0)

    def crawl_advanced_search(self, cache_file: str = "search_to_checkbox_id.json"):
        """
        Creates a mapping between Advances Search checkboxe's name
        and their corresponding checkbox id
        """
        self.init_and_log()
        self.driver.get(ppmi_query_page)
        soup = BeautifulSoup(self.driver.page_source, features="lxml")
        criteria_name_to_checkbox_id = self.crawl_checkboxes_id(soup)
        with open(cache_file, "w", encoding="utf-8") as fo:
            json.dump(criteria_name_to_checkbox_id, fo, indent=0)

    def download_imaging_data(
        self,
        cohort: pd.DataFrame,
        timeout: float = 600,
        destination_dir: str = ".",
    ):
        r"""Download all imaging data files from PPMI. Requires Google Chrome.

        Data is downloaded in the original format; usually DICOM.

        Parameters
        ----------
        cohort: pd.DataFrame
            cohort of subjects to download.
        timeout : bool
            file download timeout, in seconds
        destination_dir : str
            directory where to store the downloaded files
        """
        if len(cohort) == 0:
            return

        subjectIds = ",".join(cohort["PATNO"].astype(str).unique())

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        self.html.login(self.email, self.password)
        self.driver.get(ppmi_query_page)

        # Enter id's and add to collection
        self.html.enter_data("subjectIdText", subjectIds, By.ID)
        self.html.click_button("advSearchQuery", By.ID)
        self.html.Search_AdvancedImageSearchbeta_SelectAll()
        self.html.click_button("advResultAddCollectId", By.ID)
        # TODO If cohort already exist, don't create a new one.
        self.html.enter_data("nameText", cohort_id(cohort), By.ID)
        self.html.click_button("nameText", By.ID)
        self.html.Search_AdvancedImageSearchbeta_AddToCollection_OK()

        self.html.click_button("export", By.ID)

        # Select only required images.
        cohort_metadata = {
            (str(row["PATNO"]), str(row["EVENT_ID"]), str(row["Description"]))
            for _, row in cohort.iterrows()
        }
        print(cohort_metadata)
        prev_rows = None
        attempts = 0
        while attempts < 3:
            self.html.wait_for_element_to_be_visible("tableData", By.ID)
            table = self.driver.find_element(By.ID, "tableData")
            rows = table.find_elements(By.TAG_NAME, "tr")
            if rows == prev_rows:
                attempts += 1
            else:
                attempts = 0
                for row in rows:
                    metadata = tuple(
                        (
                            x.strip()
                            for i, x in enumerate(row.text.split("\n"))
                            if i in [0, 4, 6]
                        )
                    )
                    if metadata in cohort_metadata:
                        value = row.find_element(By.NAME, "checkbox").get_dom_attribute(
                            "value"
                        )
                        self.html.click_button(
                            f"//div[@id='tableData']//input[@value='{value}']"
                        )

                # Scroll down the table.
                # For some reason, there's a second button that appears with the crawler.
                # The first button doesn't work...
                scroll_down_button = self.driver.find_elements(
                    By.XPATH,
                    "//tbody[.//div[@id='slider']]//input[@alt='V' and @onclick]",
                )[1]
                ActionChains(self.driver).move_to_element(
                    scroll_down_button
                ).click().perform()
                self.driver.implicitly_wait(0.2)

            prev_rows = rows

        self.html.click_button("simple-download-button", By.ID)

        # Download imaging data and metadata
        # Try to click on download button for 2 minutes before timing out.
        self.html.click_button("Zip File", By.PARTIAL_LINK_TEXT, trials=24)
        self.html.click_button("Metadata", By.PARTIAL_LINK_TEXT)

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(self.tempdir.name)
            # assert len(downloaded_files) <= 3
            if len(downloaded_files) == 0:
                return False
            for f in downloaded_files:
                if f.endswith(".crdownload"):
                    filename = os.path.join(self.tempdir.name, f)
                    size = os.stat(filename).st_size
                    logger.debug("Size", size)
                    return False
            # assert f.endswith((".csv", ".zip", ".dcm", ".xml")), f
            return True

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=5).until(
                download_complete
            )
        except TimeoutException:
            self.quit()
            logger.error("Timeout when downloading imaging data")
        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(self.tempdir.name)

        # unzip files
        self.html.unzip_imaging_data(
            downloaded_files, self.tempdir.name, destination_dir
        )

    def download_3D_T1_info(self, timeout: float = 120, destination_dir: str = "."):
        r"""Download csv file containing information about available 3D MRIs

        Parameters
        ----------
        timeout : float
            file download timeout, in seconds
        destination_dir : str
            directory where to store the downloaded files

        """

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        # self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get(ppmi_query_page)

        # Click checkbox to display image ID.
        self.html.click_button("RESET_MODALITY.1", By.ID)
        # Click 3D checkbox
        self.html.click_button("imgProtocol_checkBox1.Acquisition_Type.3D", By.ID)
        # Click checkbox to display visit name in results
        self.html.click_button("RESET_VISIT.0", By.ID)
        # Click checkbox to display weighting in results
        self.html.click_button("RESET_PROTOCOL_STRING.1_Weighting", By.ID)
        # Click checkbox to display manufacturer in results
        self.html.click_button("RESET_PROTOCOL_STRING.1_Manufacturer", By.ID)
        # Click checkbox to display slice thickness in results
        self.html.click_button(
            "RESET_PROTOCOL_NUMERIC.imgProtocol_1_Slice_Thickness", By.ID
        )
        # Click checkbox to display manufacturer model in results
        self.html.click_button("RESET_PROTOCOL_STRING.1_Mfg_Model", By.ID)
        # Click checkbox to display study date in results
        self.html.click_button("RESET_STUDY.0", By.ID)
        # Click checkbox to display field strength in results
        self.html.click_button(
            "RESET_PROTOCOL_NUMERIC.imgProtocol_1_Field_Strength", By.ID
        )
        # Click checkbox to display acquisition plane in results
        self.html.click_button("RESET_PROTOCOL_STRING.1_Acquisition_Plane", By.ID)

        # Click search button
        self.html.click_button("advSearchQuery", By.ID)
        # Click CSV Download button
        self.html.click_button('//*[@type="button" and @value="CSV Download"]')

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(self.tempdir.name)
            # assert len(downloaded_files) <= 1
            if len(downloaded_files) == 0:
                return False
            for f in downloaded_files:
                if f.endswith(".crdownload"):
                    filename = os.path.join(self.tempdir.name, f)
                    size = os.stat(filename).st_size
                    logger.debug("Size", size)
                    return False
                if f.endswith(".csv"):
                    return True
            # assert f.endswith(".csv"), f"file ends with: {f}"
            return True

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=5).until(
                download_complete
            )
        except TimeoutException:
            self.quit()
            logger.error("Unable to download T1 3D information")

        # Move file to cwd or extract zip file
        file_name = self.html.unzip_metadata(self.tempdir.name, destination_dir)

        return file_name

    def download_fmri_info(self, timeout: float = 120, destination_dir: str = "."):
        r"""Download csv file containing information about available fMRIs

        Parameters
        ----------
        timeout : float
            file download timeout, in seconds
        destination_dir : str
            directory where to store the downloaded files

        """

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        # self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get(ppmi_query_page)

        # Click checkbox to display study date in results
        self.html.click_button("RESET_STUDY.0", By.ID)
        # Click checkbox to display visit name in results
        self.html.click_button("RESET_VISIT.0", By.ID)
        # Click checkbox to display image ID.
        self.html.click_button("RESET_MODALITY.1", By.ID)

        # Click fMRI checkbox and deselect MRI one.
        self.html.click_button(
            "//td[@id='imgModHolder']//td/input[@value='2']", By.XPATH
        )
        self.html.click_button(
            "//td[@id='imgModHolder']//td/input[@value='1']", By.XPATH
        )

        # Click checkbox to display field strength in results
        self.html.click_button(
            "RESET_PROTOCOL_NUMERIC.imgProtocol_2_Field_Strength", By.ID
        )
        # Click checkbox to display slice thickness in results
        self.html.click_button(
            "RESET_PROTOCOL_NUMERIC.imgProtocol_2_Slice_Thickness", By.ID
        )
        # Click checkbox to display TE in results
        self.html.click_button("RESET_PROTOCOL_NUMERIC.imgProtocol_2_TE", By.ID)
        # Click checkbox to display TR in results
        self.html.click_button("RESET_PROTOCOL_NUMERIC.imgProtocol_2_TR", By.ID)
        # Click checkbox to display manufacturer in results
        self.html.click_button("RESET_PROTOCOL_STRING.2_Manufacturer", By.ID)

        # Click search button
        self.html.click_button("advSearchQuery", By.ID)
        # Click CSV Download button
        self.html.click_button('//*[@type="button" and @value="CSV Download"]')

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(self.tempdir.name)
            # assert len(downloaded_files) <= 1
            if len(downloaded_files) == 0:
                return False
            for f in downloaded_files:
                if f.endswith(".crdownload"):
                    filename = os.path.join(self.tempdir.name, f)
                    size = os.stat(filename).st_size
                    logger.debug("Size", size)
                    return False
                if f.endswith(".csv"):
                    return True
            # assert f.endswith(".csv"), f"file ends with: {f}"
            return True

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=5).until(
                download_complete
            )
        except TimeoutException:
            self.quit()
            logger.error("Unable to download fMRI information")

        # Move file to cwd or extract zip file
        file_name = self.html.unzip_metadata(self.tempdir.name, destination_dir)

        return file_name

    def download_metadata(
        self,
        file_ids: str | List[str],
        timeout: float = 600,
        destination_dir: str = ".",
    ) -> None:
        """
        Download metadata files from PPMI. Requires Google Chrome.

        Parameters
        ----------
        file_ids: str | List[str]
          list of file ids included in self.file_ids.keys
        timeout : float
          file download timeout, in seconds
        destination_dir : str
          directory where to store the downloaded files
        """

        if not isinstance(file_ids, list):
            file_ids = [file_ids]

        supported_files = set(self.file_ids.keys()) | set(self.real_to_guessed.keys())
        for file_name in tqdm.tqdm(file_ids):
            if file_name not in supported_files:
                raise Exception(f"Unsupported file name: {file_name}.")

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        # self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get(ppmi_home_webpage)
        self.html.click_button_chain(["Download", "Study Data", "ALL"])

        # select file and download
        for file_name in file_ids:
            # Look for the guessed name
            # if not present, retrieve the guessed name from the real name
            checkbox_id = self.file_ids.get(file_name, None)
            if checkbox_id is None:
                guess = self.real_to_guessed[file_name]
                checkbox_id = self.file_ids.get(guess)
            for checkbox in self.driver.find_elements(By.ID, checkbox_id)[0:2]:
                logger.debug("Click checkbox", checkbox_id, file_name)
                checkbox.click()

        self.html.click_button("downloadBtn", By.ID)

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(self.tempdir.name)
            # assert len(downloaded_files) <= 1
            if len(downloaded_files) == 0:
                return False
            for f in downloaded_files:
                if f.endswith(".crdownload"):
                    filename = os.path.join(self.tempdir.name, f)
                    size = os.stat(filename).st_size
                    logger.debug("Size", size)
                    return False
            # assert f.endswith((".csv", ".zip")), f"file ends with: {f}"
            return True

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=5).until(
                download_complete
            )
        except TimeoutException as e:
            self.quit()
            raise e

        # Move file to cwd or extract zip file
        self.html.unzip_metadata(self.tempdir.name, destination_dir)
