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
from configparser import SafeConfigParser

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

    def __init__(self, config_file='.ppmi_config'):
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
            'Montreal_Cognitive_Assessment__MoCA_.csv': 2712,
            'Age_of_Parkinson_s_Disease_Diagnosis__Online_.csv': 2853,
            'PD_Diagnosis_History.csv': 2588,
            'PPMI_Original_Cohort_BL_to_Year_5_Dataset_Apr2020.csv': 2203,
            'Participant_Status.csv' : 2543,
            'Inclusion_Exclusion.csv': 2696,
            'Inclusion_Exclusion-Archived.csv': 34,
            'Concomitant_Medication_Log.csv': 2701,
            'MRI_Metadata.csv': 2583
        
        }
        self.config_file = config_file
        self.__set_credentials()
    
    def __set_credentials(self):
        '''
        Set PPMI credentials by (1) looking in config file (default:
        .ppmi_config in current working directory), (2) looking in
        environment variables PPMI_LOGIN and PPMI_PASSWORD, (3) prompting
        the user.
        '''

        # These variables will be set by the configuration
        login = None
        password = None

        read_config = False  # will set to True if credentials are read from config file

        # look in .ppmi_config
        if op.exists(self.config_file):
            config = SafeConfigParser()
            config.read('.ppmi_config')
            login = config.get('ppmi', 'login')
            password = config.get('ppmi', 'password')
            read_config = True

        if login is None or password is None:
            # read environment variables
            login = os.environ.get('PPMI_LOGIN')
            password = os.environ.get('PPMI_PASSWORD')
        
        if login is None or password is None:
            # prompt user
            login = input('PPMI login: ')
            password = input('PPMI password: ')

        if not read_config:
            # write .ppmi_config
            config = SafeConfigParser()
            config.read(self.config_file)
            config.add_section('ppmi')
            config.set('ppmi', 'login', login)
            config.set('ppmi', 'password', password)
            with open(self.config_file, 'w') as f:
                config.write(f)

        self.email = login
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
        self.html.enter_data('//*[@id="nameText"]', f"images-{op.basename(tempdir)}")
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
            assert(f.endswith('.csv') or f.endswith('.zip') or f.endswith('.dcm') or f.endswith('.xml')), f
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

    def download_3D_T1_info(self, headless=True, timeout=120, destination_dir='.'):
        '''
        Download csv file containing information about available 3D MRIs

        Keyword arguments:
        * headless: if False, run Chrome not headless
        * timeout: file download timeout, in seconds
        * destination_dir: directory where to store the downloaded files
        '''
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
        self.html.click_button("//a[text()='Image Collections']")
        # Click Advanced Search button
        self.html.click_button("/html/body/div[3]/table/tbody/tr[2]/td/div/ul/li[2]/a/em/font")
        # Click 3D checkbox
        self.html.click_button('//*[@id="imgProtocol_checkBox1.Acquisition_Type.3D"]')
        # Click T1 checkbox
        self.html.click_button('//*[@id="imgProtocol_checkBox1.Weighting.T1"]')
        # Click checkbox to display visit name in resuls
        self.html.click_button('//*[@id="RESET_VISIT.0"]')

        # Click search button
        self.html.click_button('//*[@id="advSearchQuery"]')
        # Click CSV Download button
        self.html.click_button("/html/body/div[2]/table/tbody/tr[2]/td/div/div/div[3]/form/table/tbody/tr/td[2]/table[1]/tbody/tr/td/table/tbody/tr/td[3]/table/tbody/tr/td[5]/input")

        # Wait for download to complete
        def download_complete(driver):
            downloaded_files = os.listdir(tempdir)
            assert(len(downloaded_files) <= 1)
            if len(downloaded_files) == 0:
                return False
            f = downloaded_files[0]
            if f.endswith('.crdownload'):
                return False
            assert(f.endswith('.csv')), f"file ends with: {f}"
            return True
        WebDriverWait(self.driver, timeout).until(download_complete)

        # Move file to cwd or extract zip file
        file_name = self.html.unzip_metadata(tempdir, destination_dir)
        
        # Remove tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

        return file_name

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
                                f'Supported files: {self.file_ids}')

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
        self.html.click_button('//*[@id="ygtvlabelel71"]')

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
        
        password_field = '/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[1]/div[2]/input'
        email_field = '/html/body/div[1]/div[2]/div/div/div[2]/div[4]/div[2]/div/div[1]/form/div[1]/div[1]/input'
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
        return file_name

    def unzip_imaging_data(self, downloaded_files, tempdir, destination_dir):
        for file_name in downloaded_files:
            assert(file_name.endswith('.zip') or file_name.endswith('.csv') or file_name.endswith('.dcm') or file_name.endswith('.xml')), file_name
            if file_name.endswith('.zip'):
                # unzip file to cwd
                with zipfile.ZipFile(op.join(tempdir, file_name), 'r') as zip_ref:
                    zip_ref.extractall(destination_dir)
                    print(f'Successfully downloaded files {zip_ref.namelist()}')
            else:
                os.rename(op.join(tempdir, file_name),
                        op.join(destination_dir, file_name))
                print(f'Successfully downloaded file {file_name}')
        return downloaded_files
