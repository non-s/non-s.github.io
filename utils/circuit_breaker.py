"""Reusable in-process circuit breaker.

Generalizes the pattern utils/ai_helper.py proved out first (see its
_mistral_circuit_open/_mistral_429_streak): a queue-refresh run once timed
out at 25 minutes because Mistral 429'd 36 times in a row and each give-up
cost ~30s of retry-and-wait before falling back. After `threshold`
consecutive failures, `is_open` trips and a caller should skip the guarded
call for the rest of the run instead of continuing to pay for retries
against something that has already shown it's down right now. A single
success resets the streak.

Deliberately in-process only (plain instance state, nothing persisted to
disk): a GitHub Actions run is a fresh process every time, so "skip for the
rest of this run" is the right lifetime -- not "stay open until someone
manually clears a state file."

ai_helper.py's own Mistral breaker is left as its own tested, working
implementation rather than retrofitted onto this class -- the value here is
for *new* call sites. A good candidate is any loop that calls an external
provider multiple times per run and currently keeps trying every one even
after the provider has clearly stopped responding (e.g. a fetch loop over
several search queries/offsets against one API), but only in a spot where
"the call failed" and "the call succeeded with zero results" are already
tracked as genuinely different outcomes -- conflating them would trip the
breaker on ordinary empty search results, not an actual outage.
"""

from __future__ import annotations


class CircuitBreaker:
    def __init__(self, threshold: int = 3):
        self.threshold = max(1, int(threshold))
        self._streak = 0
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def streak(self) -> int:
        return self._streak

    def record_success(self) -> None:
        self._streak = 0
        self._open = False

    def record_failure(self) -> None:
        self._streak += 1
        if self._streak >= self.threshold:
            self._open = True

    def reset(self) -> None:
        self._streak = 0
        self._open = False
