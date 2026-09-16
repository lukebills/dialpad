"""Template library, selected cycling order and resumable reviewed cycle."""
import copy
import json
import os
from pathlib import Path
import sys

_UNSET = object()


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
        self.error = ''
        self.load_failed = False
        self.show_request = 0
        self.order = None
        self.restored = False
        try:
            order = self.path.with_name('cycle-order.json')
            if order.exists():
                value = json.loads(order.read_text(encoding='utf-8'))
                if isinstance(value, list) and all(isinstance(n, str) for n in value):
                    self.order = value
        except (ValueError, OSError):
            pass
        try:
            if self.path.exists():
                if self.path.stat().st_size > 262144:
                    raise ValueError('Saved setups file is too large.')
                self.profiles = self.checked(json.loads(self.path.read_text(encoding='utf-8')))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            self.load_failed = True
            self.error = 'Could not load saved setups: ' + str(exc)

    def install_defaults(self, profiles):
        """Seed bundled layouts once, preserving edits, removals and existing profiles."""
        if self.load_failed:
            return  # Do not overwrite an unreadable user library.
        defaults = self.checked(profiles)
        marker = self.path.with_name('preloaded-layouts.json')
        try:
            installed = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else []
            if not isinstance(installed, list) or any(not isinstance(v, str) for v in installed):
                raise ValueError('Invalid preload history.')
            installed = set(installed)
            updated = copy.deepcopy(self.profiles)
            layer = updated[0]['layer'] if updated else 1
            for profile in defaults:
                identity = profile['starter_id']
                if identity in installed:
                    continue
                if any(p.get('starter_id') == identity or p['name'] == profile['name'] for p in updated):
                    installed.add(identity)
                    continue
                if len(updated) >= 8:
                    continue  # Still available in Starting layout; retry next launch if space opens.
                profile['layer'] = layer
                updated.append(profile)
                installed.add(identity)
            if updated != self.profiles:
                self.save(updated)
            marker.parent.mkdir(parents=True, exist_ok=True)
            temporary = marker.with_suffix('.tmp')
            temporary.write_text(json.dumps(sorted(installed)), encoding='utf-8')
            temporary.replace(marker)
        except (OSError, ValueError, TypeError) as exc:
            self.error = 'Could not preload all layouts: ' + str(exc)

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

    def save(self, profiles, *, order=_UNSET):
        checked = self.checked(profiles)
        if order is _UNSET:
            order = self.order
        if order is not None:
            if not isinstance(order, list) or any(not isinstance(n, str) for n in order) or len(set(order)) != len(order):
                raise ValueError('Choose distinct setups for the cycle.')
            names = {p['name'] for p in checked}
            order = [n for n in order if n in names]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(checked, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self.profiles = checked
        if order is not None:
            self.save_order(order)
        # An enabled cycle keeps its reviewed snapshot until explicitly re-enabled.
        return self.state()

    def upsert(self, profile, previous_name, expected_profile=_UNSET):
        """Save one editor draft without replacing unrelated setups or the live cycle.

        The HTTP caller holds WRITE_LOCK across validation and persistence. An
        optional stored snapshot prevents an older editor from overwriting a
        setup changed by another editor.
        """
        checked = self.checked([profile])[0]
        if previous_name is not None and (not isinstance(previous_name, str) or not previous_name):
            raise ValueError('Choose the setup being edited.')
        profiles = copy.deepcopy(self.profiles)
        names = [p['name'] for p in profiles]
        if previous_name is None:
            if checked['name'] in names:
                raise ValueError('A setup with that name already exists. Choose a different name.')
            if expected_profile is not _UNSET and expected_profile is not None:
                raise ValueError('A new setup cannot replace an existing setup.')
            profiles.append(checked)
        else:
            if previous_name not in names:
                raise ValueError('This setup was removed or renamed. Select it again before editing.')
            index = names.index(previous_name)
            if expected_profile is not _UNSET and profiles[index] != expected_profile:
                raise ValueError('This setup changed in another editor. Select it again before editing.')
            if checked['name'] != previous_name and checked['name'] in names:
                raise ValueError('A setup with that name already exists. Choose a different name.')
            profiles[index] = checked
        order = self.order
        if order is not None and previous_name is not None:
            order = [checked['name'] if n == previous_name else n for n in order]
        return self.save(profiles, order=order)

    def save_order(self, names):
        self.selected(names)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        target = self.path.with_name('cycle-order.json')
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(names), encoding='utf-8')
        temporary.replace(target)
        self.order = list(names)
        return self.state()

    def selected(self, names=None):
        names = names if names is not None else self.order
        if names is None:
            return copy.deepcopy(self.profiles)
        if not isinstance(names, list) or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
            raise ValueError('Choose distinct templates for the cycle.')
        by_name = {p['name']: p for p in self.profiles}
        if any(n not in by_name for n in names):
            raise ValueError('A cycling template has been removed. Update your cycle.')
        return [copy.deepcopy(by_name[n]) for n in names]

    def persist_runtime(self):
        target = self.path.with_name('active-cycle.json')
        if not self.enabled:
            target.unlink(missing_ok=True)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'profiles': self.cycle_profiles,
            'device_id': self.device_id, 'active': self.active}), encoding='utf-8')
        temporary.replace(target)

    def restore(self):
        if self.restored:
            return
        self.restored = True
        target = self.path.with_name('active-cycle.json')
        if not target.exists():
            return
        try:
            if target.stat().st_size > 262144:
                raise ValueError('Saved cycle is too large.')
            data = json.loads(target.read_text(encoding='utf-8'))
            profiles = self.checked(data['profiles'])
            active = data['active']
            if not profiles or type(active) is not int or not 0 <= active < len(profiles):
                raise ValueError('Invalid active setup.')
            if not isinstance(data['device_id'], str) or not data['device_id']:
                raise ValueError('Invalid saved device.')
            if any(p['bindings']['dial_press'] != {'type': 'shortcut', 'key': 'F18', 'modifiers': []} for p in profiles):
                raise ValueError('Invalid saved dial shortcut.')
            self.cycle_profiles = profiles
            self.active = active
            self.device_id = data['device_id']
            self.enabled = True
            self.generation += 1
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.error = 'Could not restore cycling. Review and enable again. ' + str(exc)

    def snapshot(self, names=None):
        if not self.ready:
            raise ValueError('Open the desktop app first. Its global dial shortcut must be available.')
        profiles = self.selected(names)
        if len(profiles) < 1:
            raise ValueError('Add at least one template to the cycle.')
        if len({p['layer'] for p in profiles}) != 1:
            raise ValueError('Cycling setups must use the same hardware layer.')
        for profile in profiles:
            profile['bindings']['dial_press'] = {'type': 'shortcut', 'key': 'F18', 'modifiers': []}
            profile.setdefault('labels', {})['dial_press'] = 'Next setup'
        return profiles

    def disable(self, error=''):
        self.enabled = False
        self.error = error
        self.restored = True
        self.active = None
        self.persist_runtime()
        self.generation += 1

    def activate(self, profiles, device_id):
        self.cycle_profiles = copy.deepcopy(profiles)
        self.device_id = device_id
        self.active = 0
        self.enabled = True
        self.error = ''
        self.persist_runtime()
        self.generation += 1

    def cycle(self, write, packets):
        if not self.enabled or not self.ready:
            raise ValueError('Setup cycling is off. Enable it from the app first.')
        if len(self.cycle_profiles) == 1:
            return self.state()
        index = (self.active + 1) % len(self.cycle_profiles)
        try:
            # A crash during transfer must not restore a possibly partial layout.
            self.path.with_name('active-cycle.json').unlink(missing_ok=True)
            write(self.device_id, packets(self.cycle_profiles[index]))
        except Exception as exc:
            self.disable('Switch failed; keypad state is unknown. ' + str(exc))
            raise
        self.active = index
        self.persist_runtime()
        self.generation += 1
        return self.state()

    def state(self):
        return {'profiles': copy.deepcopy(self.profiles), 'order': self.order, 'show_request': self.show_request, 'enabled': self.enabled,
                'ready': self.ready, 'active': self.active, 'generation': self.generation,
                'current': copy.deepcopy(self.cycle_profiles[self.active]) if self.enabled else None,
                'cycle_names': [p['name'] for p in self.cycle_profiles] if self.enabled else [],
                'error': self.error}
