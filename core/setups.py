"""Saved layouts and an explicitly armed, session-only setup cycle."""
import copy
import json
import os
from pathlib import Path
import sys
import time


def storage_path():
    base = Path(os.environ.get('APPDATA', Path.home())) if sys.platform == 'win32' else Path.home() / 'Library/Application Support'
    return base / 'Dialpad' / 'setups.json'


class Setups:
    def __init__(self, validate, path=None):
        self.validate = validate
        self.path = path or storage_path()
        self.profiles = []
        self.enabled = False
        self.ready = False
        self.active = None
        self.device_id = None
        self.cycle_profiles = []
        self.generation = 0
        self.last_switch = 0
        self.error = ''
        try:
            if self.path.exists():
                if self.path.stat().st_size > 262144:
                    raise ValueError('Saved setups file is too large.')
                self.profiles = self.checked(json.loads(self.path.read_text()))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            self.error = 'Could not load saved setups: ' + str(exc)

    def checked(self, profiles):
        if not isinstance(profiles, list) or len(profiles) > 8:
            raise ValueError('Save up to eight setups.')
        result = copy.deepcopy(profiles)
        for profile in result:
            self.validate(profile)
            labels = profile.get('labels', {})
            if not isinstance(labels, dict) or any(not isinstance(v, str) or len(v) > 32 for v in labels.values()):
                raise ValueError('Setup labels must be text of at most 32 characters.')
        if len({p['name'] for p in result}) != len(result):
            raise ValueError('Give each setup a different name.')
        return result

    def save(self, profiles):
        checked = self.checked(profiles)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            json.dump(checked, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self.profiles = checked
        # An enabled cycle keeps its reviewed snapshot until explicitly re-enabled.
        return self.state()

    def snapshot(self):
        if not self.ready:
            raise ValueError('Open the desktop app first. Its global dial shortcut must be available.')
        if len(self.profiles) < 2:
            raise ValueError('Save at least two setups to cycle through.')
        if len({p['layer'] for p in self.profiles}) != 1:
            raise ValueError('Cycling setups must use the same hardware layer.')
        profiles = copy.deepcopy(self.profiles)
        for profile in profiles:
            profile['bindings']['dial_press'] = {'type': 'shortcut', 'key': 'F18', 'modifiers': []}
            profile.setdefault('labels', {})['dial_press'] = 'Next setup'
        return profiles

    def disable(self, error=''):
        self.enabled = False
        self.error = error
        self.active = None
        self.generation += 1

    def activate(self, profiles, device_id):
        self.cycle_profiles = copy.deepcopy(profiles)
        self.device_id = device_id
        self.active = 0
        self.enabled = True
        self.error = ''
        self.last_switch = time.monotonic()
        self.generation += 1

    def cycle(self, write, packets):
        if not self.enabled or not self.ready:
            raise ValueError('Setup cycling is off. Enable it from the app first.')
        if time.monotonic() - self.last_switch < 1.2:
            return self.state()
        index = (self.active + 1) % len(self.cycle_profiles)
        self.last_switch = time.monotonic()
        try:
            write(self.device_id, packets(self.cycle_profiles[index]))
        except Exception as exc:
            self.disable('Switch failed; keypad state is unknown. ' + str(exc))
            raise
        self.active = index
        self.generation += 1
        return self.state()

    def state(self):
        return {'profiles': copy.deepcopy(self.profiles), 'enabled': self.enabled,
                'ready': self.ready, 'active': self.active, 'generation': self.generation,
                'current': copy.deepcopy(self.cycle_profiles[self.active]) if self.enabled else None,
                'cycle_names': [p['name'] for p in self.cycle_profiles] if self.enabled else [],
                'error': self.error}
