from setuptools import setup


DEPS = [ 'webdriver_manager', 'selenium']

setup(
    name='ppmi_metadata',
    version='0.1.0',
    description='A downloader of PPMI metadata files.',
    author='Tristan Glatard',
    author_email='tristan.glatard@concordia.ca',
    license='MIT',
    packages=['ppmi_metadata'],
    setup_requires=DEPS,
    install_requires=DEPS,
)
