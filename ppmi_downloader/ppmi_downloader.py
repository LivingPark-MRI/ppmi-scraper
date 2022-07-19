import os
from os import path as op
import getpass
import tempfile
import time
import shutil
import zipfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from configparser import SafeConfigParser
import glob
import xml.etree.ElementTree as ET
import os.path as op
from pathlib import Path


def get_driver(headless, tempdir):
    # Create Chrome webdriver
    options = webdriver.ChromeOptions()
    prefs = {"download.default_directory": tempdir}
    options.add_experimental_option("prefs", prefs)
    if headless:
        options.add_argument("--headless")

    return webdriver.Chrome(ChromeDriverManager().install(), chrome_options=options)


class PPMIDownloader:
    """
    A downloader of PPMI metadata. Requires a PPMI account.
    See function download_metadata for usage.
    """

    def __init__(self, config_file=".ppmi_config"):
        """
        Initializes PPMI downloader. Set PPMI credentials by (1) looking in
        config file (default: .ppmi_config in current working directory),
        (2) looking in environment variables PPMI_LOGIN and PPMI_PASSWORD,
        (3) prompting the user.
        """
        # Ids of the download checkboxes in the PPMI metadata download page
        self.file_ids = {
            "Demographics.csv": 2544,
            "Age_at_visit.csv": 2834,
            "REM_Sleep_Behavior_Disorder_Questionnaire.csv": 2472,
            "Magnetic_Resonance_Imaging__MRI_.csv": 2655,
            "MDS_UPDRS_Part_III.csv": 2796,
            "Socio-Economics.csv": 2576,
            "Montreal_Cognitive_Assessment__MoCA_.csv": 2712,
            "Age_of_Parkinson_s_Disease_Diagnosis__Online_.csv": 2853,
            "PD_Diagnosis_History.csv": 2588,
            "PPMI_Original_Cohort_BL_to_Year_5_Dataset_Apr2020.csv": 2203,
            "Participant_Status.csv": 2543,
            "Inclusion_Exclusion.csv": 2696,
            "Inclusion_Exclusion-Archived.csv": 34,
            "Concomitant_Medication_Log.csv": 2701,
            "MRI_Metadata.csv": 2583,
            "Cognitive_Categorization.csv": 2708,
        }
        self.config_file = config_file
        self.__set_credentials()

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

        # look in config file
        if op.exists(self.config_file):
            config = SafeConfigParser()
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
            config = SafeConfigParser()
            config.read(self.config_file)
            config.add_section("ppmi")
            config.set("ppmi", "login", login)
            config.set("ppmi", "password", password)
            with open(self.config_file, "w") as f:
                config.write(f)

        self.email = login
        self.password = password

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
        * type: can be 'archived' or 'nifti'. Archived means that the images are downloaded as archived in the PPMI database, which usually means in DICOM format.
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
        self.driver.get("https://ida.loni.usc.edu/login.jsp?project=PPMI")
        self.html = HTMLHelper(self.driver)
        self.html.login(self.email, self.password)

        # navigate to search page
        self.driver.get("https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI")
        self.html.click_button("//a[text()='SEARCH']")
        self.html.click_button("//a[text()='Advanced Image Search (beta)']")
        time.sleep(2)

        # Enter id's and add to collection
        self.html.enter_data('//*[@id="subjectIdText"]', subjectIds)
        time.sleep(2)
        self.html.click_button('//*[@id="advSearchQuery"]')
        time.sleep(2)
        self.html.click_button('//*[@id="advResultSelectAll"]')
        time.sleep(3)
        self.html.click_button('//*[@id="advResultAddCollectId"]')
        time.sleep(2)
        self.html.enter_data('//*[@id="nameText"]', f"images-{op.basename(tempdir)}")
        time.sleep(3)
        self.html.click_button('//*[text()="OK"]')
        time.sleep(2)
        self.html.click_button('//*[@id="export"]')
        time.sleep(2)
        self.html.click_button('//*[@id="selectAllCheckBox"]')
        time.sleep(2)
        if type == "nifti":
            self.html.click_button('//*[@id="niftiButton"]')
        elif type == "archived":
            self.html.click_button('//*[@id="archivedButton"]')
        self.html.click_button('//*[@id="simple-download-button"]')

        # Download imaging data and metadata
        self.html.click_button('//*[@id="simple-download-link"]')
        time.sleep(2)
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
            assert (
                f.endswith(".csv")
                or f.endswith(".zip")
                or f.endswith(".dcm")
                or f.endswith(".xml")
            ), f
            return True

        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(tempdir)

        # we got imaging data and metadata
        assert len(downloaded_files) == 3

        # unzip files
        self.html.unzip_imaging_data(downloaded_files, tempdir, destination_dir)

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
        self.driver.get("https://ida.loni.usc.edu/login.jsp?project=PPMI")
        self.html = HTMLHelper(self.driver)
        self.html.login(self.email, self.password)
        print("after login")

        # navigate to metadata page
        self.driver.get("https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI")
        self.html.click_button("//a[text()='Download']")
        self.html.click_button("//a[text()='Image Collections']")
        # Click Advanced Search button
        self.html.click_button(
            "/html/body/div[3]/table/tbody/tr[2]/td/div/ul/li[2]/a/em/font"
        )
        # Click 3D checkbox
        self.html.click_button('//*[@id="imgProtocol_checkBox1.Acquisition_Type.3D"]')
        # Click T1 checkbox
        self.html.click_button('//*[@id="imgProtocol_checkBox1.Weighting.T1"]')
        # Click checkbox to display visit name in resuls
        self.html.click_button('//*[@id="RESET_VISIT.0"]')

        # Click search button
        self.html.click_button('//*[@id="advSearchQuery"]')
        # Click CSV Download button
        self.html.click_button(
            "/html/body/div[2]/table/tbody/tr[2]/td/div/div/div[3]/form/table/tbody/tr/td[2]/table[1]/tbody/tr/td/table/tbody/tr/td[3]/table/tbody/tr/td[5]/input"
        )

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

        for file_name in file_ids:
            if file_name not in self.file_ids:
                raise Exception(
                    f"Unsupported file name: {file_name}."
                    f"Supported files: {self.file_ids}"
                )

        # Create Chrome webdriver
        tempdir = op.abspath(tempfile.mkdtemp(dir="."))
        self.driver = get_driver(headless, tempdir)

        # Login to PPMI
        self.driver.get("https://ida.loni.usc.edu/login.jsp?project=PPMI")
        self.html = HTMLHelper(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get("https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI")
        self.html.click_button("//a[text()='Download']")
        self.html.click_button("//a[text()='Study Data']")
        self.html.click_button('//*[@id="ygtvlabelel71"]')

        # select file and download
        for file_name in file_ids:
            xpath = f"//input[@id={self.file_ids[file_name]}]"
            for checkbox in self.driver.find_elements(By.XPATH, xpath)[0:2]:
                checkbox.click()
        self.html.click_button('//*[@id="downloadBtn"]')

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert len(downloaded_files) <= 1
            if len(downloaded_files) == 0:
                return False
            f = downloaded_files[0]
            if f.endswith(".crdownload"):
                return False
            assert f.endswith(".csv") or f.endswith(".zip"), f"file ends with: {f}"
            return True

        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        self.html.unzip_metadata(tempdir, destination_dir)

        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)


class HTMLHelper:
    def __init__(self, driver) -> None:
        self.driver = driver

    def enter_data(self, field, data, BY=By.XPATH):
        try:
            self.driver.find_element(BY, field).send_keys(data)
            pass
        except Exception as e:
            print(e)
            time.sleep(1)
            self.enter_data(field, data, BY=BY)

    def click_button(self, field, BY=By.XPATH):
        try:
            self.driver.find_element(BY, field).click()
            pass
        except Exception:
            time.sleep(1)
            self.click_button(field, BY=BY)

    def login(self, email, password):
        self.driver.get("https://ida.loni.usc.edu/login.jsp?project=PPMI")
        self.click_button("ida-cookie-policy-accept", BY=By.CLASS_NAME)
        self.click_button("ida-user-menu-icon", BY=By.CLASS_NAME)

        self.enter_data("userEmail", email, BY=By.NAME)
        self.enter_data("userPassword", password, BY=By.NAME)
        self.click_button(
            "/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[2]/span"
        )

    def unzip_metadata(self, tempdir, destination_dir):
        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(tempdir)
        # we got either a csv or a zip file
        assert len(downloaded_files) == 1
        file_name = downloaded_files[0]
        assert file_name.endswith(".zip") or file_name.endswith(".csv")

        if file_name.endswith(".zip"):
            # unzip file to cwd
            with zipfile.ZipFile(op.join(tempdir, file_name), "r") as zip_ref:
                zip_ref.extractall(destination_dir)
                print(f"Successfully downloaded files {zip_ref.namelist()[:2]}...")
        else:
            os.rename(op.join(tempdir, file_name), op.join(destination_dir, file_name))
            print(f"Successfully downloaded file {file_name}")
        return file_name

    def unzip_imaging_data(self, downloaded_files, tempdir, destination_dir):
        for file_name in downloaded_files:
            assert (
                file_name.endswith(".zip")
                or file_name.endswith(".csv")
                or file_name.endswith(".dcm")
                or file_name.endswith(".xml")
            ), file_name
            if file_name.endswith(".zip"):
                # unzip file to cwd
                with zipfile.ZipFile(op.join(tempdir, file_name), "r") as zip_ref:
                    zip_ref.extractall(destination_dir)
                    print(f"Successfully downloaded files {zip_ref.namelist()[:2]}...")
            else:
                os.rename(
                    op.join(tempdir, file_name), op.join(destination_dir, file_name)
                )
                print(f"Successfully downloaded file {file_name}")
        return downloaded_files


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
                    study_id, series_id, image_id, description = parse_study(child)
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
        Find the nifti file associated with subject, event and protocol description in the finder's download directory.
        Raise an exception if file is not found: make sure you know what you're looking for!

        Parameters:
        * subject_id: Subject id of the sought file.
        * event_id: Event id of the file. Example: "V06". Warning: this is not the image visit id but a one-to-one mapping exists (see self.visit_map).
        * description: Protocol description of the file. Example: "MPRAGE GRAPPA".

        Return values:
        * Nifti file path corresponding to the subject, event, and protocol description.
        * None if no file path is found
        """

        def clean_desc(desc):
            return desc.replace(" ", "_").replace("(", "_").replace(")", "_").replace("/", "_")

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
