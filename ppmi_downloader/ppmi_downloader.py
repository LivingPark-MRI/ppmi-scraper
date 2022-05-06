import os
from os import path as op
import tempfile
import time
import shutil
import zipfile
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

def get_driver(headless, tempdir):
    # Create Chrome webdriver
    options = webdriver.ChromeOptions()
    prefs = {'download.default_directory': tempdir}
    options.add_experimental_option("prefs", prefs)
    if headless:
        options.add_argument("--headless")

    return webdriver.Chrome(ChromeDriverManager().install(), chrome_options=options)

class PPMIDownloader():
    '''
    A downloader of PPMI metadata. Requires a PPMI account.
    See function download_metadata for usage.
    '''

    def __init__(self, email, password):
        '''
        Positional arguments:
        * email: PPMI account email address
        * password: PPMI account password
        '''
        # Ids of the download checkboxes in the PPMI metadata download page
        self.file_ids = {
            'Demographics.csv': 2544,
            'Age_at_visit.csv': 2834,
            'REM_Sleep_Behavior_Disorder_Questionnaire.csv': 2472,
            'Magnetic_Resonance_Imaging__MRI_.csv': 2655,
            'MDS_UPDRS_Part_III.csv': 2796,
            'Socio-Economics.csv': 2576,
            'Montreal_Cognitive_Assessment__MoCA_.csv': 2712
        }
        self.email = email
        self.password = password

    def download_imaging_data(self, subject_ids,
                            headless=True, timeout=600, destination_dir='.'):
        '''
        Download all imaging data files from PPMI. Requires Google Chrome.

        Positional arguments
        * subject_ids: list of subject ids

        Keyword arguments:
        * headless: if False, run Chrome not headless
        * timeout: file download timeout, in seconds
        * destination_dir: directory where to store the downloaded files
        '''

        subjectIds = ','.join([str(i) for i in subject_ids])

        # Create Chrome webdriver
        tempdir = op.abspath(tempfile.mkdtemp(dir='.'))
        self.driver = get_driver(headless, tempdir)

        # Login to PPMI
        self.driver.get('https://ida.loni.usc.edu/login.jsp?project=PPMI')
        self.html = HTMLHelper(self.driver)
        self.html.login(self.email, self.password)

        # navigate to search page
        self.driver.get('https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI')
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
        self.html.enter_data('//*[@id="nameText"]', "images")
        time.sleep(3)
        self.html.click_button('//*[text()="OK"]')
        time.sleep(2)
        self.html.click_button('//*[@id="selectAllCheckBox"]')
        time.sleep(2)
        self.html.click_button('//*[@id="simple-download-button"]')

        # Download imaging data and metadata
        self.html.click_button('//*[@id="simple-download-link"]')
        time.sleep(2)
        self.html.click_button(('//*[@class="simple-download-metadata-link-text singlefile-download-metadata-link"]'))

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert(len(downloaded_files) <= 2)
            if len(downloaded_files) == 0:
                return False
            f = downloaded_files[0]
            if f.endswith('.crdownload'):
                return False
            assert(f.endswith('.csv') or f.endswith('.zip') or f.endswith('.dcm'))
            return True
        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(tempdir)

        # we got imaging data and metadata
        assert(len(downloaded_files) == 2)

        # unzip files
        self.html.unzip_imaging_data(downloaded_files, tempdir, destination_dir)
        
        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

    def download_metadata(self, file_ids,
                          headless=True, timeout=120, destination_dir='.'):
        '''
        Download metadata files from PPMI. Requires Google Chrome.

        Positional arguments
        * file_ids: list of file ids included in self.file_ids.keys

        Keyword arguments:
        * headless: if False, run Chrome not headless
        * timeout: file download timeout, in seconds
        * destination_dir: directory where to store the downloaded files
        '''

        if not type(file_ids) is list:
            file_ids = [file_ids]

        for file_name in file_ids:
            if file_name not in self.file_ids:
                raise Exception(f'Unsupported file name: {file_name}.'
                                f'Supported files: {file_ids.keys}')

        # Create Chrome webdriver
        tempdir = op.abspath(tempfile.mkdtemp(dir='.'))
        self.driver = get_driver(headless, tempdir)

        # Login to PPMI
        self.driver.get('https://ida.loni.usc.edu/login.jsp?project=PPMI')
        self.html = HTMLHelper(self.driver)
        self.html.login(self.email, self.password)

        # navigate to metadata page
        self.driver.get('https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI')
        self.html.click_button("//a[text()='Download']")
        self.html.click_button("//a[text()='Study Data']")
        self.html.click_button('//*[@id="ygtvlabelel56"]')

        # select file and download
        for file_name in file_ids:
            xpath = f'//input[@id={self.file_ids[file_name]}]'
            for checkbox in self.driver.find_elements_by_xpath(xpath)[0:2]:
                checkbox.click()
        self.html.click_button('//*[@id="downloadBtn"]')

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert(len(downloaded_files) <= 1)
            if len(downloaded_files) == 0:
                return False
            f = downloaded_files[0]
            if f.endswith('.crdownload'):
                return False
            assert(f.endswith('.csv') or f.endswith('.zip')), f"file ends with: {f}"
            return True
        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        self.html.unzip_metadata(tempdir, destination_dir)
        
        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

    def _login(self, email, password):
        password_field = '/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[1]/div[2]/div/div/input'
        email_field = '/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[1]/div[1]/div/div/input'
        self.html.enter_data(email_field, email)
        self.html.enter_data(password_field, password)
        self.html.click_button('/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[2]/span')


class HTMLHelper():

    def __init__(self, driver) -> None:
        self.driver = driver

    def enter_data(self, field, data):
        try:
            self.driver.find_element_by_xpath(field).send_keys(data)
            pass
        except Exception as e:
            print(e)
            time.sleep(1)
            self.enter_data(field, data)

    def click_button(self, xpath):
        try:
            self.driver.find_element_by_xpath(xpath).click()
            pass
        except Exception:
            time.sleep(1)
            self.click_button(xpath)

    def login(self, email, password):
        self.driver.get('https://ida.loni.usc.edu/login.jsp?project=PPMI')
        self.click_button("//div[contains(@class,'ida-cookie-policy-accept')]")
        self.click_button("//div[contains(@class,'ida-user-menu-icon')]")
        
        password_field = '/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[1]/div[2]/div/div/input'
        email_field = '/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[1]/div[1]/div/div/input'
        self.enter_data(email_field, email)
        self.enter_data(password_field, password)
        self.click_button('/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[2]/span')

    def unzip_metadata(self, tempdir, destination_dir):
        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(tempdir)
        # we got either a csv or a zip file
        assert(len(downloaded_files) == 1)
        file_name = downloaded_files[0]
        assert(file_name.endswith('.zip') or file_name.endswith('.csv'))

        if file_name.endswith('.zip'):
            # unzip file to cwd
            with zipfile.ZipFile(op.join(tempdir, file_name), 'r') as zip_ref:
                zip_ref.extractall(destination_dir)
                print(f'Successfully downloaded files {zip_ref.namelist()}')
        else:
            os.rename(op.join(tempdir, file_name),
                      op.join(destination_dir, file_name))
            print(f'Successfully downloaded file {file_name}')

    def unzip_imaging_data(self, downloaded_files, tempdir, destination_dir):
        for file_name in downloaded_files:
            assert(file_name.endswith('.zip') or file_name.endswith('.csv') or file_name.endswith('.dcm'))
            if file_name.endswith('.zip'):
                # unzip file to cwd
                with zipfile.ZipFile(op.join(tempdir, file_name), 'r') as zip_ref:
                    zip_ref.extractall(destination_dir)
                    print(f'Successfully downloaded files {zip_ref.namelist()}')
            else:
                os.rename(op.join(tempdir, file_name),
                        op.join(destination_dir, file_name))
                print(f'Successfully downloaded file {file_name}')
