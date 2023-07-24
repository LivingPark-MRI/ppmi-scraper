import pandas as pd

visit_ids = {
    "BL": "Baseline",
    "V01": "Month 3",
    "V02": "Month 6",
    "V03": "Month 9",
    "V04": "Month 12",
    "V05": "Month 18",
    "V06": "Month 24",
    "V07": "Month 30",
    "V08": "Month 36",
    "V09": "Month 42",
    "V10": "Month 48",
    "V11": "Month 54",
    "V12": "Month 60",
    "V13": "Month 72",
    "V14": "Month 84",
    "V15": "Month 96",
    "V16": "Month 108",
    "V17": "Month 120",
    "V18": "Month 132",
    "V19": "Month 144",
    "V20": "Month 156",
}


def cohort_id(cohort: pd.DataFrame) -> str:
    """Return a unique id for the cohort.

    The id is built as the hash of the sorted list of patient ids in the cohort.
    Since cohort_ids may be used to create file names, negative signs ('-')
    are replaced with underscore characters ('_') since SPM crashes on file names
    containing negative signs. Therefore, the cohort id is a string that cannot
    be cast to an integer.

    Parameters
    ----------
    cohort: pd.DataFrame
        A Pandas DataFrame with a column named 'PATNO'.

    Returns
    -------
    cohort_id: string
        A string containing the unique id of the cohort.
    """
    return str(hash(tuple(sorted(cohort["PATNO"])))).replace("-", "_")
