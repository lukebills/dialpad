# Dialpad local agent guide (API version 1)

Dialpad configures compatible six-key + clickable-dial CH57x-2 keypads. Use this
local API from Claude Code, Codex, or another agent with terminal access on the
same computer. No MCP server, browser automation, repository, or account is
required. Launch Dialpad first and leave its desktop companion running.

## Connect without exposing credentials

Read the current session file privately:
- macOS: ~/Library/Application Support/Dialpad/session.json
- Windows: %APPDATA%/Dialpad/session.json

It contains `base` (http://127.0.0.1:<port>/) and `token`. Send requests to
`base + "api/<endpoint>"` with `Authorization: Bearer <token>` and, for POST,
`Content-Type: application/json`. Use UTF-8 JSON. Never print, paste into chat,
commit, or transmit the token. Do not hard-code a port. Do not expose the local
server to a network. If the session is stale, reopen Dialpad and reread it.
Only accept a base URL whose scheme is http and hostname is exactly 127.0.0.1;
disable proxies and redirects for requests carrying the token.

Python standard-library connection example (Python belongs to the agent's
working environment; the packaged app itself does not require Python):

```python
import json, os, sys, urllib.request, urllib.parse
from pathlib import Path
folder = (Path(os.environ['APPDATA']) if sys.platform == 'win32'
          else Path.home() / 'Library/Application Support') / 'Dialpad'
session = json.loads((folder / 'session.json').read_text(encoding='utf-8'))
base = session['base']
url = urllib.parse.urlsplit(base)
assert url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
assert not url.username and not url.password and url.path == '/'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
def api(endpoint, body=None):
    req = urllib.request.Request(base + 'api/' + endpoint,
        data=None if body is None else json.dumps(body).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + session['token'],
                 'Content-Type': 'application/json'})
    with opener.open(req, timeout=30) as response:
        return json.load(response)
state = api('setups')
capabilities = api('agent')
```

On Windows, an agent can use PowerShell's ConvertFrom-Json, ConvertTo-Json
-Depth 30 and Invoke-RestMethod with the same headers, URLs and JSON bodies.
Do not include the token in command-line arguments or debug output.

## Read, edit, save, then apply

1. GET `agent`: this guide, platform, supported keys/modifiers/media/mouse,
   multi-tap keys and maximum number of setups. GET `setups`: saved `profiles`,
   selected cycle `order`, `ready`, `enabled`, `current`, `cycle_names`,
   `active` (zero-based), `generation`, and `error`.
2. Copy the entire saved profile before editing it. Preserve unrelated keys,
   labels, hardware layer and profiles. For a new setup, clone an appropriate
   existing profile or GET `/starters.json` (outside /api/) for bundled Mac
   and Windows examples. Use a unique name. Maximum eight saved setups.
3. POST `validate` with `{"profile": profile}`. This never writes to USB.
4. POST `setups/upsert` with `{"profile": edited, "previous_name": original_name,
   "expected_profile": original}`. For a new profile use `previous_name: null`
   and omit expected_profile. This saves to the app, not the keypad.
   On a stale-edit error reread and reconcile; never blindly overwrite.
5. To include the setup in the dial cycle, POST `setups/order` with
   `{"names": ["Setup A", "Setup B"]}`. Preserve the user's existing order unless
   asked to change it. This replaces only the selected order, not the library.
6. If the user asked to set/apply/activate it, GET `devices` and choose the
   intended device's `id`. If multiple devices are present, clarify which.
   POST `setups/preview` with `{"device_id": id, "names": ordered_names}`.
   Every included profile must share a layer and the desktop must be `ready`.
   To activate a particular setup immediately, put it first in ordered_names
   (rotate the existing order to preserve relative cycling order). Save that
   same order using step 5. Preview returns the exact normalized `profiles`,
   controls, layer, packet count, SHA-256 and a one-use `nonce` valid 120 seconds.
   Dial press is automatically assigned F18 / Next setup for every profile.
7. Inspect the preview and summarize the changes. When applying is within the
   user's request, POST `apply` with `{"nonce": preview_nonce}`; no extra
   approval is needed solely because an agent is doing it. If asked only to
   create/edit a saved setup, stop after saving. Never fabricate a nonce.
8. GET `setups` to confirm `enabled` and `current`. Report what was saved versus
   what was sent. Successful USB transfer is not hardware read-back: ask the
   user to test the physical controls. Do not simulate input into their apps.

Saving changes does not update an already-running cycle: it retains its last
applied snapshot until step 7. Never edit settings JSON files directly while
Dialpad is running. Never call desktop-ready yourself; only the real companion
registers global shortcuts. Avoid bulk setups/save; upsert protects unrelated
profiles. On transfer failure cycling stops because hardware state is unknown;
report the failure instead of retrying writes automatically.

Other operations: POST `setups/cycle` with `{}` advances one setup; serialize
requests and wait for each response. POST `setups/disable` with `{}` stops
cycling without changing the keypad's last bindings. POST `show` with `{}`
opens the editor. GET `devices` is read-only. All /api endpoints require auth.
HTTP 400 is invalid/conflicting input, 401 stale credentials, 503 runtime/USB
failure; inspect the JSON `error`. Never repeatedly retry an apply request.

## Profile and action format

```json
{
  "version": 1, "name": "My coding setup", "layer": 1,
  "labels": {"key1":"Wispr Flow", "key5":"Copy / Paste / Cut"},
  "bindings": {
    "key1":{"type":"shortcut","key":"NONE","modifiers":["ctrl","cmd","alt"]},
    "key2":{"type":"shortcut","key":"ENTER","modifiers":[]},
    "key3":{"type":"shortcut","key":"ESCAPE","modifiers":[]},
    "key4":{"type":"shortcut","key":"ENTER","modifiers":["shift"]},
    "key5":{"type":"multi_tap","window_ms":350,
      "single":{"type":"clipboard","action":"copy","formatting":"plain","modifiers":["cmd"]},
      "double":{"type":"clipboard","action":"paste","formatting":"plain","modifiers":["cmd"]},
      "triple":{"type":"clipboard","action":"cut","formatting":"plain","modifiers":["cmd"]}},
    "key6":{"type":"shortcut","key":"TAB","modifiers":[]},
    "dial_ccw":{"type":"shortcut","key":"UP","modifiers":[]},
    "dial_press":{"type":"shortcut","key":"F18","modifiers":[]},
    "dial_cw":{"type":"shortcut","key":"DOWN","modifiers":[]}
  }
}
```

Name: 1–80 characters. Labels: at most 32 characters. Layer: integer 1–3.
Exactly six keys and three dial controls are required. Physical key positions
can vary by device: retain the user's existing assignments.

- shortcut: `{"type":"shortcut","key":"C","modifiers":["cmd"]}`.
  `cmd` means Command on Mac, Windows key on Windows. Use ctrl for conventional
  Windows copy/paste, or ctrl+shift for terminals configured that way.
  `NONE` supports a modifier-only chord; Fn cannot be encoded. The example's
  Wispr Flow chord is the user's Mac configuration; match their Flow settings.
- mouse: `{"type":"mouse","action":"wheel_up","modifiers":[]}`.
  Mouse permits no modifier or one of ctrl, shift, alt.
- media: `{"type":"media","action":"play_pause"}`.
- multi_tap: six keys only, integer window_ms 100–1000 (default 350), required
  single/double/triple actions. The timing window restarts after each tap.
  Single/double wait for the gap; triple executes immediately. Leaf types:
  shortcut, mouse, media, clipboard. No nested multi-tap or sequences.
  Shortcut keys must be in multi_tap_keys, modifiers ctrl/alt/shift/cmd.
  Multi-tap media: volume_up, volume_down, mute, play_pause, next, previous.
- clipboard: only inside multi_tap; action copy/paste/cut, formatting plain or
  formatted, modifiers [cmd], [ctrl], or [ctrl,shift]. Plain removes text
  formatting while preserving non-text clipboard items.
- sequence: `{"type":"sequence","steps":[{"key":"A","modifiers":["cmd"]},
  {"key":"C","modifiers":["cmd"]}]}`. 1–5 shortcut steps, no delays.
  This is API-supported but the graphical editor does not offer sequence editing.
- legacy copy_paste is retained for existing profiles; prefer multi_tap for new
  clipboard configurations. Preserve legacy actions unless asked to convert.

Reserve F13–F20 for Dialpad's companion; do not assign them to normal shortcuts
apart from dial_press F18 for cycling. Managed multi-tap/clipboard actions need
an applied cycle and the background app. On Mac they need Accessibility/device
control access; an agent must not attempt to grant or bypass OS permission.

## User-facing navigation

The Live setup dropdown selects an editable saved setup. Add new creates one.
Click a key or dial to edit its action; edits autosave. Setup settings contains
name, starting layout, platform, import/export and hardware layer. Dial cycling
checkboxes select included setups, with arrows for ordering. Apply to keypad
opens the preview, then Apply sends it. Closing the editor leaves the app
running. Selecting a saved setup alone does not change the physical keypad.
