import os
import tempfile
import livingpark_utils
import json
from pathlib import Path
import random
from configparser import ConfigParser

import pytest

from ppmi_downloader.ppmi_downloader import PPMIDownloader

ppmi = PPMIDownloader()


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_metadata():
    """Download 3 random files from PPMI."""
    with open(Path(__file__).parents[1].joinpath("file_id.json").resolve()) as fin:
        file_id = json.load(fin)
    filenames = file_id.keys()
    ppmi.download_metadata(random.sample(filenames, min(3, len(filenames))))


def test_download_ppmi_metadata():

    tmpdir = tempfile.TemporaryDirectory()
    utils = livingpark_utils.LivingParkUtils(tmpdir)

    required_files = [
        "Demographics.csv",
        "REM_Sleep_Behavior_Disorder_Questionnaire.csv",
        "Primary_Clinical_Diagnosis.csv",
        "Cognitive_Categorization.csv",
        "Medical_Conditions_Log.csv",
        "Concomitant_Medication_Log.csv",
        "Prodromal_History.csv",
    ]

    utils.download_ppmi_metadata(required_files, headless=False)


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
        ppmi_wrong.init_and_log(headless=False)


def test_ppmi_successing_login():
    # Requires PPMI_LOGIN and PPMI_PASSWORD
    # environment variables to be set
    ppmi.init_and_log()


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_3D_T1_info():
    ppmi.download_3D_T1_info()


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_imaging_data():
    ppmi.download_imaging_data([3001, 3003, 3011])
    ppmi.download_imaging_data([3001, 3003, 3011], type="nifti")


def test_crawl_study_data():
    cache_file = 'study_data_to_checkbox_id.csv'
    ppmi.crawl_study_data(cache_file=cache_file, headless=False)
    assert os.path.exists(cache_file)


def test_crawl_advanced_search():
    cache_file = 'search_to_checkbox_id.csv'
    ppmi.crawl_advanced_search(cache_file=cache_file, headless=False)
    assert os.path.exists(cache_file)
