"""Windows companion: floating layout, F18 global hotkey and browser editor."""
import ctypes
from ctypes import wintypes
import json
import queue
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
    root.attributes('-topmost', True)
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
            state['pending'] = True
            request('setups/cycle', {}, 'cycle')

    def close():
        state['closed'] = True
        user32.UnregisterHotKey(None, 1)
        user32.UnregisterHotKey(None, 2)
        root.destroy()
        shutdown()

    clipboard = {'copy': True, 'name': None, 'binding': None}

    def alternate_clipboard():
        action = clipboard['binding']
        if not state['enabled'] or not action:
            return
        modifiers = {'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12, 'cmd': 0x5B, 'win': 0x5B}
        keys = [modifiers[m] for m in action.get('modifiers', ['ctrl']) if m in modifiers]
        key = ord('C' if clipboard['copy'] else 'V')
        for modifier in keys:
            user32.keybd_event(modifier, 0, 0, 0)
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, 2, 0)
        for modifier in reversed(keys):
            user32.keybd_event(modifier, 0, 2, 0)
        clipboard['copy'] = not clipboard['copy']

    def describe(action):
        if action.get('type') == 'copy_paste':
            return 'Copy / Paste'
        if action.get('type') == 'shortcut':
            return ' + '.join(action.get('modifiers', []) + ([action['key']] if action['key'] != 'NONE' else []))
        return action.get('action', '').replace('_', ' ')

    def update(data):
        state['enabled'] = data['enabled']
        next_button.configure(state='normal' if data['enabled'] else 'disabled')
        current = data.get('current')
        if current:
            if clipboard['name'] != current['name']:
                clipboard['copy'] = True
                clipboard['name'] = current['name']
            clipboard['binding'] = next((a for a in current['bindings'].values() if a.get('type') == 'copy_paste'), None)
        else:
            clipboard['binding'] = None
        if current:
            labels = current.get('labels', {})
            rows = [f"{i}  {labels.get(f'key{i}', f'Key {i}')} · {describe(current['bindings'][f'key{i}'])}" for i in range(1, 7)]
            text.set(current['name'] + '\n\n' + '\n\n'.join(rows) + '\n\nTurn: ' +
                     describe(current['bindings']['dial_ccw']) + ' / ' + describe(current['bindings']['dial_cw']) + '\nPress dial → Next setup')
            root.title('Dialpad · ' + current['name'])
            if data['generation'] != state['generation']:
                # A brief visual notification without taking focus from the coding app.
                root.configure(bg='#dfecc9')
                root.after(2500, lambda: root.configure(bg='#f5f4ef'))
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
    request('desktop-ready', {'ready': ready and copy_ready, 'error': 'F18 is in use. Close another Dialpad instance or app using F18 and reopen.'}, 'ready')
    webbrowser.open(url)
    tick()
    poll()
    root.mainloop()
