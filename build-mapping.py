import argparse
import textdistance as td
import zipfile
import json

distance_algos_default = ["edit_based", "token_based", "compression_based"]


def get_real_names(filename):
    """
    List files containing the in ZIP file
    """
    if not zipfile.is_zipfile(filename):
        raise Exception(f"Not a zip file {filename}")

    real_names = None
    with zipfile.ZipFile(filename, "r") as fi:
        real_names = [f.filename for f in fi.infolist()]

    return real_names


def get_guessed_names(filename):
    """
    Load the JSON file and return the dictionnary
    """
    with open(filename, "r", encoding="utf-8") as fi:
        map_guess_id = json.load(fi)
    return map_guess_id


def find_matching(real, guess, algorithms, top=3):
    """
    For each guessed name, compute the scores accross differents distance algorithms for each real name
    Keep a table mapping the guessed name with the real name having the highest cumulated score accross
    the different algorithms.
    """
    global_scores = {}
    for guess_name, _ in guess.items():
        scores_local = {}
        for _, algo in algorithms.items():
            for real_name in real:
                similarity = algo.normalized_similarity(real_name, guess_name)
                scores_local[real_name] = scores_local.get(real_name, []) + [similarity]

        scores_sorted = sorted(
            scores_local.items(), key=lambda i: sum(i[1]), reverse=True
        )
        for real_name, scr in scores_sorted[:top]:
            print(guess_name, real_name, max(scr), sum(scr))

        global_scores[guess_name] = scores_sorted[0][0]

        print()

    return global_scores


def get_algorithms(names):
    """
    Return a mapping between the names of the algorithm and them
    """
    algos = {}
    for name in names:
        algo_module = getattr(td.algorithms, name)
        for algo_name in algo_module.__all__:
            algo = getattr(algo_module, algo_name, None)
            if not callable(algo) or isinstance(algo, type):
                continue
            algos[algo_name] = algo
    return algos


def output(filename, scores):
    """
    Dump the score in filename as a JSON file
    """
    with open(filename, "w", encoding="utf-8") as fo:
        json.dump(scores, fo)


def parse_args():
    parser = argparse.ArgumentParser(
        "build-mapping",
        description="Build a mapping between PPMI metadata guessed name and real name",
    )
    parser.add_argument(
        "--download-zip",
        required=True,
        help="Path the .zip file that contains all files downloaded from PPMI Download Study data webpage",
    )
    parser.add_argument(
        "--guessed-filename",
        required=True,
        help="JSON file that contains the mapping between the guessed name and the corresponding checkbox ids (study_data_to_checkbox_id.json)",
    )
    parser.add_argument(
        "--output", default="guessed_to_real.json", help="Output filename"
    )
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    real = get_real_names(args.download_zip)
    guessed = get_guessed_names(args.guessed_filename)
    algos = get_algorithms(distance_algos_default)
    scores = find_matching(real, guessed, algos)
    output(args.output, scores)


if "__main__" == __name__:
    main()
