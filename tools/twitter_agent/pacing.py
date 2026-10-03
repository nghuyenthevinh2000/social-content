"""Randomized browsing delays and periodic breaks shared within a CLI process."""

import random
import time
from typing import Callable, Optional


class ActionPacer:
    DELAYS = {
        'profile': (3.0, 7.0),
        'scroll': (2.0, 5.0),
        'search': (5.0, 10.0),
        'navigation': (3.0, 7.0),
    }

    def __init__(self, *, sleep: Callable[[float], None] = time.sleep, rng=None):
        self.sleep = sleep
        self.rng = rng if rng is not None else random.Random()
        self.actions = 0
        self.break_after = self.rng.randint(50, 100)

    def wait(self, action: str) -> float:
        """Pause before an action; return elapsed wait for collection budgets.

        Attempts count even if the following browser action fails. A long break
        occurs before the next action once the sampled action budget is reached.
        """
        low, high = self.DELAYS[action]
        started = time.monotonic()
        if self.actions >= self.break_after:
            self.sleep(self.rng.uniform(30.0, 60.0))
            self.actions = 0
            self.break_after = self.rng.randint(50, 100)
        self.sleep(self.rng.uniform(low, high))
        self.actions += 1
        return time.monotonic() - started


_default_pacer: Optional[ActionPacer] = None


def get_pacer() -> ActionPacer:
    """Keep pacing across pages, report topics, and watch polling cycles."""
    global _default_pacer
    if _default_pacer is None:
        _default_pacer = ActionPacer()
    return _default_pacer
