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
        root.destroy()
        shutdown()

    def describe(action):
        if action.get('type') == 'shortcut':
            return ' + '.join(action.get('modifiers', []) + ([action['key']] if action['key'] != 'NONE' else []))
        return action.get('action', '').replace('_', ' ')

    def update(data):
        state['enabled'] = data['enabled']
        next_button.configure(state='normal' if data['enabled'] else 'disabled')
        current = data.get('current')
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
            cycle()
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
    root.protocol('WM_DELETE_WINDOW', close)
    ready = bool(user32.RegisterHotKey(None, 1, 0x4000, 0x81))  # MOD_NOREPEAT, VK_F18
    request('desktop-ready', {'ready': ready, 'error': 'F18 is in use. Close another Dialpad instance or app using F18 and reopen.'}, 'ready')
    webbrowser.open(url)
    tick()
    poll()
    root.mainloop()
