from installer.links import REPO_URL, TROUBLESHOOTING_URL


def test_repo_url_is_the_project_repo():
    assert REPO_URL == "https://github.com/castocolina/tools-installer"


def test_troubleshooting_url_points_into_the_repo_docs():
    assert TROUBLESHOOTING_URL.startswith(REPO_URL)
    assert TROUBLESHOOTING_URL.endswith("docs/TROUBLESHOOTING.md")
