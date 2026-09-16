import copy
import unittest

import app
from core.multi_tap import MultiTapGesture
from core.protocol import encode_binding, MULTI_TAP_TRIGGERS


def binding():
    return {'type': 'multi_tap', 'window_ms': 350,
            **{name: {'type': 'clipboard', 'action': operation, 'formatting': 'plain', 'modifiers': ['cmd']}
               for name, operation in zip(('single', 'double', 'triple'), ('copy', 'paste', 'cut'))}}


class MultiTapTests(unittest.TestCase):
    def test_single_double_and_triple_are_exclusive(self):
        for count, expected in ((1, 'single'), (2, 'double'), (3, 'triple')):
            gesture = MultiTapGesture()
            emitted = []
            for i in range(count):
                emitted.extend(gesture.tap(i * .2))
            if gesture.count:
                emitted.append(gesture.flush())
            self.assertEqual(emitted, [expected])
            self.assertIsNone(gesture.flush())

    def test_window_is_between_taps_and_customizable(self):
        gesture = MultiTapGesture()
        self.assertEqual(gesture.tap(0), [])
        self.assertEqual(gesture.tap(.3), [])
        self.assertEqual(gesture.tap(.6), ['triple'])
        self.assertEqual(gesture.tap(1, 100), [])
        self.assertEqual(gesture.tap(1.2, 100), ['single'])
        self.assertEqual(gesture.flush(), 'single')

    def test_keys_are_independent_and_cancel_on_reset(self):
        first, second = MultiTapGesture(), MultiTapGesture()
        first.tap(0); second.tap(.1); first.tap(.2)
        self.assertEqual(first.flush(), 'double')
        self.assertEqual(second.flush(), 'single')
        first.tap(1); first.reset()
        self.assertIsNone(first.flush())

    def test_each_physical_key_has_a_distinct_trigger(self):
        for control, trigger in MULTI_TAP_TRIGGERS.items():
            self.assertEqual(encode_binding(control, binding()),
                             encode_binding(control, {'type': 'shortcut', 'key': trigger, 'modifiers': []}))
        for control in ('dial_ccw', 'dial_cw', 'dial_press'):
            with self.assertRaises(ValueError):
                encode_binding(control, binding())

    def test_rejects_invalid_and_recursive_actions(self):
        invalid = [{**binding(), 'window_ms': value} for value in (True, 99, 1001, 350.0, '350', None)]
        invalid += [{**binding(), 'single': leaf} for leaf in (
            binding(), {'type': 'copy_paste'}, {'type': 'sequence', 'steps': []},
            {'type': 'shortcut', 'key': 'F18'}, {'type': 'shortcut', 'key': 'F24'},
            {'type': 'shortcut', 'key': 'A', 'modifiers': ['rctrl']},
            {'type': 'media', 'action': 'brightness_up'},
            {'type': 'clipboard', 'action': 'delete'},
            {'type': 'clipboard', 'action': 'copy', 'formatting': 'html'},
            {'type': 'clipboard', 'action': 'copy', 'modifiers': ['alt']}, None)]
        invalid.append({key: value for key, value in binding().items() if key != 'triple'})
        invalid.append({**binding(), 'delay': 2})
        for action in invalid:
            with self.subTest(action=action), self.assertRaises(ValueError):
                encode_binding('key1', action)

    def test_all_six_buttons_can_have_multitap(self):
        profile = {'version': 1, 'name': 'Multi', 'layer': 1, 'bindings': {
            control: binding() if control.startswith('key') else {'type': 'shortcut', 'key': 'UP'}
            for control in app.CONTROLS}}
        self.assertEqual(app.validate_profile(profile), profile)
        request = {'profile': profile, 'controls': ['key1'], 'device_id': 'mock'}
        with self.assertRaisesRegex(ValueError, 'dial cycle'):
            app.make_preview(request)
        preview = app.make_preview({**request, '_cycle': True})
        self.addCleanup(app.PREVIEWS.pop, preview['nonce'], None)
        self.assertEqual(preview['packet_count'], 5)

    def test_leaf_options_preserved_and_standalone_clipboard_rejected(self):
        action = binding()
        action['double'] = {'type': 'shortcut', 'key': 'NONE', 'modifiers': ['cmd', 'alt', 'ctrl']}
        action['triple'] = {'type': 'mouse', 'action': 'wheel_down'}
        original = copy.deepcopy(action)
        encode_binding('key6', action)
        self.assertEqual(action, original)
        with self.assertRaises(ValueError):
            encode_binding('key1', action['single'])
