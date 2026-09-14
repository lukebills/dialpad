# AI coding keypad: proposed starting layouts

Reviewed 14 September 2026. These are design recommendations based on current provider documentation, not hardware-tested bindings. Number keys left-to-right across the top row, then the bottom row; confirm the physical device order before programming.

## Recommended Claude Code terminal profile

| Control | Label | macOS | Windows |
| --- | --- | --- | --- |
| Key 1 | Wispr Flow | Ctrl+Command+Option (user-configured; no extra key) | Ctrl+Win+Space; verify Flow's hands-free shortcut |
| Key 2 | Enter | Enter | Enter |
| Key 3 | Escape | Escape | Escape |
| Key 4 | New line | Ctrl+J | Ctrl+J |
| Key 5 | Paste | Cmd+V | Ctrl+Shift+V; match the terminal's actual paste binding |
| Key 6 | Transcript | Ctrl+O | Ctrl+O |
| Dial left | Arrow up | Up arrow | Up arrow |
| Dial right | Arrow down | Down arrow | Down arrow |
| Dial press | Tab | Tab | Tab |

The physical grouping follows the user's workflow: speak, send, interrupt; then compose, paste context, inspect output. Tab on dial press is a proposed convenience for navigating fields and completions. All should remain editable. Wheel direction should be reversible after a short test in the user's terminal.

Claude Code documents Ctrl+J as a newline that works without terminal setup, Ctrl+O for the transcript viewer, and Escape to interrupt an active response. Repeated Escape can open rewind/summarize. Shift+Tab cycles permission modes, so it should be an optional explicitly labelled mapping, rather than a default “Plan” button. Claude also supports native voice input, but the user has selected Wispr Flow. [Claude Code interactive mode](https://code.claude.com/docs/en/interactive-mode)

The paste chords above are suggested host conventions, not Claude commands. Verify them in the actual terminal. In particular Ctrl+V can have a different terminal meaning. Wispr Flow must also be tested in the user's terminal input; successful activation alone does not establish text insertion support.

## Wispr Flow setup — selected by the user

Latest user-confirmed Mac bindings: push-to-talk uses Fn or Control+Option. Hands-free uses **Control+Command+Option**, **Fn+Space**, **middle click**, or **double-tap Fn**. The app now defaults to the modifier-only Control+Command+Option chord. These are this user's settings, not a claim about universal Flow defaults.

Press once to listen, then again to finish and paste. Keep Enter separate so the user can inspect dictated text before sending. The editor can also assign Mouse → middle click; Apple Fn is not available through this encoder. On Windows, verify the proposed Control+Windows+Space chord in Flow settings. [Wispr hands-free behavior](https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free)

Flow accepts customizable shortcuts with up to three keys and at least one modifier. Push-to-talk defaults to Fn on an Apple keyboard, Ctrl+Option on some external-Mac setups, and Ctrl+Win on Windows; defaults can vary. Flow warns when hands-free and push-to-talk shortcuts overlap, so check the installed settings if it reports a conflict and choose another unused three-key chord. [Wispr supported shortcuts](https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts)

Hold-to-talk starts while the shortcut is down and stops when released. A keypad that emits a short macro tap cannot provide a sustained hold, so hands-free is the recommended initial action until keydown/keyup behavior is tested. Wispr confirms the same hands-free shortcut stops and pastes. [Wispr first dictation](https://docs.wisprflow.ai/articles/6409258247-starting-your-first-dictation)

Wispr Flow must already be running and configured; this app sends its shortcut. No Flow installation, login, or settings changes are implied by editing a keypad profile. Test first in TextEdit/Notepad, then in Claude Code and Codex.

## Optional OS dictation alternatives

As an alternative to Wispr Flow, Mac Dictation supports a custom shortcut under System Settings → Keyboard, such as Ctrl+Option+D. This chord is our proposed alternative, not Apple's default. [Apple Dictation settings](https://support.apple.com/en-ie/guide/mac-help/mh40584/mac)

On Windows, Win+H starts voice typing. It needs a microphone, an internet connection, and focus in a supported text field. [Microsoft voice typing](https://support.microsoft.com/en-us/accessibility/windows/use-voice-typing-to-talk-instead-of-type-on-your-pc)

## Separate desktop profiles

For Claude Code Desktop, keep Dictate/Enter/Escape/Paste and offer a Review key: Cmd+Shift+D on Mac, Ctrl+Shift+D on Windows toggles the diff pane. Ctrl+O cycles view modes. Desktop explicitly uses different bindings from the terminal; for example Shift+Tab is not its permission-mode shortcut. Confirm a desktop newline binding in the installed app before labelling one as supported. [Claude Code Desktop](https://code.claude.com/docs/en/desktop)

For the Codex desktop profile, retain Wispr Flow on Key 1 and offer Review Ctrl+Shift+G on both platforms. Native dictation Ctrl+Shift+D is an optional alternative. These Codex shortcuts come from official OpenAI documentation, whose former Codex app commands URL currently redirects to a shared desktop reference. Features and shortcuts depend on the installed app; verify in Settings → Keyboard Shortcuts. Enter approves and Escape declines specifically while an approval request is open. Do not treat either key as a universal approval/rejection command. The desktop mappings must not be reused as claimed Codex CLI bindings. [Official OpenAI desktop commands](https://learn.chatgpt.com/docs/reference/commands)

For a Codex CLI starter, retain Wispr Flow, Enter, Escape, and terminal paste; let users assign the remaining keys after checking the installed CLI's shortcut help. No CLI-specific binding was established from the retrieved [official CLI overview](https://learn.chatgpt.com/docs/codex/cli).

## What comparable tools suggest

Elgato Stream Deck + treats dial clockwise, counterclockwise, and press as independently configurable hotkeys. Adopt that clear three-action editor structure. This source establishes configurable dial actions, not native wheel support on this keypad. [Elgato dial hotkeys](https://help.elgato.com/hc/en-us/articles/10870947641741-Elgato-Stream-Deck-Hotkeys)

Elgato profiles combine hotkeys, text, dial actions, and other actions into reusable configurations. Adopt named, exportable profiles for Claude Terminal, Claude Desktop, and Codex Desktop, with separate OS bindings. The research did not establish a provider-endorsed standard six-key AI layout; the layout above is our synthesis. [Elgato profiles](https://docs.elgato.com/stream-deck/profiles/getting-started/)

## Implementation implications

- Store the label separately from the exact shortcut, so “Escape” stays honest even when context changes its effect.
- Include OS and target surface in profile metadata; profile selection in the editor should not imply automatic foreground-app switching.
- Treat a dictation mapping as a shortcut that starts an existing service. It does not add a speech engine to the keypad app.
- Keep actual wheel events distinct from Up/Down keys: arrows can edit text or navigate history instead of scrolling.
- Show keyboard, mouse-wheel, and mouse-button actions separately; retain a clear unsupported state where the hardware protocol cannot encode an action.
- Test in a scratch text field, then the target coding app, before claiming that a programmed profile works.

## Preloaded everyday layouts

The Mac app now preloads these four editable layouts into saved setups. They are appended on upgrade without replacing existing profiles; preload history preserves later edits/removals. New profiles use the existing first profile's hardware layer (or layer 1 on a fresh install). Windows includes Media, Web browsing and Word; Apple Mail is explicitly Mac-only.

| Layout | Keys 1–6 | Dial rotation | Standalone dial press |
| --- | --- | --- | --- |
| Media | Play/pause, Previous track, Next track, Mute, Volume down, Volume up | Volume down/up | Mute |
| Web browsing | Address bar, New tab, Back, Forward, Reload, Find on page | Scroll up/down | Tab |
| Word desktop | Wispr Flow, New paragraph, Bold, Undo, Paste, Save | Scroll up/down | Tab |
| Apple Mail | Wispr Flow, New message, Reply, Forward, Paste, Get new mail | Scroll up/down | Tab |

Enabling the cycle replaces each standalone dial press with F18 → Next setup. It does not open or focus the target application. Media uses standard consumer HID actions; the OS/player determines support.

Browser shortcuts are Cmd+L/T, Cmd+[/], Cmd+R/F on Mac, and Ctrl+L/T, Alt+Left/Right, Ctrl+R/F on Windows. Source: [Google Chrome shortcuts](https://support.google.com/chrome/answer/157179?hl=en). Other browsers require a physical compatibility check.

Word uses Return, Cmd/Ctrl+B, Z, V, S and the user's Flow chord. Source: [Microsoft Word shortcuts](https://support.microsoft.com/en-au/accessibility/word/keyboard-shortcuts-in-word). The preset targets the desktop application.

Apple Mail uses Cmd+N for a new message, Cmd+R to reply, Cmd+Shift+F to forward, Cmd+V to paste and Cmd+Shift+N to get new mail. Source: [Apple Mail keyboard shortcuts](https://support.apple.com/en-gb/guide/mail/mlhlb94f262b/mac). Flow retains the user's exact modifier-only Control+Command+Option hands-free shortcut.

The user requested Up/Down arrow keys for dial rotation in all Claude and Codex starter layouts. Counterclockwise sends Up; clockwise sends Down. Media, Web browsing, Word and Apple Mail retain their existing dial actions.
