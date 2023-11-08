import json
import os
import random
import tempfile
from configparser import ConfigParser

import pandas as pd
import pytest
from ppmi_downloader.ppmi_downloader import PPMIDownloader


def test_ppmi_successing_login(remote, no_headless):
    # Requires PPMI_LOGIN and PPMI_PASSWORD
    # environment variables to be set
    headless = not no_headless
    ppmi = PPMIDownloader(remote=remote, headless=headless)
    ppmi.init_and_log()
    ppmi.quit()


def test_ppmi_failing_login(remote, no_headless):
    headless = not no_headless
    config_filename = tempfile.NamedTemporaryFile()
    config_parser = ConfigParser()
    config_parser["ppmi"] = {"login": "fake@fake.com", "password": "fake"}
    with open(config_filename.name, "w", encoding="utf-8") as fo:
        config_parser.write(fo)
        fo.flush()
    ppmi_wrong = PPMIDownloader(
        config_file=config_filename.name, remote=remote, headless=headless
    )
    with pytest.raises(SystemExit):
        ppmi_wrong.init_and_log()
    ppmi_wrong.quit()


def test_ppmi_double_login(remote, no_headless):
    headless = not no_headless
    ppmi = PPMIDownloader(remote=remote, headless=headless)
    ppmi.init_and_log()
    ppmi.init_and_log()
    ppmi.quit()


def test_hamburger_menu(remote, no_headless):
    """
    Test Download is correctly clicked when
    window is small (displayed hamburger menu)
    """
    headless = not no_headless
    ppmi = PPMIDownloader(remote=remote, headless=headless)
    ppmi.init_and_log()
    ppmi.driver.set_window_size(800, 600)
    ppmi.html.Download()
    ppmi.quit()


def test_crawl_study_data(remote, no_headless):
    headless = not no_headless
    ppmi = PPMIDownloader(remote=remote, headless=headless)
    cache_file = "study_data_to_checkbox_id.json"
    ppmi.crawl_study_data(cache_file=cache_file)
    assert os.path.exists(cache_file)
    with open(cache_file, "r") as fi:
        print(json.load(fi))
    ppmi.quit()


def test_crawl_advanced_search(remote, no_headless):
    headless = not no_headless
    cache_file = "search_to_checkbox_id.json"
    ppmi = PPMIDownloader(remote=remote, headless=headless)
    ppmi.crawl_advanced_search(cache_file=cache_file)
    assert os.path.exists(cache_file)
    ppmi.quit()


def test_download_metadata(remote, no_headless):
    """Download 3 random files from PPMI."""
    headless = not no_headless
    ppmi = PPMIDownloader(remote=remote, tempdir=".", headless=headless)
    with open(ppmi.file_ids_path, "r", encoding="utf-8") as fin:
        file_id = json.load(fin)
    filenames = file_id.keys()
    mismatched_names = [
        "Socio-Economics.csv",
        "Data_Dictionary_-__Annotated_.csv",
        "SCOPA-AUT.csv",
    ]
    random_names = random.sample(list(filenames), min(3, len(filenames)))
    ppmi.download_metadata(mismatched_names + random_names)
    ppmi.quit()


def test_download_3D_T1_info(remote, no_headless):
    headless = not no_headless
    ppmi = PPMIDownloader(remote=remote, tempdir=".", headless=headless)
    ppmi.download_3D_T1_info()
    ppmi.quit()


def test_download_imaging_data(remote, no_headless):
    headless = not no_headless
    cohort = pd.DataFrame(
        {
            "PATNO": [3001, 3003, 3011],
            "EVENT_ID": ["BL", "BL", "BL"],
            "Description": ["AX T2 FLAIR 5/1", "AX T2 FLAIR 5/1", "AX T2 FLAIR 5/1"],
        }
    )
    ppmi = PPMIDownloader(remote=remote, tempdir=".", headless=headless)
    ppmi.download_imaging_data(cohort)
    ppmi.quit()
