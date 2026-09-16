"""Windows companion: floating layout, F18 global hotkey and browser editor."""
import ctypes
from ctypes import wintypes
import json
import queue
import time
from core.clipboard_gesture import ClipboardGesture
from core.multi_tap import MultiTapGesture
import threading
import tkinter as tk
import urllib.request
import webbrowser


def launch(url, shutdown):
    base, token = url.split('#', 1)
    results = queue.Queue()
    user32 = ctypes.windll.user32
    root = tk.Tk()
    root.title('Dialpad · live layout')
    root.geometry('380x400')
    root.configure(bg='#f5f4ef')
    root.iconify()  # Keep the companion in the taskbar; no floating live-layout popup.
    text = tk.StringVar(value='Connecting…')
    tk.Label(root, textvariable=text, bg='#f5f4ef', fg='#293e2f', justify='left',
             wraplength=345, padx=18, pady=18).pack(fill='both', expand=True)
    state = {'enabled': False, 'generation': -1, 'pending': False, 'polling': False, 'closed': False}

    def request(path, body=None, kind='poll'):
        def worker():
            try:
                req = urllib.request.Request(base + 'api/' + path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    results.put((kind, json.load(response), None))
            except Exception as exc:
                results.put((kind, None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def cycle():
        if state['enabled'] and not state['pending']:
            reset_multi()
            state['pending'] = True
            request('setups/cycle', {}, 'cycle')

    def close():
        state['closed'] = True
        for hotkey_id in range(1, 9):
            user32.UnregisterHotKey(None, hotkey_id)
        root.destroy()
        shutdown()

    gesture = ClipboardGesture()
    clipboard = {'context': None, 'binding': None, 'timer': None, 'focus': None, 'busy': False}
    user32.GetForegroundWindow.restype = wintypes.HWND

    def reset_clipboard():
        if clipboard['timer'] is not None:
            root.after_cancel(clipboard['timer'])
        clipboard.update(timer=None, focus=None, busy=False)
        gesture.reset()

    def finish_copy(operation, action, before, context, focus, attempts=25):
        if not state['enabled'] or context != clipboard['context']:
            return
        if user32.GetForegroundWindow() != focus:
            reset_clipboard()
            return
        count = user32.GetClipboardSequenceNumber()
        if count != before:
            if action.get('formatting', 'plain') == 'plain' and not any(user32.IsClipboardFormatAvailable(f) for f in (2, 8, 15, 17)):
                try:
                    value = root.clipboard_get()
                    if user32.GetClipboardSequenceNumber() == count:
                        root.clipboard_clear()
                        root.clipboard_append(value)
                except tk.TclError:
                    pass  # Non-text clipboard data stays untouched.
            clipboard['busy'] = False
            gesture.complete(operation, time.monotonic())
        elif attempts > 1:
            root.after(40, lambda: finish_copy(operation, action, before, context, focus, attempts-1))
        else:
            reset_clipboard()

    def perform_clipboard(operation, action, focus):
        clipboard['timer'] = None
        if not state['enabled'] or state['pending'] or not focus or user32.GetForegroundWindow() != focus:
            reset_clipboard()
            return
        modifiers = {'ctrl': 0x11, 'shift': 0x10, 'cmd': 0x5B}
        keys = [modifiers[m] for m in action.get('modifiers', ['ctrl']) if m in modifiers]
        key = ord({'copy': 'C', 'paste': 'V', 'cut': 'X'}[operation])
        before = user32.GetClipboardSequenceNumber()
        for modifier in keys:
            user32.keybd_event(modifier, 0, 0, 0)
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, 2, 0)
        for modifier in reversed(keys):
            user32.keybd_event(modifier, 0, 2, 0)
        if operation == 'paste':
            gesture.complete(operation, time.monotonic())
        else:
            clipboard['busy'] = True
            context = clipboard['context']
            root.after(40, lambda: finish_copy(operation, action, before, context, focus))

    def alternate_clipboard():
        action = clipboard['binding']
        if not state['enabled'] or state['pending'] or not action or clipboard['busy']:
            return
        focus = user32.GetForegroundWindow()
        if gesture.pending is not None and focus != clipboard['focus']:
            reset_clipboard()
        now = time.monotonic()
        if gesture.pending is not None and now - gesture.pending > gesture.delay:
            root.after_cancel(clipboard['timer'])
            perform_clipboard(gesture.flush(), action, clipboard['focus'])
            return
        if clipboard['timer'] is not None:
            root.after_cancel(clipboard['timer'])
            clipboard['timer'] = None
        clipboard['focus'] = focus
        operation = gesture.tap(now, action.get('reset_seconds', 10), action.get('double_tap_cut', True))
        if operation:
            perform_clipboard(operation, action, focus)
        else:
            clipboard['timer'] = root.after(320, lambda: perform_clipboard(gesture.flush(), action, focus))

    multi = {f'key{i}': {'gesture': MultiTapGesture(), 'timer': None, 'focus': None, 'binding': None} for i in range(1, 7)}

    def reset_multi():
        for item in multi.values():
            if item['timer'] is not None:
                root.after_cancel(item['timer'])
            item.update(timer=None, focus=None)
            item['gesture'].reset()

    def emit_multi(action, focus, context):
        if (not state['enabled'] or state['pending'] or context != clipboard['context'] or
                not focus or focus != user32.GetForegroundWindow()):
            return
        kind = action['type']
        if kind == 'clipboard':
            if not clipboard['busy']:
                reset_clipboard()
                perform_clipboard(action['action'], action, focus)
            return
        modifiers = {'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12, 'cmd': 0x5B}
        held = [modifiers[m] for m in action.get('modifiers', [])]
        for modifier in held:
            user32.keybd_event(modifier, 0, 0, 0)
        try:
            if kind == 'shortcut':
                name = action['key'].upper()
                named = dict(zip('ENTER ESCAPE TAB SPACE BACKSPACE DELETE UP DOWN LEFT RIGHT HOME END PAGEUP PAGEDOWN CAPSLOCK'.split(),
                                 (0x0D, 0x1B, 0x09, 0x20, 0x08, 0x2E, 0x26, 0x28, 0x25, 0x27, 0x24, 0x23, 0x21, 0x22, 0x14)))
                named.update(dict(zip('MINUS EQUAL LEFTBRACKET RIGHTBRACKET BACKSLASH SEMICOLON QUOTE GRAVE COMMA DOT SLASH'.split(),
                                      (0xBD, 0xBB, 0xDB, 0xDD, 0xDC, 0xBA, 0xDE, 0xC0, 0xBC, 0xBE, 0xBF))))
                named.update({f'F{i}': 0x6F+i for i in range(1, 13)})
                if name != 'NONE':
                    key = ord(name) if len(name) == 1 else named[name]
                    extended = 1 if name in ('DELETE', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'HOME', 'END', 'PAGEUP', 'PAGEDOWN') else 0
                    user32.keybd_event(key, 0, extended, 0)
                    user32.keybd_event(key, 0, extended | 2, 0)
            elif kind == 'media':
                key = {'volume_up': 0xAF, 'volume_down': 0xAE, 'mute': 0xAD, 'play_pause': 0xB3, 'next': 0xB0, 'previous': 0xB1}[action['action'].lower()]
                user32.keybd_event(key, 0, 0, 0)
                user32.keybd_event(key, 0, 2, 0)
            elif kind == 'mouse':
                name = action['action'].lower()
                if name.startswith('wheel_'):
                    user32.mouse_event(0x0800, 0, 0, 120 if name == 'wheel_up' else -120, 0)
                else:
                    down, up = {'left_click': (2, 4), 'right_click': (8, 16), 'middle_click': (32, 64)}[name]
                    user32.mouse_event(down, 0, 0, 0, 0)
                    user32.mouse_event(up, 0, 0, 0, 0)
        finally:
            for modifier in reversed(held):
                user32.keybd_event(modifier, 0, 2, 0)

    def multi_tap(control):
        item = multi[control]
        binding = item['binding']
        if not state['enabled'] or state['pending'] or not binding:
            return
        focus = user32.GetForegroundWindow()
        if item['timer'] is not None:
            root.after_cancel(item['timer'])
            item['timer'] = None
        if item['focus'] != focus:
            item['gesture'].reset()
        item['focus'] = focus
        context = clipboard['context']
        for name in item['gesture'].tap(time.monotonic(), binding.get('window_ms', 350)):
            emit_multi(binding[name], focus, context)
        if item['gesture'].count:
            def flush():
                item['timer'] = None
                name = item['gesture'].flush()
                if name:
                    emit_multi(binding[name], focus, context)
            item['timer'] = root.after(binding.get('window_ms', 350), flush)

    def describe(action):
        if action.get('type') == 'multi_tap':
            return ' / '.join(describe(action[name]) for name in ('single', 'double', 'triple'))
        if action.get('type') == 'copy_paste':
            return 'Copy / Paste'
        if action.get('type') == 'shortcut':
            return ' + '.join(action.get('modifiers', []) + ([action['key']] if action['key'] != 'NONE' else []))
        return action.get('action', '').replace('_', ' ')

    def update(data):
        state['enabled'] = data['enabled']
        if not state['enabled']:
            reset_multi()
            reset_clipboard()
        next_button.configure(state='normal' if data['enabled'] else 'disabled')
        current = data.get('current')
        if current:
            context = (current['name'], data['generation'])
            if clipboard['context'] != context:
                reset_clipboard()
                reset_multi()
                clipboard['context'] = context
            clipboard['binding'] = next((a for a in current['bindings'].values() if a.get('type') == 'copy_paste'), None)
            for control, item in multi.items():
                binding = current['bindings'].get(control)
                item['binding'] = binding if binding and binding.get('type') == 'multi_tap' else None
        else:
            reset_clipboard()
            reset_multi()
            for item in multi.values():
                item['binding'] = None
            clipboard['binding'] = None
            clipboard['context'] = None
        if current:
            labels = current.get('labels', {})
            rows = [f"{i}  {labels.get(f'key{i}', f'Key {i}')} · {describe(current['bindings'][f'key{i}'])}" for i in range(1, 7)]
            text.set(current['name'] + '\n\n' + '\n\n'.join(rows) + '\n\nTurn: ' +
                     describe(current['bindings']['dial_ccw']) + ' / ' + describe(current['bindings']['dial_cw']) + '\nPress dial → Next setup')
            root.title('Dialpad · ' + current['name'])
        else:
            root.title('Dialpad · cycling off')
            text.set(data.get('error') or 'Cycling is off.\n\nSave two setups and enable cycling in the editor.\n\nThe keypad keeps its last bindings. Apply a normal layout to restore the dial press.')
        state['generation'] = data['generation']

    def tick():
        msg = wintypes.MSG()
        # RegisterHotKey and PeekMessage run on this same desktop thread.
        while user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
            if msg.wParam == 1:
                cycle()
            elif msg.wParam == 2:
                alternate_clipboard()
            elif 3 <= msg.wParam <= 8:
                multi_tap(f'key{msg.wParam-2}')
        while not results.empty():
            kind, data, error = results.get_nowait()
            if kind == 'cycle':
                state['pending'] = False
            if kind == 'poll':
                state['polling'] = False
            if data:
                update(data)
            elif error:
                text.set('Connection or transfer failed.\n' + error)
                state['enabled'] = False
                reset_clipboard()
                reset_multi()
                clipboard['context'] = None
                next_button.configure(state='disabled')
        root.after(50, tick)

    def poll():
        if not state['polling']:
            state['polling'] = True
            request('setups')
        root.after(750, poll)

    tk.Button(root, text='Open editor', command=lambda: webbrowser.open(url)).pack(pady=3)
    next_button = tk.Button(root, text='Next setup', command=cycle, state='disabled')
    next_button.pack(pady=3)
    tk.Button(root, text='Quit Dialpad', command=close).pack(pady=8)
    root.protocol('WM_DELETE_WINDOW', root.iconify)
    ready = bool(user32.RegisterHotKey(None, 1, 0x4000, 0x81))  # MOD_NOREPEAT, VK_F18
    copy_ready = bool(user32.RegisterHotKey(None, 2, 0x4000, 0x82))
    multi_ready = [bool(user32.RegisterHotKey(None, i+3, 0x4000, key)) for i, key in enumerate((0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0x83))]
    request('desktop-ready', {'ready': ready and copy_ready and all(multi_ready), 'error': 'A reserved F13–F20 shortcut is in use. Close another Dialpad instance or app using these keys and reopen.'}, 'ready')
    webbrowser.open(url)
    tick()
    poll()
    root.mainloop()
