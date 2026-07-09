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


class TestRawShellFallback(unittest.TestCase):
    def test_restart_gemma_calls_systemctl(self):
        with mock.patch("artoo_tools.subprocess.run") as run:
            result = artoo_tools.local_artoo_executor("restart gemma", "local")
        run.assert_called_once_with(["systemctl", "--user", "restart", "gemma.service"], check=True)
        self.assertEqual(result, "Successfully restarted the Gemma service.")

    def test_safelisted_command_executes(self):
        with mock.patch("artoo_tools.subprocess.check_output", return_value="up 3 days\n") as check_output:
            result = artoo_tools.local_artoo_executor("uptime", "local")
        check_output.assert_called_once_with("uptime", shell=True, text=True, stderr=subprocess.STDOUT)
        self.assertEqual(result, "System Output:\nup 3 days")

    def test_non_safelisted_command_is_rejected_without_executing(self):
        with mock.patch("artoo_tools.subprocess.check_output") as check_output, \
             mock.patch("artoo_tools.subprocess.run") as run:
            result = artoo_tools.local_artoo_executor("rm -rf /", "local")

        check_output.assert_not_called()
        run.assert_not_called()
        self.assertIn("is not in the safe-list", result)

    def test_shell_command_failure_returns_captured_output(self):
        error = subprocess.CalledProcessError(1, ["df", "-h"], output="df: command not found")
        with mock.patch("artoo_tools.subprocess.check_output", side_effect=error):
            result = artoo_tools.local_artoo_executor("df -h", "local")
        self.assertEqual(result, "Command failed: df: command not found")


if __name__ == "__main__":
    unittest.main()
