import os
import tempfile
import json
from pathlib import Path
import random
from configparser import ConfigParser

import pytest

from ppmi_downloader.ppmi_downloader import PPMIDownloader

headless = True

ppmi = PPMIDownloader()


def test_ppmi_successing_login():
    # Requires PPMI_LOGIN and PPMI_PASSWORD
    # environment variables to be set
    ppmi.init_and_log(headless=headless)


def test_ppmi_failing_login():
    config_filename = tempfile.NamedTemporaryFile()
    config_parser = ConfigParser()
    config_parser['ppmi'] = {
        'login': 'fake@fake.com',
        'password': 'fake'
    }
    with open(config_filename.name, 'w', encoding='utf-8') as fo:
        config_parser.write(fo)
        fo.flush()
    ppmi_wrong = PPMIDownloader(config_file=config_filename.name)
    with pytest.raises(SystemExit):
        ppmi_wrong.init_and_log(headless=headless)


def test_hamburger_menu():
    '''
    Test Download is correctly clicked when
    window is small (displayed hamburger menu)
    '''
    ppmi.init_and_log()
    ppmi.driver.set_window_size(800, 600)
    ppmi.html.Download()


def test_crawl_study_data():
    cache_file = 'study_data_to_checkbox_id.json'
    ppmi.crawl_study_data(cache_file=cache_file, headless=headless)
    assert os.path.exists(cache_file)


def test_crawl_advanced_search():
    cache_file = 'search_to_checkbox_id.json'
    ppmi.crawl_advanced_search(cache_file=cache_file, headless=headless)
    assert os.path.exists(cache_file)


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_metadata():
    """Download 3 random files from PPMI."""
    with open(ppmi.file_ids_path, 'r', encoding='utf-8') as fin:
        file_id = json.load(fin)
    filenames = file_id.keys()
    ppmi.download_metadata(random.sample(
        filenames, min(3, len(filenames))), headless=headless)


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_3D_T1_info():
    ppmi.download_3D_T1_info(headless=headless)


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_imaging_data():
    ppmi.download_imaging_data([3001, 3003, 3011], headless=headless)
    ppmi.download_imaging_data(
        [3001, 3003, 3011], type="nifti", headless=headless)
