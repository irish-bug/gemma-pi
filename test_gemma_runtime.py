import unittest

from gemma_runtime import WAKE_WORD_THRESHOLD, is_listener_locked_out, wake_word_detected


class TestIsListenerLockedOut(unittest.TestCase):
    """Covers the v18.2.18 double-session race-condition fix: a listener must
    not run wake-word detection whenever active_node is already claimed, even
    before session_active_event is set (see gemma_runtime.py's docstring on
    is_listener_locked_out for the race window this closes)."""

    def test_unlocked_when_no_node_claimed(self):
        self.assertFalse(is_listener_locked_out(None))

    def test_locked_when_local_has_claimed(self):
        self.assertTrue(is_listener_locked_out("local"))

    def test_locked_when_satellite_has_claimed(self):
        self.assertTrue(is_listener_locked_out("satellite"))

    def test_locked_for_any_truthy_node_value(self):
        # The function only cares whether a node has claimed the lock, not
        # which one -- a listener checking its own name is handled by the
        # caller (session_active_event branch), not this guard.
        self.assertTrue(is_listener_locked_out("chores"))


class TestWakeWordDetected(unittest.TestCase):
    def test_score_above_threshold_triggers(self):
        self.assertTrue(wake_word_detected(0.71))

    def test_score_at_threshold_does_not_trigger(self):
        # Original inline check was a strict `>`, not `>=` -- preserve that.
        self.assertFalse(wake_word_detected(WAKE_WORD_THRESHOLD))

    def test_score_below_threshold_does_not_trigger(self):
        self.assertFalse(wake_word_detected(0.69))

    def test_custom_threshold_overrides_default(self):
        self.assertTrue(wake_word_detected(0.5, threshold=0.4))
        self.assertFalse(wake_word_detected(0.5, threshold=0.6))


if __name__ == "__main__":
    unittest.main()
