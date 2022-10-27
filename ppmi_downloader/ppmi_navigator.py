from typing import Dict
from typing import List
import time
import os
import os.path as op
import zipfile
import urllib.parse

import selenium.webdriver.support.expected_conditions as EC
import tqdm
from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException,
                                        WebDriverException,
                                        TimeoutException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

import ppmi_downloader.ppmi_logger as logger

TIMEOUT = 5
TRIALS = 5
ppmi_main_webpage = "https://ida.loni.usc.edu/login.jsp?project=PPMI"
ppmi_home_webpage = "https://ida.loni.usc.edu/home/projectPage.jsp?project=PPMI"
ppmi_login_webpage = 'https://ida.loni.usc.edu/explore/jsp/common/login.jsp?project=PPMI'


class HTMLHelper:
    def __init__(self, driver) -> None:
        self.driver = driver

    def wait_for_element_to_be_visible(self, field, BY=By.XPATH):
        predicate = EC.visibility_of_element_located((BY, field))
        element = WebDriverWait(self.driver, TIMEOUT,
                                poll_frequency=1).until(predicate)
        return element

    def enter_data(self, field, data,
                   BY=By.XPATH,
                   debug_name='',
                   trials=TRIALS):
        if trials < 0:
            logger.error('Number of trials is exceeded')
            self.driver.quit()
        try:
            logger.debug('Enter data', field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            form = WebDriverWait(self.driver, TIMEOUT,
                                 poll_frequency=1).until(predicate)
            form.send_keys(data)
        except WebDriverException:
            self.enter_data(field=field, data=data, BY=BY,
                            debug_name=debug_name,
                            trials=trials - 1)

    def click_button(self, field, BY=By.XPATH, debug_name='', trials=TRIALS):
        if trials < 0:
            logger.error('Number of trials is exceeded')
            self.driver.quit()
        try:
            logger.debug('Click button', field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            button = WebDriverWait(self.driver, TIMEOUT,
                                   poll_frequency=1).until(predicate)
            button.click()
        except WebDriverException:
            self.click_button(field=field, BY=BY,
                              debug_name=debug_name,
                              trials=trials - 1)

    # def click_button(self, field, BY=By.XPATH, debug_name='', trials=TRIALS):
    #     elements = self.driver.find_elements(BY, field)
    #     if len(elements) > 1:
    #         logger.warning('Multiple elements found for ', field)
    #         logger.warning(
    #             'Try a more restrictive mark to avoid selecting misleading elements')

    #     self._click_button(field=field, BY=By.XPATH,
    #                        debug_name=debug_name, trials=trials)

    def submit_button(self, field, BY=By.XPATH, debug_name='', trials=TRIALS):
        if trials < 0:
            logger.error('Number of trials is exceeded')
            self.driver.quit()
        try:
            logger.debug('Submit button', field, debug_name)
            predicate = EC.element_to_be_clickable((BY, field))
            button = WebDriverWait(self.driver, TIMEOUT,
                                   poll_frequency=1).until(predicate)
            button.submit()
        except WebDriverException:
            self.submit_button(field=field, BY=BY,
                               debug_name=debug_name,
                               trials=trials - 1)

    def wait_for(self, predicate):
        return WebDriverWait(self.driver, TIMEOUT,
                             poll_frequency=1).until(predicate)

    def click_button_by_text(self, text, debug_name=''):
        self.click_button(f"//*[text()='{text}']", debug_name=debug_name)

    def submit_button_by_text(self, text, debug_name=''):
        self.submit_button(f"//*[text()='{text}']", debug_name=debug_name)

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
        self.driver.get(ppmi_login_webpage)
        self.wait_for_element_to_be_visible('userEmail', BY=By.NAME)
        self.enter_data("userEmail", email, BY=By.NAME, debug_name='Email')
        self.wait_for_element_to_be_visible('userPassword', BY=By.NAME)
        self.enter_data("userPassword", password,
                        BY=By.NAME, debug_name='Password')
        self.wait_for_element_to_be_visible('button', BY=By.TAG_NAME)
        self.click_button("button", By.TAG_NAME, debug_name='Login button')

        try:
            self.driver.find_element(
                By.CLASS_NAME, 'register-input-error-msg.invalid-login')
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

    def click_chain_cleaner(self, action: str) -> str:
        '''
        Clean action name to match function
        '''
        return action.replace('(', '').replace(')', '').replace(' ', '')

    def click_button_chain(self, chain: List[str]) -> None:
        '''
        Allows for chaining multiple actions represented as a list of string
        For example:
            ["Download","Study Data","ALL"]
        will click on Download then Study Data and finally ALL
        '''
        action = []
        for action_name in chain:
            action.append(self.click_chain_cleaner(action_name))
            getattr(self, '_'.join(action))()

    def check_url_query(self, url: str, queries: Dict[str, str]) -> bool:
        query = urllib.parse.parse_qs(url)
        logger.debug(queries)
        for field, expected in queries.items():
            actual = query.get(field, ['']).pop()
            logger.debug(field, expected, actual, expected == actual)
            if actual != expected:
                return False
        return True

    def is_element_active(self, class_name) -> bool:
        try:
            name = f'{class_name}.active'
            predicate = EC.presence_of_element_located(
                (By.CLASS_NAME, name))
            WebDriverWait(self.driver, 2,
                          poll_frequency=1).until(predicate)
        except (NoSuchElementException, TimeoutException):
            return False
        else:
            return True

    def has_HamburgerMenu(self) -> bool:
        try:
            return self.driver.find_element(By.CLASS_NAME, 'ida-menu-hamburger').is_displayed()
        except NoSuchElementException:
            return False
        else:
            return True

    def HamburgerMenu(self) -> None:
        def postcondition() -> bool:
            return self.is_element_active('ida-menu-main-options')

        while not postcondition():
            self.click_button('ida-menu-hamburger',
                              BY=By.CLASS_NAME,
                              debug_name='Hamburger menu')

    def HamburgerMenu_Download(self) -> None:
        def postcondition() -> bool:
            return self.is_element_active('ida-menu-option.sub-menu.download')

        while not postcondition():
            self.click_button('ida-menu-option.sub-menu.download',
                              BY=By.CLASS_NAME,
                              debug_name='Download Hamburger submenu')

    def Download(self) -> None:
        if self.has_HamburgerMenu():
            self.HamburgerMenu()
            self.HamburgerMenu_Download()

        def postcondition() -> bool:
            return self.is_element_active('ida-menu-option.sub-menu.download')

        while not postcondition():
            self.click_button('ida-menu-option.sub-menu.download',
                              BY=By.CLASS_NAME,
                              debug_name='Download')

    def Download_StudyData(self) -> None:
        '''
        Parent: Download
        '''
        studydata_url = 'https://ida.loni.usc.edu/pages/access/studyData.jsp'
        while not self.driver.current_url.startswith(studydata_url):
            self.click_button_by_text('Study Data',
                                      debug_name='Study Data')

    def Download_StudyData_ALL(self) -> None:
        '''
        Parent: StudyData
        '''
        studydata_url = 'https://ida.loni.usc.edu/pages/access/studyData.jsp'
        while self.driver.current_url != studydata_url:
            self.click_button("ygtvlabelel71", BY=By.ID, debug_name='ALL')

    def Download_ImageCollections(self) -> None:
        '''
        Parent: Download
        '''
        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(self.driver.current_url,
                                        {'page': 'DOWNLOADS',
                                         'subPage': 'IMAGE_COLLECTIONS'})

        while not postcondition():
            self.click_button_by_text(
                "Image Collections", debug_name='Image Collections')

    def Download_GeneticData(self) -> None:
        '''
        Parent: Download
        '''
        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(self.driver.current_url,
                                        {'page': 'DOWNLOADS',
                                         'subPage': 'GENETIC_DATA'})

        while not postcondition():
            self.click_button_by_text("Genetic Data",
                                      debug_name='Generic Data')

    def Search(self) -> None:
        def postcondition() -> bool:
            try:
                name = 'ida-menu-option.sub-menu.search.active'
                predicate = EC.presence_of_element_located(
                    (By.CLASS_NAME, name))
                WebDriverWait(self.driver, 2,
                              poll_frequency=1).until(predicate)
            except (NoSuchElementException, TimeoutException):
                return False
            else:
                return True
        while not postcondition():
            self.click_button('ida-menu-option.sub-menu.search',
                              BY=By.CLASS_NAME,
                              debug_name='Search')

    def Search_SimpleImageSearch(self) -> None:
        '''
        Parent: Search
        '''
        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(self.driver.current_url,
                                        {'page': 'SEARCH',
                                         'subPage': 'SIMPLE_QUERY'})

        while not postcondition():
            self.click_button_by_text('Simple Image Search',
                                      debug_name='Simple Image Search')

    def Search_AdvancedImageSearch(self) -> None:
        '''
        Parent: Search
        '''
        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(self.driver.current_url,
                                        {'page': 'SEARCH',
                                         'subPage': 'ADV_QUERY'})

        while not postcondition():
            self.click_button_by_text("Advanced Image Search",
                                      debug_name='Advanced Image Search')

    def Search_AdvancedImageSearchbeta(self) -> None:
        '''
        Parent: Search
        '''
        def postcondition() -> bool:
            time.sleep(1)
            return self.check_url_query(self.driver.current_url,
                                        {'page': 'SEARCH',
                                         'subPage': 'NEW_ADV_QUERY'})

        while not postcondition():
            logger.debug(not postcondition())
            self.click_button_by_text("Advanced Image Search (beta)",
                                      debug_name="Advanced Image Search (beta)")

    def Search_AdvancedImageSearchbeta_SelectAll(self) -> None:
        '''
        Parent: Search
        '''
        def predicate(driver) -> bool:
            select_all = driver.find_element(By.ID, 'advResultSelectAll')
            add_to_collection = driver.find_element(By.ID,
                                                    'advResultAddCollectId')
            logger.debug(select_all, select_all.is_selected())
            logger.debug(add_to_collection, add_to_collection.is_enabled())
            return select_all.is_selected() and add_to_collection.is_enabled()

        def postcondition() -> bool:
            try:
                WebDriverWait(self.driver, 2,
                              poll_frequency=1).until(predicate)
            except (NoSuchElementException, TimeoutException):
                return False
            else:
                return True

        while not postcondition():
            logger.debug(not postcondition())
            self.click_button("advResultSelectAll", By.ID,
                              debug_name='Select All')

    def Search_AdvancedImageSearchbeta_AddToCollection_OK(self) -> None:
        '''
        Parent: Search
        '''
        def postcondition() -> bool:
            # Check that the dialog panel has disappeared
            try:
                return not self.driver.find_element(By.ID, 'regroupDialog').is_displayed()
            except (NoSuchElementException):
                return True
            else:
                return False

        while not postcondition():
            logger.debug(not postcondition())
            ok = None
            for elt in self.driver.find_elements(By.TAG_NAME, 'button'):
                if elt.text == 'OK':
                    ok = elt
            try:
                ok.click()
            except AttributeError:
                continue
            except StaleElementReferenceException:
                break
