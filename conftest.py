import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--remote", action="store", dest="url", help="Use [url] for remote webdriver"
    )
    parser.addoption(
        "--no-headless",
        action="store_true",
        default=False,
        help="Use to visualize webdriver interactions",
    )


@pytest.fixture
def remote(request):
    return request.config.getoption("--remote")


@pytest.fixture
def no_headless(request):
    return request.config.getoption("--no-headless")
