import time
import getpass
import glob
import json
import os
import os.path as op
import shutil
import string
import tempfile
import xml.etree.ElementTree as ET
from configparser import ConfigParser
from pathlib import Path

import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import ppmi_downloader.ppmi_logger as logger
from ppmi_downloader.ppmi_navigator import (PPMINavigator,
                                            ppmi_main_webpage,
                                            ppmi_home_webpage)


def get_driver(headless, tempdir):
    # Create Chrome webdriver
    options = webdriver.ChromeOptions()
    prefs = {"download.default_directory": tempdir}
    options.add_experimental_option("prefs", prefs)
    if headless:
        options.add_argument("--headless")
    driver = webdriver.Chrome(
        ChromeDriverManager().install(), chrome_options=options)

    driver.set_window_size(1200, 720)
    driver.maximize_window()
    return driver


class PPMIDownloader:
    """
    A downloader of PPMI metadata. Requires a PPMI account.
    See function download_metadata for usage.
    """

    file_ids_default_path = 'file_id.json'

    def __init__(self, config_file=".ppmi_config"):
        """
        Initializes PPMI downloader. Set PPMI credentials by (1) looking in
        config file (default: .ppmi_config in current working directory),
        (2) looking in environment variables PPMI_LOGIN and PPMI_PASSWORD,
        (3) prompting the user.
        """
        self.__set_credentials()

        # Ids of the download checkboxes in the PPMI metadata download page
        file_ids_path = Path(__file__).parent.joinpath(
            self.file_ids_default_path)
        if not file_ids_path.exists():
            self.crawl_study_data(cache_file=file_ids_path)

        with open(file_ids_path, 'r', encoding='utf-8') as fin:
            self.file_ids = json.load(fin)
        self.config_file = config_file

        logger.debug(self.config_file, config_file)

    def __del__(self):
        if hasattr(self, "driver"):
            self.driver.close()

    def __set_credentials(self):
        """
        Set PPMI credentials by (1) looking in config file (default:
        .ppmi_config in current working directory), (2) looking in
        environment variables PPMI_LOGIN and PPMI_PASSWORD, (3) prompting
        the user.
        """

        # These variables will be set by the configuration
        login = None
        password = None

        read_config = False  # will set to True if credentials are read from config file
        logger.debug(self.config_file)

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

    def init_and_log(self, headless=True):
        '''
        Initialize a driver, a ppmi navigator
        and login to ppmi portal
        '''
        tempdir = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.driver = get_driver(headless, tempdir.name)
        self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

    def crawl_checkboxes_id(self, soup):
        label_to_checkboxes_id = {}
        for checkbox in soup.find_all(type='checkbox'):
            if (checkbox_id := checkbox.get('id')) is not None:
                if (href := checkbox.findNext()) is not None:
                    name = href.text
                    if name == '' or name is None:
                        logger.warning(
                            f'Found checkbox with no name {checkbox}')
                    else:
                        label_to_checkboxes_id[name.strip()] = checkbox_id
        return label_to_checkboxes_id

    def crawl_study_data(self,
                         cache_file='study_data_to_checkbox_id.json',
                         headless=True):
        '''
        Creates a mapping between Study data checkbox's name
        and their corresponding checkbox id
        '''
        self.init_and_log(headless=headless)
        self.html.click_button_chain(['Download', 'Study Data', 'ALL'])
        soup = BeautifulSoup(self.driver.page_source, features='lxml')
        study_name_to_checkbox = self.crawl_checkboxes_id(soup)

        def clean_name(name):
            allow = string.ascii_letters + string.digits
            cleaned = [''.join([c for c in token if c in allow])
                       for token in name.split()]
            return '_'.join(cleaned) + '.csv'

        study_name_to_checkbox_clean = {}
        for name, checkbox in study_name_to_checkbox.items():
            study_name_to_checkbox_clean[clean_name(name)] = checkbox

        with open(cache_file, 'w', encoding='utf-8') as fo:
            json.dump(study_name_to_checkbox_clean, fo, indent=0)

        self.driver.close()

    def crawl_advanced_search(self,
                              cache_file='search_to_checkbox_id.json',
                              headless=True):
        '''
        Creates a mapping between Advances Search checkboxe's name
        and their corresponding checkbox id
        '''
        self.init_and_log(headless=headless)
        self.html.click_button_chain(['Search',
                                      'Advanced Image Search (beta)'])
        soup = BeautifulSoup(self.driver.page_source, features='lxml')
        criteria_name_to_checkbox_id = self.crawl_checkboxes_id(soup)
        with open(cache_file, 'w', encoding='utf-8') as fo:
            json.dump(criteria_name_to_checkbox_id, fo, indent=0)

        self.driver.close()

    def download_imaging_data(
        self,
        subject_ids,
        headless=True,
        timeout=600,
        destination_dir=".",
        type="archived",
    ):
        """
        Download all imaging data files from PPMI. Requires Google Chrome.

        Positional arguments
        * subject_ids: list of subject ids

        Keyword arguments:
        * headless: if False, run Chrome not headless
        * timeout: file download timeout, in seconds
        * destination_dir: directory where to store the downloaded files
        * type: can be 'archived' or 'nifti'. Archived means that the images are
        downloaded as archived in the PPMI database, which usually means in DICOM format.
        """
        assert type in (
            "archived",
            "nifti",
        ), f'Invalid type: {type}. Only "archived" and "nifti" are supported'

        if len(subject_ids) == 0:
            return

        subjectIds = ",".join([str(i) for i in subject_ids])

        # Create Chrome webdriver
        tempdir = op.abspath(tempfile.mkdtemp(dir="."))
        self.driver = get_driver(headless, tempdir)

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

        # navigate to search page
        self.driver.get(ppmi_home_webpage)
        # click on 'Search'
        # Click on 'Advanced Image Search (beta)'
        self.html.click_button_chain(
            ['Search', 'Advanced Image Search (beta)'])

        # Enter id's and add to collection
        self.html.enter_data('subjectIdText', subjectIds, By.ID)
        self.html.click_button("advSearchQuery", By.ID)
        self.html.Search_AdvancedImageSearchbeta_SelectAll()
        # self.html.click_button("advResultSelectAll", By.ID)
        self.html.click_button("advResultAddCollectId", By.ID)
        self.html.enter_data("nameText",
                             f"images-{op.basename(tempdir)}", By.ID)
        self.html.click_button('nameText', By.ID)
        self.html.Search_AdvancedImageSearchbeta_AddToCollection_OK()

        self.html.click_button("export", By.ID)
        self.html.click_button("selectAllCheckBox", By.ID)
        if type == "nifti":
            self.html.click_button("niftiButton", By.ID)
        elif type == "archived":
            self.html.click_button("archivedButton", By.ID)
        self.html.click_button("simple-download-button", By.ID)

        # Download imaging data and metadata
        self.html.click_button("simple-download-link", By.ID)
        self.html.click_button(
            (
                '//*[@class="simple-download-metadata-link-text singlefile-download-metadata-link"]'
            )
        )

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert len(downloaded_files) <= 3
            if len(downloaded_files) == 0:
                return False
            for f in downloaded_files:
                if f.endswith(".crdownload"):
                    return False
            assert f.endswith(('.csv', '.zip', '.dcm', '.xml')), f
            return True

        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(tempdir)

        # we got imaging data and metadata
        assert len(downloaded_files) == 3

        # unzip files
        self.html.unzip_imaging_data(
            downloaded_files, tempdir, destination_dir)

        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

    def download_3D_T1_info(self, headless=True, timeout=120, destination_dir="."):
        """
        Download csv file containing information about available 3D MRIs

        Keyword arguments:
        * headless: if False, run Chrome not headless
        * timeout: file download timeout, in seconds
        * destination_dir: directory where to store the downloaded files
        """
        # Create Chrome webdriver
        tempdir = op.abspath(tempfile.mkdtemp(dir="."))
        self.driver = get_driver(headless, tempdir)

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get(ppmi_home_webpage)
        self.html.click_button_chain(
            ['Search', 'Advanced Image Search (beta)'])

        # Click 3D checkbox
        self.html.click_button(
            "imgProtocol_checkBox1.Acquisition_Type.3D", By.ID)
        # Click T1 checkbox
        self.html.click_button("imgProtocol_checkBox1.Weighting.T1", By.ID)
        # Click checkbox to display visit name in results
        self.html.click_button("RESET_VISIT.0", By.ID)
        # Click checkbox to display study date in results
        self.html.click_button("RESET_STUDY.0", By.ID)
        # Click checkbox to display field strength in results
        self.html.click_button(
            "RESET_PROTOCOL_NUMERIC.imgProtocol_1_Field_Strength", By.ID)
        # Click checkbox to display acquisition plane in results
        self.html.click_button("RESET_PROTOCOL_STRING.1_Acquisition_Plane",
                               By.ID)

        # Click search button
        self.html.click_button("advSearchQuery", By.ID)
        # Click CSV Download button
        self.html.click_button('//*[@type="button" and @value="CSV Download"]')

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert len(downloaded_files) <= 1
            if len(downloaded_files) == 0:
                return False
            f = downloaded_files[0]
            if f.endswith(".crdownload"):
                return False
            assert f.endswith(".csv"), f"file ends with: {f}"
            return True

        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        file_name = self.html.unzip_metadata(tempdir, destination_dir)

        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

        return file_name

    def download_metadata(
        self, file_ids, headless=True, timeout=120, destination_dir="."
    ):
        """
          Download metadata files from PPMI. Requires Google Chrome.

          Positional arguments
          * file_ids: list of file ids included in self.file_ids.keys

          Keyword arguments:
          * headless: if False, run Chrome not headless
          * timeout: file download timeout, in seconds
          * destination_dir: directory where to store the downloaded files
          """

        if not type(file_ids) is list:
            file_ids = [file_ids]

        for file_name in tqdm.tqdm(file_ids):
            if file_name not in self.file_ids:
                raise Exception(
                    f"Unsupported file name: {file_name}."
                    f"Supported files: {self.file_ids}"
                )

        # Create Chrome webdriver
        tempdir = op.abspath(tempfile.mkdtemp(dir="."))

        self.driver = get_driver(headless, tempdir)

        # Login to PPMI
        self.driver.get(ppmi_main_webpage)
        self.html = PPMINavigator(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get(ppmi_home_webpage)
        self.html.click_button_chain(['Download', 'Study Data', 'ALL'])

        # select file and download
        for file_name in file_ids:
            for checkbox in self.driver.find_elements(By.ID, self.file_ids[file_name])[
                0:2
            ]:
                checkbox.click()
        self.html.click_button("downloadBtn", By.ID)

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert len(downloaded_files) <= 1
            if len(downloaded_files) == 0:
                return False
            f = downloaded_files[0]
            if f.endswith(".crdownload"):
                return False
            assert f.endswith(".csv") or f.endswith(
                ".zip"), f"file ends with: {f}"
            return True

        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        self.html.unzip_metadata(tempdir, destination_dir)

        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)


class PPMINiftiFileFinder:
    """
    A class to find a Nifti file by subject ID, visit ID and protocol description
    from a PPMI image collection. See function find_nifti for detailed usage.
    """

    def __init__(self, download_dir="PPMI"):
        self.download_dir = download_dir
        # Mapping between Study Data Event IDs and imaging visit names
        self.visit_map = {
            "SC": "Screening",
            "BL": "Baseline",
            "V04": "Month 12",
            "V06": "Month 24",
            "V08": "Month 36",
            "V10": "Month 48",
            "ST": "Symptomatic Therapy",
            "U01": "Unscheduled Visit 01",
            "U02": "Unscheduled Visit 02",
            "PW": "Premature Withdrawal",
        }

    def __parse_xml_metadata(self, xml_file):
        """
        Return (subject_id, visit_id, study_id, series_id, image_id, description) from XML metadata file.

        Parameter:
        * xml_file: PPMI XML image metadata file. Such files come with PPMI image collections.

        Returned values:
        * subject_id: Subject ID associated with the image.
        * visit_id: Visit id of the image. Example: "Month 24".
        * study_id: Study id of the image. Example: 12345.
        * series_id: Series id of the image. Example: 123456.
        * image_id: Image id of the image. Example: 123456.
        * description: Protocol description of the image. Example: "MPRAGE GRAPPA"
        """
        tree = ET.parse(xml_file)
        root = tree.getroot()

        def parse_series(series):
            assert series.tag == "series", xml_file
            for child in series:
                if child.tag == "seriesIdentifier":
                    return child.text

        def parse_protocol(protocol):
            assert protocol.tag == "imagingProtocol", xml_file
            for child in protocol:
                if child.tag == "imageUID":
                    image_id = child.text
                if child.tag == "description":
                    description = child.text
            return (image_id, description)

        def parse_study(study):
            assert study.tag == "study", xml_file
            for study_child in study:
                if study_child.tag == "studyIdentifier":
                    study_id = study_child.text
                if study_child.tag == "series":
                    series_id = parse_series(study_child)
                if study_child.tag == "imagingProtocol":
                    image_id, description = parse_protocol(study_child)
            return (study_id, series_id, image_id, description)

        def parse_visit(visit):
            assert visit.tag == "visit", xml_file
            for visit_child in visit:
                if visit_child.tag == "visitIdentifier":
                    return visit_child.text
            raise Exception(f"Visit identifier not found in visit {visit}")

        def parse_subject(subject):
            assert subject.tag == "subject", xml_file
            subject_id, visit_id, study_id, series_id, image_id, description = (
                None for x in range(6)
            )
            for child in subject:
                if child.tag == "subjectIdentifier":
                    subject_id = child.text
                if child.tag == "visit":
                    visit_id = parse_visit(child)
                if child.tag == "study":
                    study_id, series_id, image_id, description = parse_study(
                        child)
            assert not None in (
                subject_id,
                visit_id,
                study_id,
                series_id,
                image_id,
                description,
            )
            return (subject_id, visit_id, study_id, series_id, image_id, description)

        for project in root:
            if project.tag == "project":
                for child in project:
                    if child.tag == "subject":
                        return parse_subject(child)
        raise Exception(
            "Malformed XML document"
        )  # TODO: it'd be nice to have an XML schema to validate the file against

    def find_nifti(self, subject_id, event_id, description):
        """
        Find the nifti file associated with subject, event and protocol description
        in the finder's download directory.
        Raise an exception if file is not found: make sure you know what you're looking for!

        Parameters:
        * subject_id: Subject id of the sought file.
        * event_id: Event id of the file. Example: "V06". Warning: this is not the
         image visit id but a one-to-one mapping exists (see self.visit_map).
        * description: Protocol description of the file. Example: "MPRAGE GRAPPA".

        Return values:
        * Nifti file path corresponding to the subject, event, and protocol description.
        * None if no file path is found
        """

        def clean_desc(desc):
            return (
                desc.replace(" ", "_")
                .replace("(", "_")
                .replace(")", "_")
                .replace("/", "_")
            )

        subject_id = str(subject_id)

        # Find metadata file for subject, event and description
        expression = op.join(self.download_dir, f"PPMI_{subject_id}_*.xml")
        xml_files = glob.glob(expression)
        # print(f'Found {len(xml_files)} metadata files to inspect')

        for xml_file in xml_files:
            (
                s_id,
                visit_id,
                study_id,
                series_id,
                image_id,
                descr,
            ) = self.__parse_xml_metadata(xml_file)
            if (
                (subject_id == s_id)
                and (self.visit_map[event_id] == visit_id)
                and (description == descr)
            ):
                expression = op.join(
                    self.download_dir,
                    subject_id,
                    clean_desc(description),
                    "*",
                    f"S{series_id}",
                    f"PPMI_{subject_id}_MR_*_S{series_id}_I{image_id}.nii",
                )
                files = glob.glob(expression)
                assert (
                    len(files) == 1
                ), f"Found {len(files)} files matching {expression} while exactly 1 was expected"
                file_name = files[0]
                assert op.exists(file_name), "This should never happen :)"
                return file_name
            # else:
            #     print(f'File {xml_file} is for {(s_id, visit_id, study_id, series_id, image_id, descr)} while we are looking for {subject_id, self.visit_map[event_id], description}')

        return None
        # raise Exception(
        #     f"Did not find any nifti file for subject {subject_id}, event {event_id} and protocol description {description}"
        # )
