import unittest

from spotify_control import (
    build_album_search_query,
    build_track_search_query,
    find_device,
    strip_command_prefix,
)


class TestStripCommandPrefix(unittest.TestCase):
    def test_strips_play_prefix(self):
        self.assertEqual(strip_command_prefix("play abbey road"), "abbey road")

    def test_strips_tell_artoo_to_play_prefix(self):
        self.assertEqual(strip_command_prefix("tell artoo to play abbey road"), "abbey road")

    def test_strips_tell_artoo_to_prefix(self):
        self.assertEqual(strip_command_prefix("tell artoo to stop"), "stop")

    def test_no_prefix_is_unchanged(self):
        self.assertEqual(strip_command_prefix("abbey road"), "abbey road")


class TestFindDevice(unittest.TestCase):
    def setUp(self):
        self.devices = [
            {"id": "id-1", "name": "GEMMA_Speaker"},
            {"id": "id-2", "name": "Satellite-of-love"},
        ]

    def test_matches_case_insensitive_substring(self):
        device_id, name = find_device(self.devices, "satellite")
        self.assertEqual(device_id, "id-2")
        self.assertEqual(name, "Satellite-of-love")

    def test_matches_exact_name_different_case(self):
        device_id, name = find_device(self.devices, "gemma_speaker")
        self.assertEqual(device_id, "id-1")

    def test_no_match_returns_none_none(self):
        device_id, name = find_device(self.devices, "kitchen")
        self.assertIsNone(device_id)
        self.assertIsNone(name)

    def test_empty_device_list_returns_none_none(self):
        device_id, name = find_device([], "anything")
        self.assertIsNone(device_id)
        self.assertIsNone(name)


class TestBuildAlbumSearchQuery(unittest.TestCase):
    def test_album_with_artist(self):
        result = build_album_search_query("album abbey road by the beatles")
        self.assertEqual(result, "album:abbey road artist:the beatles")

    def test_album_without_artist(self):
        result = build_album_search_query("album abbey road")
        self.assertEqual(result, "abbey road")


class TestBuildTrackSearchQuery(unittest.TestCase):
    def test_track_with_artist(self):
        result = build_track_search_query("let it be by the beatles")
        self.assertEqual(result, "track:let it be artist:the beatles")

    def test_track_without_artist(self):
        result = build_track_search_query("let it be")
        self.assertEqual(result, "let it be")


if __name__ == "__main__":
    unittest.main()
