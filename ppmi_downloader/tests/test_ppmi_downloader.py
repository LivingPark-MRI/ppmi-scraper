import json
import os
import random
import tempfile
from configparser import ConfigParser

import pytest
from ppmi_downloader.ppmi_downloader import PPMIDownloader

headless = True


def test_ppmi_successing_login(remote):
    # Requires PPMI_LOGIN and PPMI_PASSWORD
    # environment variables to be set
    ppmi = PPMIDownloader(remote=remote)
    ppmi.init_and_log(headless=headless)
    ppmi.quit()


def test_ppmi_failing_login(remote):
    config_filename = tempfile.NamedTemporaryFile()
    config_parser = ConfigParser()
    config_parser['ppmi'] = {
        'login': 'fake@fake.com',
        'password': 'fake'
    }
    with open(config_filename.name, 'w', encoding='utf-8') as fo:
        config_parser.write(fo)
        fo.flush()
    ppmi_wrong = PPMIDownloader(
        config_file=config_filename.name, remote=remote)
    with pytest.raises(SystemExit):
        ppmi_wrong.init_and_log(headless=headless)
    ppmi_wrong.quit()


def test_hamburger_menu(remote):
    '''
    Test Download is correctly clicked when
    window is small (displayed hamburger menu)
    '''
    ppmi = PPMIDownloader(remote=remote)
    ppmi.init_and_log()
    ppmi.driver.set_window_size(800, 600)
    ppmi.html.Download()
    ppmi.quit()


def test_crawl_study_data(remote):
    ppmi = PPMIDownloader(remote=remote)
    cache_file = 'study_data_to_checkbox_id.json'
    ppmi.crawl_study_data(cache_file=cache_file, headless=headless)
    assert os.path.exists(cache_file)
    with open(cache_file, 'r') as fi:
        print(json.load(fi))
    ppmi.quit()


def test_crawl_advanced_search(remote):
    cache_file = 'search_to_checkbox_id.json'
    ppmi = PPMIDownloader(remote=remote)
    ppmi.crawl_advanced_search(cache_file=cache_file, headless=headless)
    assert os.path.exists(cache_file)
    ppmi.quit()


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_metadata(remote):
    """Download 3 random files from PPMI."""
    ppmi = PPMIDownloader(remote=remote, tempdir='.')
    with open(ppmi.file_ids_path, 'r', encoding='utf-8') as fin:
        file_id = json.load(fin)
    filenames = file_id.keys()
    mismatched_names = ['Socio-Economics.csv',
                        'Data_Dictionary_-__Annotated_.csv',
                        'SCOPA-AUT.csv']
    random_names = random.sample(filenames, min(3, len(filenames)))
    ppmi.download_metadata(mismatched_names + random_names, headless=headless)
    ppmi.quit()


@ pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_3D_T1_info(remote):
    ppmi = PPMIDownloader(remote=remote, tempdir='.')
    ppmi.download_3D_T1_info(headless=headless)
    ppmi.quit()


@ pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_imaging_data(remote):
    ids = [3001, 3003, 3011]
    ppmi = PPMIDownloader(remote=remote, tempdir='.')
    ppmi.download_imaging_data(ids, headless=headless)
    ppmi.download_imaging_data(ids, type="nifti", headless=headless)
    ppmi.quit()
