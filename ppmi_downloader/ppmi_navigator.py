import time
import os
import os.path as op
import zipfile

import selenium.webdriver.support.expected_conditions as EC
import tqdm
from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException,
                                        WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

import ppmi_downloader.ppmi_logger as logger

TIMEOUT = 120
ppmi_main_webpage = "https://ida.loni.usc.edu/login.jsp?project=PPMI"
ppmin_home_webpage = "https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI"


class HTMLHelper:
    def __init__(self, driver) -> None:
        self.driver = driver

    def is_page_loaded(self):
        return self.driver.execute_script('return window.load') == 'true'

    def wait_until_page_is_loaded(self):
        while not self.is_page_loaded():
            time.sleep(.1)

    def wait(self):
        self.driver.implicitly_wait(1)

    def enter_data(self, field, data, BY=By.XPATH, debug_name=''):
        try:
            logger.debug('Enter data', field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            form = WebDriverWait(self.driver, TIMEOUT,
                                 poll_frequency=1).until(predicate)
            self.wait()
            form.send_keys(data)
        except WebDriverException as e:
            self.driver.quit()
            logger.error(e)

    def click_button(self, field, BY=By.XPATH, debug_name=''):
        try:
            logger.debug('Click button', field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            button = WebDriverWait(self.driver, TIMEOUT,
                                   poll_frequency=1).until(predicate)
            self.wait()
            button.click()
        except WebDriverException as e:
            self.driver.quit()
            logger.error(e)

    def click_button_by_text(self, text, debug_name):
        self.click_button(f"//*[text()='{text}']", debug_name=debug_name)

    def validate_cookie_policy(self):
        self.driver.get(ppmi_main_webpage)
        try:
            self.click_button("ida-cookie-policy-accept",
                              BY=By.CLASS_NAME, debug_name='Cookie Policy')
        except ElementClickInterceptedException:
            logger.debug('Cookie Policy already accepted')

    def find_all_anchors(self):
        return self.driver.find_elements(By.TAG_NAME, 'a')

    def find_all_checkboxes(self):
        return self.driver.find_elements(By.XPATH, '//*[@type="checkbox"]')

    def login(self, email, password):
        self.validate_cookie_policy()
        self.click_button("ida-menu-option.sub-menu.login",
                          BY=By.CLASS_NAME, debug_name='Log In')
        self.enter_data("userEmail", email, BY=By.NAME, debug_name='Email')
        self.enter_data("userPassword", password + 'afd',
                        BY=By.NAME, debug_name='Password')
        self.click_button("login-btn", By.CLASS_NAME, debug_name='Login')

        try:
            self.driver.find_element(
                By.CLASS_NAME, 'ida-menu-login-invalid')
            logger.error('Login Failed')
        except NoSuchElementException:
            logger.info('Login Successful')

    def unzip_file(self, filename, tempdir, destination_dir):
        if filename.endswith(".zip"):
            # unzip file to cwd
            with zipfile.ZipFile(op.join(tempdir, filename), "r") as zip_ref:
                zip_ref.extractall(destination_dir)
                filesname = zip_ref.namelist()[:2]
                logger.info(f"Successfully downloaded files {filesname}...")
        else:
            source = op.join(tempdir, filename)
            target = op.join(destination_dir, filename)
            os.rename(source, target)
            logger.info(f"Successfully downloaded file {filename}")

    def unzip_metadata(self, tempdir, destination_dir):
        # Move file to cwd or extract zip file
        downloaded_files = os.listdir(tempdir)
        # we got either a csv or a zip file
        assert len(downloaded_files) == 1
        file_name = downloaded_files[0]
        assert file_name.endswith((".zip", ".csv"))
        self.unzip_file(file_name, tempdir, destination_dir)
        return file_name

    def unzip_imaging_data(self, downloaded_files, tempdir, destination_dir):
        accepted_extension = ('.zip', '.csv', '.dcm', '.xml')
        for filename in tqdm.tqdm(downloaded_files):
            assert filename.endswith(accepted_extension), filename
            self.unzip_file(filename, tempdir, destination_dir)
        return downloaded_files


class PPMINavigator(HTMLHelper):

    def click_chain_cleaner(self, action):
        '''
        Clean action name to match function        
        '''
        return action.replace('(', '').replace(')', '').replace(' ', '')

    def click_button_chain(self, chain):
        '''
        Allows for chaining multiple actions represented as a list of string
        For example:
            ["Download","Study Data","ALL"]
        will click on Download then Study Data and finally ALL        
        '''
        if isinstance(chain, list):
            actions = chain
        else:
            raise Exception(f'Unknown type {type(action)} for action chain')

        action = []
        for action_name in actions:
            action.append(self.click_chain_cleaner(action_name))
            getattr(self, '_'.join(action))()

    def Download(self):
        self.click_button('ida-menu-option.sub-menu.download',
                          BY=By.CLASS_NAME,
                          debug_name='Download')

    def Download_StudyData(self):
        '''
        Parent: Download
        '''
        self.click_button_by_text('Study Data', debug_name='Study Data')

    def Download_StudyData_ALL(self):
        '''
        Parent: StudyData
        '''
        self.click_button("ygtvlabelel71", BY=By.ID, debug_name='ALL')

    def Download_ImageCollections(self):
        '''
        Parent: Download
        '''
        self.click_button_by_text(
            "Image Collections", debug_name='Image Collections')

    def Download_GeneticData(self):
        '''
        Parent: Download
        '''
        self.click_button_by_text("Genetic Data", debug_name='Generic Data')

    def Search(self):
        self.click_button('ida-menu-option.sub-menu.search',
                          BY=By.CLASS_NAME,
                          debug_name='Search')

    def Search_SimpleImageSearch(self):
        '''
        Parent: Search
        '''
        self.click_button_by_text('Simple Image Search',
                                  debug_name='Simple Image Search')

    def Search_AdvancedImageSearch(self):
        '''
        Parent: Search
        '''
        self.click_button_by_text("Advanced Image Search",
                                  debug_name='Advanced Image Search')

    def Search_AdvancedImageSearchbeta(self):
        '''
        Parent: Search
        '''
        self.click_button_by_text("Advanced Image Search (beta)",
                                  debug_name="Advanced Image Search (beta)")
