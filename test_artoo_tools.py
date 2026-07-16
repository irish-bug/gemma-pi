import json
import subprocess
import unittest
from unittest import mock

import artoo_tools


class TestSpotifyRouting(unittest.TestCase):
    def test_play_command_routes_to_spotify_script_with_target_node(self):
        with mock.patch("artoo_tools.subprocess.check_output", return_value="Success: Playing track.\n") as check_output:
            result = artoo_tools.local_artoo_executor("play let it be", "satellite")

        self.assertEqual(result, "Success: Playing track.")
        args, kwargs = check_output.call_args
        argv = args[0]
        self.assertEqual(argv[1], "/home/shane/google-labs/spotify_control.py")
        self.assertEqual(argv[2], "play let it be")
        self.assertEqual(argv[3], "satellite")
        self.assertEqual(kwargs.get("stderr"), subprocess.STDOUT)

    def test_stop_command_routes_to_spotify(self):
        with mock.patch("artoo_tools.subprocess.check_output", return_value="Success: paused.\n"):
            result = artoo_tools.local_artoo_executor("stop", "local")
        self.assertEqual(result, "Success: paused.")

    def test_spotify_failure_returns_captured_output(self):
        error = subprocess.CalledProcessError(1, ["spotify_control.py"], output="Error: Device Offline\n")
        with mock.patch("artoo_tools.subprocess.check_output", side_effect=error):
            result = artoo_tools.local_artoo_executor("play abbey road", "local")
        self.assertEqual(result, "Error executing Spotify command: Error: Device Offline")


class TestHomeAssistantRouting(unittest.TestCase):
    def test_light_command_returns_simulated_success(self):
        result = artoo_tools.local_artoo_executor("turn on the hallway light", "local")
        self.assertIn("Simulated Home Assistant success", result)

    def test_plug_command_matches_plug_keyword(self):
        result = artoo_tools.local_artoo_executor("plug in the fan", "local")
        self.assertIn("Simulated Home Assistant success", result)


class TestWeightLogging(unittest.TestCase):
    def test_logs_weight_with_decimal_value(self):
        m = mock.mock_open()
        with mock.patch("builtins.open", m):
            result = artoo_tools.local_artoo_executor("log my weight as 185.4 lbs", "local")

        m.assert_called_once_with("/home/shane/google-labs/memory/weight_tracker.txt", "a")
        written = m().write.call_args[0][0]
        self.assertIn("185.4 lbs", written)
        self.assertIn("Successfully logged weight: 185.4 lbs.", result)

    def test_logs_weight_with_integer_value(self):
        m = mock.mock_open()
        with mock.patch("builtins.open", m):
            artoo_tools.local_artoo_executor("weigh 190 pounds", "local")
        written = m().write.call_args[0][0]
        self.assertIn("190 lbs", written)

    def test_no_number_found_does_not_touch_the_file(self):
        with mock.patch("builtins.open", mock.mock_open()) as m:
            result = artoo_tools.local_artoo_executor("weigh in please", "local")
        m.assert_not_called()
        self.assertIn("Could not detect a valid number", result)


class TestArtooEscalation(unittest.TestCase):
    """Covers the v3.0.0 refactor: unrecognized commands (not Spotify/Home
    Assistant/weight logging) now check Myne Jr's cache and, on a miss, hand
    off to the real Artoo reasoning agent (agy) instead of a hardcoded shell
    safelist."""

    def setUp(self):
        # _myne_url reads a gitignored config file that doesn't exist in a
        # fresh checkout -- stub it directly so tests don't depend on it.
        patcher = mock.patch("artoo_tools._myne_url", side_effect=lambda path: f"http://myne.test{path}")
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_myne_cache_hit_returns_cached_answer_without_calling_artoo(self):
        hit_response = mock.Mock()
        hit_response.json.return_value = {"hit": True, "answer": "It's 72 degrees.", "source": "learned_cache"}
        with mock.patch("artoo_tools.requests.post", return_value=hit_response) as post, \
             mock.patch("artoo_tools.subprocess.check_output") as check_output:
            result = artoo_tools.local_artoo_executor("what's the weather", "local")

        self.assertEqual(result, "It's 72 degrees.")
        post.assert_called_once_with("http://myne.test/query", json={"text": "what's the weather"}, timeout=5)
        check_output.assert_not_called()

    def test_myne_miss_escalates_to_agy_and_learns_the_answer(self):
        miss_response = mock.Mock()
        miss_response.json.return_value = {"hit": False}
        with mock.patch("artoo_tools.requests.post", return_value=miss_response) as post, \
             mock.patch("artoo_tools.subprocess.check_output", return_value="Sure, the lab is Room 4.\n") as check_output:
            result = artoo_tools.local_artoo_executor("where is the lab", "satellite")

        self.assertEqual(result, "Sure, the lab is Room 4.")

        argv, kwargs = check_output.call_args
        self.assertEqual(argv[0][:3], [artoo_tools.AGY_BIN, "--print", artoo_tools.build_artoo_prompt("where is the lab", "satellite")])
        self.assertIn("--dangerously-skip-permissions", argv[0])
        self.assertEqual(kwargs["cwd"], artoo_tools.AGY_WORKDIR)

        query_call, learn_call = post.call_args_list
        self.assertEqual(query_call.args[0], "http://myne.test/query")
        self.assertEqual(learn_call.args[0], "http://myne.test/learn")
        self.assertEqual(learn_call.kwargs["json"], {"query": "where is the lab", "answer": "Sure, the lab is Room 4."})

    def test_myne_unreachable_falls_through_to_agy(self):
        with mock.patch("artoo_tools.requests.post", side_effect=artoo_tools.requests.exceptions.ConnectionError):
            with mock.patch("artoo_tools.subprocess.check_output", return_value="Answered anyway.") as check_output:
                result = artoo_tools.local_artoo_executor("tell me a joke", "local")

        self.assertEqual(result, "Answered anyway.")
        check_output.assert_called_once()

    def test_agy_failure_returns_apology_without_poisoning_the_cache(self):
        miss_response = mock.Mock()
        miss_response.json.return_value = {"hit": False}
        error = subprocess.CalledProcessError(1, ["agy"], output="model overloaded")
        with mock.patch("artoo_tools.requests.post", return_value=miss_response) as post, \
             mock.patch("artoo_tools.subprocess.check_output", side_effect=error):
            result = artoo_tools.local_artoo_executor("what is the capital of colorado", "local")

        self.assertIn("didn't respond", result)
        # Only the /query call should have happened -- no /learn call with a failed answer.
        post.assert_called_once()

    def test_agy_timeout_returns_apology(self):
        miss_response = mock.Mock()
        miss_response.json.return_value = {"hit": False}
        timeout = subprocess.TimeoutExpired(cmd=["agy"], timeout=artoo_tools.AGY_TIMEOUT_S)
        with mock.patch("artoo_tools.requests.post", return_value=miss_response), \
             mock.patch("artoo_tools.subprocess.check_output", side_effect=timeout):
            result = artoo_tools.local_artoo_executor("what is the capital of colorado", "local")

        self.assertIn("didn't respond", result)


class TestMyneUrlResolution(unittest.TestCase):
    def test_returns_none_when_config_file_is_missing(self):
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertIsNone(artoo_tools._myne_url("/query"))

    def test_builds_url_from_config(self):
        config = json.dumps({"myne": {"host": "169.254.234.8", "port": 9000}})
        with mock.patch("builtins.open", mock.mock_open(read_data=config)):
            self.assertEqual(artoo_tools._myne_url("/query"), "http://169.254.234.8:9000/query")


if __name__ == "__main__":
    unittest.main()
