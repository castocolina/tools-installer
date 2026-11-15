"""The one app-wide mutation lock and its refusal template.

`MutationLock` is a plain base: `UnifiedApp` and a test host share it instead of copying it.
A holder noun fills `MUTATION_REFUSAL` while a mutation runs; a scheduled run refuses with
`SCHEDULED_RUN_REFUSAL`.
"""

from installer import runlock
from installer.catalog_tui import RefreshRequested
from installer.enums import MutationHolder
from installer.execute_screen import ExecuteScreen
from installer.ui_common import AppScreen

MUTATION_REFUSAL = "{holder} is running; wait for it to finish. Navigation still works."
# Nothing in the app ever holds this noun: only a scheduled runner holds the run lock, so it
# is a refusal, not a MutationHolder.
SCHEDULED_RUN_REFUSAL = MUTATION_REFUSAL.format(holder="A scheduled run")


class MutationLock:
    """The one app mutation lock: a holder noun while a mutation runs, else None.
    A plain base so `UnifiedApp` and a test host share it instead of copying it.

    The four holders that change installed tools also take the cross-process run lock, so a
    scheduled run and the app never mutate at once (D-12); toggles and schedule changes stay
    in-app only."""

    _mutation_holder: MutationHolder | None = None
    _run_lock: runlock.RunLock | None = None
    _CROSS_PROCESS = frozenset(
        {
            MutationHolder.INSTALL_RUN,
            MutationHolder.UPDATE,
            MutationHolder.REMOVAL,
            MutationHolder.GLOBALS_REINSTALL,
        }
    )

    @property
    def mutation_in_flight(self) -> bool:
        return self._mutation_holder is not None

    @property
    def mutation_holder(self) -> MutationHolder | None:
        return self._mutation_holder

    def begin_mutation(
        self, holder: MutationHolder, *, screen: AppScreen | ExecuteScreen | None = None
    ) -> bool:
        """Take the lock; False when a scheduled run holds the run lock (refusal on `screen`)."""
        # Every caller refuses first; a second take would let one end_mutation
        # release both (C-30), so it is a bug, never a queue.
        if self._mutation_holder is not None:
            raise RuntimeError(f"{self._mutation_holder} already holds the mutation lock")
        if holder in self._CROSS_PROCESS:
            run_lock = runlock.try_acquire(runlock.run_lock_path(), runlock.INSTALLER_JOB)
            if run_lock is None:
                if screen is not None:
                    self._refuse(screen, SCHEDULED_RUN_REFUSAL)
                return False
            self._run_lock = run_lock
        self._mutation_holder = holder
        return True

    def end_mutation(self) -> None:
        if self._run_lock is not None:
            self._run_lock.release()
            self._run_lock = None
        self._mutation_holder = None

    def refuse_if_mutating(
        self, screen: AppScreen | ExecuteScreen, *, cross_process: bool = False
    ) -> bool:
        """Refuse a second mutation while the lock is held: the one template on
        `screen`'s status, true when refused. `cross_process` also refuses while a
        scheduled run holds the run lock; it reads the holder line and never probes the
        flock (a probe could make a starting runner see busy)."""
        if self._mutation_holder is not None:
            self._refuse(screen, MUTATION_REFUSAL.format(holder=self._mutation_holder))
            return True
        if cross_process and runlock.holder(runlock.run_lock_path()) is not None:
            self._refuse(screen, SCHEDULED_RUN_REFUSAL)
            return True
        return False

    @staticmethod
    def _refuse(screen: AppScreen | ExecuteScreen, sentence: str) -> None:
        screen.status.set(sentence, "warn")
        screen.post_message(RefreshRequested())  # SPEC R2: a refusal still ends with one pass
