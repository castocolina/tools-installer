"""The messages the Doctor view's workers post back to it."""

from textual.message import Message

from installer.pnpm_globals import (
    NodeGlobalsReport,
)


class GlobalsReinstalled(Message):
    """The threaded pnpm-globals reinstall finished; `error` is None on success.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.
    """

    def __init__(self, error: str | None, invalidate_error: str | None = None) -> None:
        self.error = error
        self.invalidate_error = invalidate_error
        super().__init__()


class GlobalsAudited(Message):
    """The threaded `pnpm list -g --json` finished; the screen may now render it.

    Same hand-off as GlobalsReinstalled, for the same reason: the audit spawns a
    subprocess, so it cannot run on the event loop, and its result cannot be
    written into a widget from the worker's own thread. `preview` travels with
    the report because building it also needs to resolve pnpm.
    """

    def __init__(
        self, report: NodeGlobalsReport, preview: str, error: str | None, generation: int
    ) -> None:
        self.report = report
        self.preview = preview
        self.error = error
        # Two audit workers can be in flight at once (e.g. a stale one from
        # screen entry still running when a reinstall finishes and starts a
        # fresh one): exclusive=True only marks the older worker cancelled, it
        # cannot stop a thread already inside subprocess.run. The generation
        # lets on_globals_audited tell which post_message is the one anyone
        # asked for and discard the other, rather than whichever lands last
        # silently overwriting fresher state with stale state.
        self.generation = generation
        super().__init__()


class DiskPressureProbed(Message):
    """The Doctor's threaded blocking disk-pressure read finished (WR-02).

    Carries nothing: the worker's only job is to warm the shared
    TimerStateCache off the event loop, and the render path then reads the
    fresh answer through the non-blocking peek.
    """
