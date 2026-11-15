"""The messages UnifiedApp's own workers post back to its event loop."""

from textual.message import Message

from installer import schedules


class ScheduleDefaultsApplied(Message):
    """The threaded schedule-defaults reconcile finished; `report` is what it did (an empty
    report when it did nothing or raised).

    Posted unconditionally from UnifiedApp's own worker, in a finally block,
    regardless of outcome -- mirroring GlobalsAudited/GlobalsReinstalled's same
    thread -> post_message hand-off shape, for the identical reason: widgets
    may only be touched from the app's own thread.
    """

    def __init__(self, report: schedules.ReconcileReport) -> None:
        self.report = report
        super().__init__()


class RefreshPublished(Message):
    """The refresh worker published a pass. `error` is the pass's first error;
    a clean publication means the pass succeeded."""

    def __init__(self, error: str | None, warning: str | None) -> None:
        super().__init__()
        self.error = error
        self.warning = warning


class RefreshFinished(Message):
    """The refresh worker ended; `error` is the pass's first failure, if any."""

    def __init__(self, error: str | None) -> None:
        super().__init__()
        self.error = error
