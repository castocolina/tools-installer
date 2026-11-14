"""A typed stand-in for `executors.launch_puppeteer`, which takes the owning manager."""

from collections.abc import Callable


def stub_launch(result: str | None) -> Callable[[str | None], str | None]:
    """A launch seam that answers `result` (None means the browser started) for any manager."""

    def launch(_manager: str | None) -> str | None:
        return result

    return launch
