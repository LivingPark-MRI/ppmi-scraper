import livingpark_utils
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
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
