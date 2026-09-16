"""Companion state tests: all transfers are mocked, settings isolated."""
import tempfile
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from app import Setups, validate_profile, profile_packets
from core.protocol import encode_binding
from test_server import profile

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'setups.json'
        self.setups = Setups(validate_profile, self.path)
        a, b = profile(), profile()
        a['name'], b['name'] = 'A', 'B'
        self.setups.save([a,b])
        self.setups.ready = True

    def test_rapid_presses_each_advance_without_cooldown(self):
        self.setups.activate(self.setups.snapshot(), 'mock')
        writer = Mock()
        for index in range(15):
            state = self.setups.cycle(writer, profile_packets)
            self.assertEqual(state['active'], (index + 1) % 2)
        self.assertEqual(writer.call_count, 15)

    def test_order_separate_from_library_and_persistent(self):
        self.setups.save_order(['B','A'])
        self.assertEqual([p['name'] for p in self.setups.snapshot()], ['B','A'])
        self.assertEqual([p['name'] for p in self.setups.profiles], ['A','B'])
        loaded = Setups(validate_profile,self.path)
        self.assertEqual(loaded.order,['B','A'])
        with self.assertRaises(ValueError):
            self.setups.save_order(['A','A'])
        with self.assertRaises(ValueError):
            self.setups.save_order(['missing'])

    def test_restart_restores_reviewed_snapshot_without_writes(self):
        self.setups.activate(self.setups.snapshot(), 'mock')
        writer=Mock(side_effect=lambda *_: self.assertFalse(self.path.with_name('active-cycle.json').exists()))
        self.setups.cycle(writer,profile_packets)
        loaded=Setups(validate_profile,self.path)
        self.assertFalse(loaded.enabled)
        loaded.ready=True
        loaded.restore()
        self.assertTrue(loaded.enabled)
        self.assertEqual(loaded.state()['current']['name'],'B')
        self.assertEqual(writer.call_count,1)
        loaded.disable()
        again=Setups(validate_profile,self.path)
        again.restore()
        self.assertFalse(again.enabled)

    def test_failure_clears_restart_marker(self):
        self.setups.activate(self.setups.snapshot(),'mock')
        with self.assertRaises(OSError):
            self.setups.cycle(Mock(side_effect=OSError('unplugged')),profile_packets)
        loaded=Setups(validate_profile,self.path)
        loaded.restore()
        self.assertFalse(loaded.enabled)

    def test_single_template_press_does_not_rewrite(self):
        self.setups.activate(self.setups.snapshot(['A']),'mock')
        writer=Mock()
        self.setups.cycle(writer,profile_packets)
        writer.assert_not_called()

    def test_copy_paste_encoding_and_constraints(self):
        toggle={'type':'copy_paste','modifiers':['cmd']}
        self.assertEqual(encode_binding('key5',toggle),encode_binding('key5',{'type':'shortcut','key':'F19','modifiers':[]}))
        with self.assertRaises(ValueError):
            encode_binding('dial_press',toggle)
        with self.assertRaises(ValueError):
            encode_binding('key1',{'type':'copy_paste','modifiers':[]})
        p=profile()
        p['bindings']['key4']=toggle
        p['bindings']['key5']=toggle
        with self.assertRaises(ValueError):
            validate_profile(p)

    def test_upsert_rename_preserves_order_and_reviewed_runtime(self):
        self.setups.save_order(['B', 'A'])
        self.setups.activate(self.setups.snapshot(), 'mock')
        runtime = self.path.with_name('active-cycle.json').read_bytes()
        original = copy.deepcopy(self.setups.profiles[0])
        edited = copy.deepcopy(original)
        edited['name'] = 'Renamed A'
        edited['bindings']['key1']['key'] = 'TAB'
        state = self.setups.upsert(edited, 'A', original)
        self.assertEqual(state['order'], ['B', 'Renamed A'])
        self.assertEqual(state['cycle_names'], ['B', 'A'])
        self.assertEqual(self.path.with_name('active-cycle.json').read_bytes(), runtime)
        loaded = Setups(validate_profile, self.path)
        self.assertEqual(loaded.profiles[0], edited)
        self.assertEqual(loaded.order, ['B', 'Renamed A'])

    def test_upsert_rejects_stale_updates_and_collisions_without_clobbering(self):
        initial = copy.deepcopy(self.setups.profiles)
        edited = copy.deepcopy(initial[0])
        edited['name'] = 'B'
        stale = copy.deepcopy(initial[0])
        stale['bindings']['key1']['key'] = 'TAB'
        before = self.path.read_bytes()
        for arguments in ((edited, 'A'), (initial[0], None),
                          (initial[0], 'missing'), (initial[0], 'A', stale),
                          (initial[0], [])):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.setups.upsert(*arguments)
        self.assertEqual(self.setups.profiles, initial)
        self.assertEqual(self.path.read_bytes(), before)

    def test_upsert_new_setup_preserves_unrelated_edits_and_cycle_selection(self):
        self.setups.save_order(['B'])
        original = copy.deepcopy(self.setups.profiles[0])
        edited = copy.deepcopy(original)
        edited['bindings']['key1']['key'] = 'TAB'
        self.setups.upsert(edited, 'A', original)
        new = profile()
        new['name'] = 'C'
        self.setups.upsert(new, None)
        self.assertEqual(self.setups.profiles, [edited, self.setups.profiles[1], new])
        self.assertEqual(self.setups.order, ['B'])

    def test_unicode_persistence_does_not_use_system_text_encoding(self):
        original_open = Path.open
        def legacy_open(path, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
            # Reproduce Windows systems whose default text encoding is cp1252.
            if 'b' not in mode and encoding is None:
                encoding = 'cp1252'
            return original_open(path, mode, buffering, encoding, errors, newline)
        setup = profile()
        setup['name'] = '编码 ⌘ → café'
        setup['labels'] = {'key1': '复制 📋'}
        setup['starter_id'] = 'unicode-fixture'
        with patch.object(Path, 'open', legacy_open):
            self.setups.install_defaults([setup])
            self.setups.save_order([setup['name']])
            self.setups.activate(self.setups.snapshot(), 'mock')
            loaded = Setups(validate_profile, self.path)
            loaded.restore()
        self.assertFalse(loaded.load_failed)
        self.assertEqual(loaded.profiles[-1], setup)
        self.assertEqual(loaded.order, [setup['name']])
        self.assertEqual(loaded.state()['current']['labels']['key1'], '复制 📋')
        self.assertIn('编码', self.path.read_bytes().decode('utf-8'))
