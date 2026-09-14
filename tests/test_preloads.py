import copy
import json
from pathlib import Path
import tempfile
import unittest

from app import ROOT, Setups, validate_profile


class PreloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'setups.json'
        self.catalog = json.loads((ROOT / 'ui/starters.json').read_text())
        self.defaults = list(self.catalog['mac'].values())
        self.store = Setups(validate_profile, self.path)

    def test_fresh_install_has_four_valid_layouts_without_arming(self):
        for profiles in self.catalog.values():
            for profile in profiles.values():
                validate_profile(profile)
        self.store.install_defaults(self.defaults)
        self.assertEqual([p['starter_id'] for p in self.store.profiles], ['media-mac', 'web-mac', 'word-mac', 'mail-mac'])
        self.assertFalse(self.store.enabled)
        self.assertEqual(self.catalog['mac']['mail']['bindings']['key1'], {'type':'shortcut','key':'NONE','modifiers':['ctrl','cmd','alt']})

    def test_upgrade_preserves_existing_and_matches_layer(self):
        existing = copy.deepcopy(self.defaults[0])
        existing.pop('starter_id')
        existing['name'] = 'My coding setup'
        existing['layer'] = 2
        self.store.save([existing])
        self.store.install_defaults(self.defaults)
        self.assertEqual(self.store.profiles[0], existing)
        self.assertEqual(len(self.store.profiles), 5)
        self.assertTrue(all(p['layer'] == 2 for p in self.store.profiles))

    def test_relaunch_preserves_renamed_edited_and_removed_defaults(self):
        self.store.install_defaults(self.defaults)
        edited = copy.deepcopy(self.store.profiles)
        edited[0]['name'] = 'My music'
        edited[0]['bindings']['key1'] = {'type':'media','action':'mute'}
        edited.pop()
        self.store.save(edited)
        reloaded = Setups(validate_profile, self.path)
        reloaded.install_defaults(self.defaults)
        self.assertEqual(reloaded.profiles, edited)

    def test_full_library_is_not_replaced_and_corrupt_library_is_not_overwritten(self):
        existing = []
        for i in range(8):
            profile = copy.deepcopy(self.defaults[0])
            profile.pop('starter_id')
            profile['name'] = str(i)
            existing.append(profile)
        self.store.save(existing)
        self.store.install_defaults(self.defaults)
        self.assertEqual(self.store.profiles, existing)
        self.path.write_text('{broken')
        reloaded = Setups(validate_profile, self.path)
        reloaded.install_defaults(self.defaults)
        self.assertEqual(self.path.read_text(), '{broken')


if __name__ == '__main__':
    unittest.main()
