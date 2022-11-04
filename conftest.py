import pytest


def pytest_addoption(parser):
    parser.addoption("--remote", action="store", dest='url',
                     help="Use [url] for remote webdriver")


@pytest.fixture
def remote(request):
    return request.config.getoption('--remote')
