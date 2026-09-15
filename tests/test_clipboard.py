import unittest
from core.clipboard_gesture import ClipboardGesture
from core.protocol import encode_binding

class ClipboardTests(unittest.TestCase):
    def test_single_waits_then_alternates(self):
        g=ClipboardGesture()
        self.assertIsNone(g.tap(0))
        self.assertEqual(g.flush(),'copy')
        g.complete('copy',.32)
        self.assertIsNone(g.tap(1))
        self.assertEqual(g.flush(),'paste')
        g.complete('paste',1.32)
        self.assertEqual(g.tap(2,double_tap=False),'copy')

    def test_double_emits_only_cut_from_either_phase(self):
        for paste_next in (True,False):
            g=ClipboardGesture()
            if paste_next:g.complete('copy',0)
            self.assertIsNone(g.tap(1))
            self.assertEqual(g.tap(1.2),'cut')
            self.assertIsNone(g.pending)
            g.complete('cut',1.2)
            self.assertEqual(g.tap(2,double_tap=False),'paste')

    def test_idle_reset_and_never(self):
        g=ClipboardGesture();g.complete('copy',1)
        self.assertEqual(g.tap(10.9,double_tap=False),'paste')
        self.assertEqual(g.tap(11,double_tap=False),'copy')
        g.complete('copy',12)
        self.assertEqual(g.tap(500,reset_seconds=0,double_tap=False),'paste')
        g.reset()
        self.assertEqual(g.tap(501,double_tap=False),'copy')

    def test_failed_action_does_not_advance(self):
        g=ClipboardGesture()
        self.assertEqual(g.tap(0,double_tap=False),'copy')
        self.assertEqual(g.tap(1,double_tap=False),'copy')

    def test_options_validated_and_do_not_change_usb_trigger(self):
        action={'type':'copy_paste','modifiers':['cmd'],'formatting':'plain','reset_seconds':10,'double_tap_cut':True}
        expected=encode_binding('key5',{'type':'shortcut','key':'F19','modifiers':[]})
        self.assertEqual(encode_binding('key5',action),expected)
        for field,values in [('formatting',['html',None,[]]),('reset_seconds',[-1,301,True,1.5,'10']),('double_tap_cut',[0,'true',None])]:
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    encode_binding('key5',{**action,field:value})
        self.assertEqual(encode_binding('key5',{**action,'formatting':'formatted','reset_seconds':0,'double_tap_cut':False}),expected)
