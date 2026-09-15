"""Companion state tests: all transfers are mocked, settings isolated."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
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
        self.setups.last_switch=0
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
        self.setups.last_switch=0
        with self.assertRaises(OSError):
            self.setups.cycle(Mock(side_effect=OSError('unplugged')),profile_packets)
        loaded=Setups(validate_profile,self.path)
        loaded.restore()
        self.assertFalse(loaded.enabled)

    def test_single_template_press_does_not_rewrite(self):
        self.setups.activate(self.setups.snapshot(['A']),'mock')
        self.setups.last_switch=0
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
