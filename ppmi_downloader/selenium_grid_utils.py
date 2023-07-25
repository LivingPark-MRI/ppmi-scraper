import sys
from pathlib import Path
import os

from spython.main import Client

VERBOSE_DEFAULT = False
SELENIUM_VERSION_DEFAULT = "4.5.0"
SINGULARITY_CACHE_FOLDER_DEFAULT = ".ppmi_singularity_cache"
SINGULARITY_BUILD_LOG_DEFAULT = "ppmi-singularity-build.log"
SINGULARITY_RUN_LOG_DEFAULT = "ppmi-singularity-run.log"

env_args = {
    "PPMI_SINGULARITY_SELENIUM_VERSION": SELENIUM_VERSION_DEFAULT,
    "PPMI_SINGULARITY_BUILD_CACHE": SINGULARITY_CACHE_FOLDER_DEFAULT,
    "PPMI_SINGULARITY_BUILD_VERBOSE": VERBOSE_DEFAULT,
    "PPMI_SINGULARITY_RUN_VERBOSE": VERBOSE_DEFAULT,
    "PPMI_SINGULARITY_BUILD_LOG": SINGULARITY_BUILD_LOG_DEFAULT,
    "PPMI_SINGULARITY_RUN_LOG": SINGULARITY_RUN_LOG_DEFAULT,
}


def parse_kwargs():
    r"""Parse environment variables and returns a dictionnary

    Returns
    -------
    dict
        dict binding environement variables value to short keys

    """
    kwargs = {}
    for env, default in env_args.items():
        kwargs[env] = os.getenv(env, default=default)
    print(kwargs)
    return {
        "version": kwargs["PPMI_SINGULARITY_SELENIUM_VERSION"],
        "cache": kwargs["PPMI_SINGULARITY_BUILD_CACHE"],
        "build_verbose": kwargs["PPMI_SINGULARITY_BUILD_VERBOSE"],
        "run_verbose": kwargs["PPMI_SINGULARITY_RUN_VERBOSE"],
        "build_log": kwargs["PPMI_SINGULARITY_BUILD_LOG"],
        "run_log": kwargs["PPMI_SINGULARITY_RUN_LOG"],
    }


def get_image_recipe(version):
    return f"docker://selenium/standalone-chrome:{version}"


def get_image_name(version):
    return f"selenium-standalone-chrome-{version}.sif"


def build():
    r"""Build selenium grid singularity container

    This function is intended to be used as script
    so arguments are passed by environment variables.
    `PPMI_SINGULARITY_BUILD_CACHE`: cache folder to store the built image
    `PPMI_SINGULARITY_SELENIUM_VERSION`: version of selenium used
    `PPMI_SINGULARITY_BUILD_VERBOSE`: enable verbose mode for the build
    `PPMI_SINGULARITY_BUILD_LOG`: log file name to dump build's outputs

    Upon success, it exits with 0.
    Upon failure, Client raises exceptions caught by the script wrapper
    generated during the build
    """
    kwargs = parse_kwargs()
    cache = kwargs["cache"]
    version = kwargs["version"]
    verbose = kwargs["build_verbose"]
    log = kwargs["build_log"]

    image = get_image_name(version)
    recipe = get_image_recipe(version)
    os.makedirs(kwargs["cache"], exist_ok=True)
    image, stream = Client.build(
        recipe=recipe, image=image, stream=True, build_folder=cache, sudo=False
    )

    with open(log, "w", encoding="utf-8") as fo:
        for line in stream:
            print(line, sep="", file=fo)
            if verbose:
                print(line, sep="")

    sys.exit()


def run():
    r"""Run selenium grid singularity container

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
    """
    kwargs = parse_kwargs()
    cache = kwargs["cache"]
    version = kwargs["version"]
    verbose = kwargs["run_verbose"]
    log = kwargs["run_log"]

    image_name = get_image_name(version)
    image = os.path.join(cache, image_name)

    Client.load(image)

    Path("supervisord.log").touch()
    Path("config.toml").touch()
    Path("supervisord.pid").touch()

    pwd = os.getcwd()
    bindings = [
        f"{pwd}/supervisord.log:/var/log/supervisor/supervisord.log",
        f"{pwd}/config.toml:/opt/selenium/config.toml",
        f"{pwd}/supervisord.pid:/var/run/supervisor/supervisord.pid",
    ]

    options = ['--network-args="mapport=4444:4444/tcp"']
    runner = Client.run(image=image, stream=True, bind=bindings, options=options)

    with open(log, "w", encoding="utf-8") as fo:
        for line in runner:
            print(line, end="", file=fo)
            if verbose:
                print(line, end="")
            fo.flush()
            sys.stdout.flush()

    sys.exit()
