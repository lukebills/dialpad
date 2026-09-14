import unittest

from core.protocol import encode_binding


def fixture(hex_string):
    return bytes.fromhex(hex_string).ljust(64, b"\x00")


class ProtocolTests(unittest.TestCase):
    def test_modifier_only_wispr_chord(self):
        reports = encode_binding('key1', {'type': 'shortcut', 'key': 'NONE', 'modifiers': ['ctrl', 'alt']})
        self.assertEqual(reports[2], fixture('03 01 11 01 01 05 00'))
        with self.assertRaises(ValueError):
            encode_binding('key1', {'type': 'shortcut', 'key': 'NONE', 'modifiers': []})

    def test_upstream_ctrl_a_fixture(self):
        self.assertEqual(encode_binding("key1", {"type": "shortcut", "key": "A", "modifiers": ["ctrl"]}), [
            fixture("03 fe 01 01 01"), fixture("03 01 11 01"),
            fixture("03 01 11 01 01 01 04"), fixture("03 aa aa")])

    def test_upstream_media_fixture(self):
        self.assertEqual(encode_binding("key2", {"type": "media", "action": "volume_up"}), [
            fixture("03 fe 01 01 01"), fixture("03 02 12 e9"), fixture("03 aa aa")])

    def test_upstream_mouse_fixture(self):
        self.assertEqual(encode_binding("key3", {"type": "mouse", "action": "left_click"}), [
            fixture("03 fe 01 01 01"), fixture("03 03 13 01"), fixture("03 aa aa")])

    def test_dial_ids_and_signed_wheel(self):
        self.assertEqual(encode_binding("dial_ccw", {"type": "mouse", "action": "wheel_up"})[1], fixture("03 0d 13 00 00 00 01"))
        self.assertEqual(encode_binding("dial_cw", {"type": "mouse", "action": "wheel_down"})[1], fixture("03 0f 13 00 00 00 ff"))
        self.assertEqual(encode_binding("dial_press", {"type": "mouse", "action": "middle_click"}, 3)[1], fixture("03 0e 33 04"))

    def test_enter_and_modifier_mask(self):
        self.assertEqual(encode_binding("key6", {"type": "shortcut", "key": "ENTER", "modifiers": ["cmd", "shift", "cmd"]}, 2)[2], fixture("03 06 21 01 01 0a 28"))

    def test_sequence_length_and_indices(self):
        reports = encode_binding("key1", {"type": "sequence", "steps": [{"key": "ESCAPE"}, {"key": "ESCAPE"}]})
        self.assertEqual(reports[1:4], [fixture("03 01 11 02"), fixture("03 01 11 02 01 00 29"), fixture("03 01 11 02 02 00 29")])

    def test_invalid_inputs(self):
        valid = {"type": "shortcut", "key": "ENTER"}
        for control, action, layer in [
            ("key7", valid, 1), ([], valid, 1), ("key1", valid, True),
            ("key1", valid, 0), ("key1", valid, 4), ("key1", valid, 1.0),
            ("key1", [], 1), ("key1", {"type": "shortcut", "key": "Fn"}, 1),
            ("key1", {**valid, "modifiers": "ctrl"}, 1),
            ("key1", {**valid, "modifiers": ["hyper"]}, 1),
            ("key1", {**valid, "delay": 500}, 1),
            ("key1", {"type": "media", "action": "unknown"}, 1),
            ("key1", {"type": "mouse", "action": "wheel_up", "modifiers": ["cmd"]}, 1),
            ("key1", {"type": "mouse", "action": "wheel_up", "modifiers": ["ctrl", "shift"]}, 1),
            ("key1", {"type": "sequence", "steps": []}, 1),
            ("key1", {"type": "sequence", "steps": [valid] * 6}, 1),
        ]:
            with self.subTest(control=control, action=action, layer=layer):
                with self.assertRaises(ValueError):
                    encode_binding(control, action, layer)


if __name__ == "__main__":
    unittest.main()
