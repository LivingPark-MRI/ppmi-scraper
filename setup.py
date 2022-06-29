from setuptools import setup


DEPS = [ 'webdriver_manager', 'selenium']

setup(
    name='ppmi_downloader',
    version='0.1.1',
    description='A downloader of PPMI files.',
    author='Tristan Glatard',
    author_email='tristan.glatard@concordia.ca',
    license='MIT',
    packages=['ppmi_downloader'],
    setup_requires=DEPS,
    install_requires=DEPS,
)
