"""Deterministic tests for the messaging pacer; no real sleeping."""

import unittest

from tools.facebook_agent.pacing import MessagePacer


class LowBoundRng:
    """Return the low bound of every range for deterministic assertions."""

    def uniform(self, low, high):
        return low


class PacerTests(unittest.TestCase):
    def build(self, **kwargs):
        self.slept = []
        return MessagePacer(sleep=self.slept.append, rng=LowBoundRng(), **kwargs)

    def test_short_delay_between_recipients(self):
        pacer = self.build(min_delay_s=3.2, max_delay_s=4.5, cooldown_every=50)
        self.assertEqual(pacer.after_attempt(), 3.2)
        self.assertEqual(pacer.after_attempt(), 3.2)
        self.assertEqual(self.slept, [3.2, 3.2])
        self.assertEqual(pacer.attempts, 2)

    def test_cooldown_at_interval(self):
        pacer = self.build(min_delay_s=3.0, max_delay_s=4.0, cooldown_every=2,
                           cooldown_s=100.0, cooldown_jitter_s=60.0)
        waits = [pacer.after_attempt() for _ in range(4)]
        self.assertEqual(waits, [3.0, 100.0, 3.0, 100.0])

    def test_zero_interval_disables_cooldown(self):
        pacer = self.build(min_delay_s=2.0, max_delay_s=2.0, cooldown_every=0)
        waits = [pacer.after_attempt() for _ in range(3)]
        self.assertEqual(waits, [2.0, 2.0, 2.0])

    def test_invalid_configuration(self):
        for kwargs in ({'min_delay_s': -1}, {'min_delay_s': 5.0, 'max_delay_s': 1.0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MessagePacer(**kwargs)


if __name__ == '__main__':
    unittest.main()
