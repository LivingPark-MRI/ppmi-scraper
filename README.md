A downloader of PPMI metadata files.

# Example usage

```
import ppmi_metadata
ppmi = ppmi_metadata.PPMIMetaDataDownloader(<ppmi_login>, <ppmi_password>)
ppmi.download_metadata(['Demographics.csv', 'Age_at_visit.csv'])
```