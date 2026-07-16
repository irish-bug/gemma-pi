import json
import unittest
from unittest import mock

from gemma_runtime import (
    WAKE_WORD_THRESHOLD,
    is_listener_locked_out,
    load_remote_audio_nodes,
    wake_word_detected,
)


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


class TestLoadRemoteAudioNodes(unittest.TestCase):
    """Covers the sputnik-node addition: config/nodes.json is gitignored
    (real IPs aren't committed), and it holds non-audio entries (myne) that
    gemma_runtime must not try to open a mic/speaker TCP listener against."""

    def test_missing_config_file_returns_no_nodes(self):
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(load_remote_audio_nodes(), {})

    def test_malformed_config_returns_no_nodes(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="not json")):
            self.assertEqual(load_remote_audio_nodes(), {})

    def test_filters_to_known_audio_relay_nodes_only(self):
        config = json.dumps({
            "satellite": {"host": "192.168.1.213", "mic_port": 10700, "spk_port": 10701},
            "sputnik": {"host": "192.168.1.222", "mic_port": 10700, "spk_port": 10701},
            "myne": {"host": "169.254.234.8", "port": 9000},
        })
        with mock.patch("builtins.open", mock.mock_open(read_data=config)):
            nodes = load_remote_audio_nodes()

        self.assertEqual(set(nodes), {"satellite", "sputnik"})
        self.assertEqual(nodes["sputnik"], {"host": "192.168.1.222", "mic_port": 10700, "spk_port": 10701})

    def test_missing_audio_node_key_is_simply_absent(self):
        config = json.dumps({"myne": {"host": "169.254.234.8", "port": 9000}})
        with mock.patch("builtins.open", mock.mock_open(read_data=config)):
            self.assertEqual(load_remote_audio_nodes(), {})


if __name__ == "__main__":
    unittest.main()
