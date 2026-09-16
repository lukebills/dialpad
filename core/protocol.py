"""CH57x-2 (1189:8890) packet encoder. This module performs no device I/O.

Packet layout adapted from kriomant/ch57x-keyboard-tool (MIT); see
THIRD_PARTY_LICENSE.txt. USB packets include their leading command/report byte;
do not automatically prepend a HID report ID without checking the descriptor.
"""

VID = 0x1189
PID = 0x8890
ENDPOINT = 0x02
PACKET_SIZE = 64
INITIALIZE_PACKET = bytes(PACKET_SIZE)
CONTROL_IDS = {**{f"key{i}": i for i in range(1, 7)},
               "dial_ccw": 13, "dial_press": 14, "dial_cw": 15}
MODIFIERS = {"ctrl": 1, "shift": 2, "alt": 4, "cmd": 8, "win": 8,
             "rctrl": 16, "rshift": 32, "ralt": 64, "rcmd": 128, "rwin": 128}
KEY_CODES = {chr(65+i): 4+i for i in range(26)}
KEY_CODES['NONE'] = 0  # Modifier-only chord; not the Apple-specific Fn key.
KEY_CODES.update({str((i+1) % 10): 30+i for i in range(10)})
KEY_CODES.update(dict(zip([
    "ENTER", "ESCAPE", "BACKSPACE", "TAB", "SPACE", "MINUS", "EQUAL",
    "LEFTBRACKET", "RIGHTBRACKET", "BACKSLASH", "NONUSHASH", "SEMICOLON",
    "QUOTE", "GRAVE", "COMMA", "DOT", "SLASH", "CAPSLOCK"], range(40, 58))))
KEY_CODES.update({f"F{i}": 57+i for i in range(1, 13)})
KEY_CODES.update(dict(zip([
    "PRINTSCREEN", "SCROLLLOCK", "PAUSE", "INSERT", "HOME", "PAGEUP",
    "DELETE", "END", "PAGEDOWN", "RIGHT", "LEFT", "DOWN", "UP"], range(70, 83))))
KEY_CODES.update({f"F{i}": 104+i-13 for i in range(13, 25)})
KEY_CODES.update({"ESC": 41, "RETURN": 40, "PERIOD": 55})
MEDIA_CODES = {"volume_up": 0xe9, "volume_down": 0xea, "mute": 0xe2,
               "play_pause": 0xcd, "next": 0xb5, "previous": 0xb6,
               "stop": 0xb7, "brightness_up": 0x6f, "brightness_down": 0x70}
MOUSE_ACTIONS = {"wheel_up": (0, 1), "wheel_down": (0, -1),
                 "left_click": (1, 0), "right_click": (2, 0), "middle_click": (4, 0)}
MULTI_TAP_TRIGGERS = dict(zip((f'key{i}' for i in range(1, 7)), ('F13', 'F14', 'F15', 'F16', 'F17', 'F20')))
RESERVED_TRIGGERS = set(MULTI_TAP_TRIGGERS.values()) | {'F18', 'F19'}
MULTI_TAP_KEYS = (set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') | {f'F{i}' for i in range(1, 13)} |
                  set('NONE ENTER ESCAPE TAB SPACE BACKSPACE DELETE UP DOWN LEFT RIGHT HOME END PAGEUP PAGEDOWN MINUS EQUAL LEFTBRACKET RIGHTBRACKET BACKSLASH SEMICOLON QUOTE GRAVE COMMA DOT SLASH CAPSLOCK'.split()))


def _packet(*values: int) -> bytes:
    return bytes(values).ljust(PACKET_SIZE, b"\x00")


def _modifiers(value, mouse=False):
    if not isinstance(value, list):
        raise ValueError("modifiers must be a list")
    mask = 0
    for item in value:
        if not isinstance(item, str) or item.lower() not in MODIFIERS:
            raise ValueError(f"Unknown modifier: {item!r}")
        mask |= MODIFIERS[item.lower()]
    if mouse and mask not in (0, 1, 2, 4):
        raise ValueError("Mouse actions support one of ctrl, shift, alt")
    return mask


def _fields(action, allowed):
    unknown = set(action) - allowed
    if unknown:
        raise ValueError(f"Unsupported action fields: {sorted(map(str, unknown))}")


def encode_binding(control: str, action: dict, layer: int = 1) -> list[bytes]:
    """Encode one binding as 64-byte USB reports (no initialization packet).

    Layers are one-based and restricted to the three common physical layers.
    Shortcut: {'type':'shortcut','key':'ENTER','modifiers':['ctrl']}.
    Mouse/media: {'type':'mouse','action':'wheel_up'} / media volume_up.
    Optional shortcut sequence: {'type':'sequence','steps':[shortcut, ...]}.
    A sequence has 1–5 steps, no delays. Names are case-insensitive.
    Raises ValueError before returning any packets on invalid input.
    """
    if not isinstance(control, str) or control not in CONTROL_IDS:
        raise ValueError("Unknown control; use key1..key6 or dial_ccw/press/cw")
    if type(layer) is not int or not 1 <= layer <= 3:
        raise ValueError("layer must be an integer from 1 to 3")
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    kind = action.get("type")
    if kind == 'multi_tap':
        _fields(action, {'type', 'window_ms', 'single', 'double', 'triple'})
        if control not in MULTI_TAP_TRIGGERS:
            raise ValueError('Multi-tap is available on the six keys only.')
        window = action.get('window_ms', 350)
        if type(window) is not int or not 100 <= window <= 1000:
            raise ValueError('Tap timing must be an integer from 100 to 1000 milliseconds.')
        for name in ('single', 'double', 'triple'):
            leaf = action.get(name)
            if not isinstance(leaf, dict) or leaf.get('type') not in ('shortcut', 'mouse', 'media', 'clipboard'):
                raise ValueError('Each tap needs a shortcut, mouse, media or clipboard action.')
            if leaf['type'] == 'clipboard':
                _fields(leaf, {'type', 'action', 'formatting', 'modifiers'})
                if leaf.get('action') not in ('copy', 'paste', 'cut'):
                    raise ValueError('Clipboard action must be copy, paste or cut.')
                if leaf.get('formatting', 'plain') not in ('plain', 'formatted'):
                    raise ValueError('Choose plain text or original formatting.')
                if leaf.get('modifiers', ['cmd']) not in (['cmd'], ['ctrl'], ['ctrl', 'shift']):
                    raise ValueError('Clipboard actions use Command, Control, or Control + Shift.')
            else:
                encode_binding(control, leaf, layer)
                if any(m not in ('ctrl', 'alt', 'shift', 'cmd') for m in leaf.get('modifiers', [])):
                    raise ValueError('Multi-tap actions support Control, Option/Alt, Shift and Command.')
                if leaf['type'] == 'shortcut':
                    if leaf['key'].upper() not in MULTI_TAP_KEYS:
                        raise ValueError('This key is unavailable for multi-tap shortcuts; function keys support F1–F12.')
                if leaf['type'] == 'media' and leaf['action'].lower() not in ('volume_up', 'volume_down', 'mute', 'play_pause', 'next', 'previous'):
                    raise ValueError('Multi-tap media supports volume, mute, play/pause, next and previous.')
        return encode_binding(control, {'type': 'shortcut', 'key': MULTI_TAP_TRIGGERS[control], 'modifiers': []}, layer)
    if kind == "copy_paste":
        _fields(action, {"type", "modifiers", "formatting", "reset_seconds", "double_tap_cut"})
        if action.get('formatting', 'plain') not in ('plain', 'formatted'):
            raise ValueError('Choose plain text or original formatting.')
        if type(action.get('reset_seconds', 10)) is not int or not 0 <= action.get('reset_seconds', 10) <= 300:
            raise ValueError('Copy reset must be 0–300 seconds (0 means never).')
        if type(action.get('double_tap_cut', True)) is not bool:
            raise ValueError('Double-tap Cut must be on or off.')
        if not control.startswith('key'):
            raise ValueError('Copy / paste is available on the six keys only.')
        if action.get('modifiers', ['cmd']) not in (['cmd'], ['ctrl'], ['ctrl', 'shift']):
            raise ValueError('Copy / Paste uses Command, Control, or Control + Shift.')
        return encode_binding(control, {'type': 'shortcut', 'key': 'F19', 'modifiers': []}, layer)
    key_id = CONTROL_IDS[control]
    packets = [_packet(3, 0xfe, layer, 1, 1)]
    if kind in ("shortcut", "sequence"):
        if kind == "sequence":
            _fields(action, {"type", "steps"})
            steps = action.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 5:
                raise ValueError("A sequence needs 1 to 5 shortcut steps")
        else:
            steps = [action]
        chords = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type", "shortcut") != "shortcut":
                raise ValueError("Every sequence step must be a shortcut")
            _fields(step, {"type", "key", "modifiers"})
            key = step.get("key")
            if not isinstance(key, str) or key.upper() not in KEY_CODES:
                raise ValueError(f"Unknown keyboard key: {key!r}")
            modifiers = _modifiers(step.get("modifiers", []))
            if key.upper() == 'NONE' and not modifiers:
                raise ValueError('A modifier-only shortcut needs at least one modifier')
            chords.append((modifiers, KEY_CODES[key.upper()]))
        for index, (modifiers, code) in enumerate([(0, 0)] + chords):
            packets.append(_packet(3, key_id, layer << 4 | 1, len(chords), index, modifiers, code))
    elif kind == "media":
        _fields(action, {"type", "action"})
        name = action.get("action")
        if not isinstance(name, str) or name.lower() not in MEDIA_CODES:
            raise ValueError(f"Unknown media action: {name!r}")
        code = MEDIA_CODES[name.lower()]
        packets.append(_packet(3, key_id, layer << 4 | 2, code & 255, code >> 8))
    elif kind == "mouse":
        _fields(action, {"type", "action", "modifiers"})
        name = action.get("action")
        if not isinstance(name, str) or name.lower() not in MOUSE_ACTIONS:
            raise ValueError(f"Unknown mouse action: {name!r}")
        buttons, wheel = MOUSE_ACTIONS[name.lower()]
        modifiers = _modifiers(action.get("modifiers", []), mouse=True)
        packets.append(_packet(3, key_id, layer << 4 | 3, buttons, 0, 0, wheel & 255, modifiers))
    else:
        raise ValueError("type must be shortcut, sequence, mouse or media")
    packets.append(_packet(3, 0xaa, 0xaa))
    return packets
