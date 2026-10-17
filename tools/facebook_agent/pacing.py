"""Randomized inter-recipient delays and periodic cooldowns for direct messaging.

Mirrors the reference tool's anti-detection intent (short jittered pauses between
sends, a longer cooldown at a configurable interval) without hardcoding its
numbers. Sleep and randomness are injectable so the behavior is testable offline.
"""

import random
import time
from typing import Callable


class MessagePacer:
    def __init__(
        self,
        *,
        min_delay_s: float = 3.2,
        max_delay_s: float = 4.5,
        cooldown_every: int = 50,
        cooldown_s: float = 240.0,
        cooldown_jitter_s: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        rng=None,
    ):
        if min_delay_s < 0 or max_delay_s < min_delay_s:
            raise ValueError('require 0 <= min_delay_s <= max_delay_s')
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s
        self.cooldown_every = cooldown_every
        self.cooldown_s = cooldown_s
        self.cooldown_jitter_s = cooldown_jitter_s
        self.sleep = sleep
        self.rng = rng if rng is not None else random.Random()
        self.attempts = 0

    def after_attempt(self) -> float:
        """Pause after a message attempt; take a longer cooldown on interval.

        Returns the elapsed wait in seconds. Every non-aborted recipient attempt
        counts, because repeated navigation is itself a signal.
        """
        self.attempts += 1
        if self.cooldown_every > 0 and self.attempts % self.cooldown_every == 0:
            wait = self.cooldown_s + self.rng.uniform(0.0, self.cooldown_jitter_s)
        else:
            wait = self.rng.uniform(self.min_delay_s, self.max_delay_s)
        self.sleep(wait)
        return wait
