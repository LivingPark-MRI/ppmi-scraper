A downloader of PPMI metadata and imaging data files.

[![Python application](https://github.com/LivingPark-MRI/ppmi-scraper/actions/workflows/python-app.yml/badge.svg)](https://github.com/LivingPark-MRI/ppmi-scraper/actions/workflows/python-app.yml)

# Example usage

```python
import ppmi_downloader
ppmi = ppmi_downloader.PPMIDownloader()

# Download metadata files
ppmi.download_metadata(['Demographics.csv', 'Age_at_visit.csv'])

# Download 3D imaging metadata
ppmi.download_3D_T1_info()

# Download imaging data (in DICOM format)
ppmi.download_imaging_data([3001, 3003, 3011])

# Download imaging data (in Nifti format)
ppmi.download_imaging_data([3001, 3003, 3011], type='nifti')

```

# Scripts to use Selenium Grid 

`ppmi_scrapper` provides scripts for building and running
selenium webdriver 

## `build_selenium`

Build selenium grid singularity container

This function is intended to be used as script
so arguments are passed by environment variables.
`PPMI_SINGULARITY_BUILD_CACHE`: cache folder to store the built image
`PPMI_SINGULARITY_SELENIUM_VERSION`: version of selenium used
`PPMI_SINGULARITY_BUILD_VERBOSE`: enable verbose mode for the build
`PPMI_SINGULARITY_BUILD_LOG`: log file name to dump build's outputs

Upon success, it exits with 0.
Upon failure, Client raises exceptions caught by the script wrapper
generated during the build

## **`run_selenium`**

Run selenium grid singularity container

This function is intended to be used as script
so arguments are passed by environment variables.
`PPMI_SINGULARITY_SELENIUM_VERSION`: version of selenium used
`PPMI_SINGULARITY_RUN_CACHE`: cache folder to find the built image
`PPMI_SINGULARITY_RUN_VERBOSE`: enable verbose mode for the run
`PPMI_SINGULARITY_RUN_LOG`: log file name to dump run's outputs
Run the selenium grid singularity container by
creating and binding files required by the container
Communication is mapped on 4444 port.


Upon success, it exits with 0.
Upon failure, Client raises exceptions caught by the script wrapper
generated during the run

