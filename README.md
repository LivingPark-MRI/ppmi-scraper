A downloader of PPMI metadata and imaging data files.

# Example usage

```
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