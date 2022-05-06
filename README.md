A downloader of PPMI metadata files.

# Example usage

```
import ppmi_downloader
ppmi = ppmi_downloader.PPMIDownloader(<ppmi_login>, <ppmi_password>)
ppmi.download_metadata(['Demographics.csv', 'Age_at_visit.csv'])
ppmi.download_imaging_data([3001, 3003, 3011])
```