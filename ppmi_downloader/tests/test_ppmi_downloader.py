import json
import os
from pathlib import Path
import random

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


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_3D_T1_info():
    ppmi.download_3D_T1_info()


@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_download_imaging_data():
    ppmi.download_imaging_data([3001, 3003, 3011])
    ppmi.download_imaging_data([3001, 3003, 3011], type="nifti")
