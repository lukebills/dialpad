import Cocoa
import WebKit
import Carbon
import ApplicationServices

let tapKeyCodes: [String: CGKeyCode] = ["A": 0, "S": 1, "D": 2, "F": 3, "H": 4, "G": 5, "Z": 6, "X": 7, "C": 8, "V": 9, "B": 11, "Q": 12, "W": 13, "E": 14, "R": 15, "Y": 16, "T": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "EQUAL": 24, "9": 25, "7": 26, "MINUS": 27, "8": 28, "0": 29, "RIGHTBRACKET": 30, "O": 31, "U": 32, "LEFTBRACKET": 33, "I": 34, "P": 35, "ENTER": 36, "L": 37, "J": 38, "QUOTE": 39, "K": 40, "SEMICOLON": 41, "BACKSLASH": 42, "COMMA": 43, "SLASH": 44, "N": 45, "M": 46, "DOT": 47, "TAB": 48, "SPACE": 49, "GRAVE": 50, "BACKSPACE": 51, "ESCAPE": 53, "CAPSLOCK": 57, "F1": 122, "F2": 120, "F3": 99, "F4": 118, "F5": 96, "F6": 97, "F7": 98, "F8": 100, "F9": 101, "F10": 109, "F11": 103, "F12": 111, "HOME": 115, "PAGEUP": 116, "DELETE": 117, "END": 119, "PAGEDOWN": 121, "LEFT": 123, "RIGHT": 124, "DOWN": 125, "UP": 126]

// Pure gesture state, exercised by --clipboard-state-test without OS input.
struct ClipboardGesture {
    var copyNext = true
    var lastAction: TimeInterval?
    var pending: TimeInterval?
    mutating func tap(now: TimeInterval, reset: Int, doubleTap: Bool) -> String? {
        if let pending = pending, now - pending <= 0.320 { self.pending = nil; return "cut" }
        if let last = lastAction, reset > 0 && now - last >= Double(reset) { copyNext = true }
        if doubleTap { pending = now; return nil }
        return copyNext ? "copy" : "paste"
    }
    mutating func flush() -> String { pending = nil; return copyNext ? "copy" : "paste" }
    mutating func complete(_ operation: String, now: TimeInterval) { copyNext = operation == "paste"; lastAction = now }
}

// Only called after an explicit Copy/Cut has changed the clipboard.
@discardableResult func stripTextFormatting(_ board: NSPasteboard) -> Bool {
    let count = board.changeCount
    guard let items = board.pasteboardItems, items.count == 1,
          !items[0].types.contains(.fileURL), !items[0].types.contains(.png), !items[0].types.contains(.tiff),
          let text = board.string(forType: .string), count == board.changeCount else { return false }
    board.clearContents()
    return board.setString(text, forType: .string)
}

// Visual layout in the menu bar.
final class KeypadPreview: NSView {
    var profile: [String: Any]?
    var title = "Cycling off"
    var detail = "Enable a saved setup in the editor."
    override var isFlipped: Bool { true }

    override init(frame: NSRect) {
        super.init(frame: frame)
        setAccessibilityElement(true)
        setAccessibilityRole(.image)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func configure(profile: [String: Any]?, title: String, detail: String) {
        self.profile = profile; self.title = title; self.detail = detail
        setAccessibilityLabel(title + ". " + detail)
        toolTip = detail
        needsDisplay = true
    }

    func color(_ red: CGFloat, _ green: CGFloat, _ blue: CGFloat) -> NSColor {
        NSColor(calibratedRed: red, green: green, blue: blue, alpha: 1)
    }
    func box(_ rect: NSRect, radius: CGFloat, fill: NSColor) {
        fill.setFill(); NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius).fill()
    }
    func text(_ value: String, _ rect: NSRect, size: CGFloat, bold: Bool = false, centered: Bool = false, ink: NSColor? = nil, wrap: Bool = false) {
        let style = NSMutableParagraphStyle()
        style.alignment = centered ? .center : .left
        style.lineBreakMode = wrap ? .byWordWrapping : .byTruncatingTail
        (value as NSString).draw(in: rect, withAttributes: [.font: NSFont.systemFont(ofSize: size, weight: bold ? .semibold : .regular), .foregroundColor: ink ?? color(0.16, 0.24, 0.18), .paragraphStyle: style])
    }
    func action(_ control: String) -> String {
        let bindings = profile?["bindings"] as? [String: [String: Any]] ?? [:]
        let binding = bindings[control] ?? [:]
        if binding["type"] as? String == "multi_tap" {
            return ["single", "double", "triple"].enumerated().map { index, name in
                let leaf = binding[name] as? [String: Any] ?? [:]
                return "\(index + 1)× " + (leaf["action"] as? String ?? leaf["key"] as? String ?? "")
            }.joined(separator: " · ")
        }
        if binding["type"] as? String == "copy_paste" { return "Copy ⇄ Paste" }
        if binding["type"] as? String == "shortcut" {
            let symbols = ["ctrl":"⌃", "alt":"⌥", "cmd":"⌘", "shift":"⇧"]
            let modifiers = (binding["modifiers"] as? [String] ?? []).map { symbols[$0] ?? $0 }.joined()
            let key = binding["key"] as? String ?? ""
            return modifiers + (key == "NONE" ? "" : key)
        }
        return (binding["action"] as? String ?? "").replacingOccurrences(of: "_", with: " ")
    }
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.saveGState()
        context.scaleBy(x: bounds.width / 440, y: bounds.height / 280)
        box(NSRect(x: 0, y: 0, width: 440, height: 280), radius: 14, fill: color(0.97, 0.97, 0.94))
        text(title, NSRect(x: 20, y: 15, width: 400, height: 25), size: 16, bold: true)
        box(NSRect(x: 12, y: 56, width: 416, height: 181), radius: 21, fill: color(0.77, 0.81, 0.72))
        box(NSRect(x: 12, y: 50, width: 416, height: 181), radius: 21, fill: color(0.87, 0.9, 0.83))
        let labels = profile?["labels"] as? [String: String] ?? [:]
        for index in 0..<6 {
            let control = "key\(index + 1)"
            let x = CGFloat(26 + (index % 3) * 94), y = CGFloat(66 + (index / 3) * 79)
            box(NSRect(x: x, y: y + 4, width: 84, height: 68), radius: 9, fill: color(0.72, 0.77, 0.66))
            box(NSRect(x: x, y: y, width: 84, height: 68), radius: 9, fill: index == 0 && profile != nil ? color(0.84, 0.93, 0.7) : color(0.98, 0.99, 0.95))
            text("0\(index + 1)", NSRect(x: x + 7, y: y + 5, width: 65, height: 12), size: 8, ink: color(0.48, 0.55, 0.43))
            text(labels[control] ?? "Key \(index + 1)", NSRect(x: x + 5, y: y + 22, width: 74, height: 25), size: 10, bold: true, centered: true, wrap: true)
            text(action(control), NSRect(x: x + 4, y: y + 49, width: 76, height: 14), size: 8, centered: true)
        }
        color(0.61, 0.67, 0.55).setFill(); NSBezierPath(ovalIn: NSRect(x: 321, y: 85, width: 91, height: 91)).fill()
        color(0.24, 0.32, 0.26).setFill(); NSBezierPath(ovalIn: NSRect(x: 321, y: 80, width: 91, height: 91)).fill()
        color(0.76, 0.87, 0.65).setStroke()
        let tick = NSBezierPath(); tick.move(to: NSPoint(x: 366.5, y: 89)); tick.line(to: NSPoint(x: 366.5, y: 103)); tick.lineWidth = 3; tick.stroke()
        text("PRESS", NSRect(x: 328, y: 112, width: 78, height: 14), size: 8, centered: true, ink: .white)
        text(labels["dial_press"] ?? "—", NSRect(x: 325, y: 130, width: 83, height: 30), size: 10, bold: true, centered: true, ink: .white)
        text("↶ " + (labels["dial_ccw"] ?? "Turn left"), NSRect(x: 313, y: 184, width: 106, height: 15), size: 9, centered: true)
        text("↷ " + (labels["dial_cw"] ?? "Turn right"), NSRect(x: 313, y: 204, width: 106, height: 15), size: 9, centered: true)
        text(profile == nil ? detail : "LIVE LAYOUT  ·  Press the dial to switch setups", NSRect(x: 20, y: 248, width: 400, height: 25), size: 10)
        context.restoreGState()
    }
}

// The host receives the session URL on stdin, never through the process arguments.
final class Desktop: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, WKScriptMessageHandler {
    let url: URL
    let token: String
    var window: NSWindow!
    var web: WKWebView!
    var status: NSStatusItem!
    var menuPreview: KeypadPreview!
    var currentProfile: [String: Any]?
    var menuFingerprint = ""
    var testTapActions: [[String: Any]]?
    var tapHotKeys: [EventHotKeyRef] = []
    var tapCounts: [Int: Int] = [:]
    var tapTimes: [Int: TimeInterval] = [:]
    var tapTasks: [Int: DispatchWorkItem] = [:]
    var tapFocus: [Int: pid_t] = [:]
    var copyHotKey: EventHotKeyRef?
    var clipboardGesture = ClipboardGesture()
    var clipboardTimer: DispatchWorkItem?
    var clipboardFocus: pid_t?
    var clipboardBusy = false
    var clipboardContext = ""
    var heldHotKeys = Set<UInt32>()
    var lastProfileName = ""
    var hotKeyReady = false
    var showRequest = 0
    var hotKey: EventHotKeyRef?
    var handler: EventHandlerRef?
    var timer: Timer?
    var enabled = false
    var cycling = false
    var polling = false
    var summary = "Setup cycling is off.\nSave two setups in the editor to get started."
    var currentName = "Cycling off"

    init(url: URL) {
        self.url = url
        self.token = url.fragment ?? ""
    }

    func request(_ path: String, body: [String: Any]? = nil, completion: @escaping ([String: Any]?, String?) -> Void) {
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        components.path = "/api/" + path
        components.fragment = nil
        var request = URLRequest(url: components.url!)
        request.timeoutInterval = 15
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        if let body = body {
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }
        URLSession.shared.dataTask(with: request) { data, response, error in
            let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let failed = (response as? HTTPURLResponse).map { !(200...299).contains($0.statusCode) } ?? true
            let failure = error?.localizedDescription ?? (failed ? (json?["error"] as? String ?? "Request failed") : nil)
            DispatchQueue.main.async { completion(json, failure) }
        }.resume()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let icon = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent().appendingPathComponent("assets/app-icon.png")
        if let image = NSImage(contentsOf: icon) { NSApp.applicationIconImage = image }
        let menu = NSMenu()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit Dialpad", action: #selector(quit), keyEquivalent: "q").target = self
        let item = NSMenuItem(); item.submenu = appMenu; menu.addItem(item)
        let editMenu = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        let edit = NSMenuItem(); edit.submenu = editMenu; menu.addItem(edit)
        NSApp.mainMenu = menu
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "desktop")
        web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = self
        web.uiDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1160, height: 830), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Dialpad"
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(calibratedRed: 245/255, green: 244/255, blue: 239/255, alpha: 1)
        window.appearance = NSAppearance(named: .aqua)
        web.underPageBackgroundColor = window.backgroundColor
        window.minSize = NSSize(width: 440, height: 560)
        window.isReleasedWhenClosed = false
        window.contentView = web
        window.center()
        web.load(URLRequest(url: url))
        showEditor()
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        let menuIcon = NSImage(size: NSSize(width: 24, height: 18), flipped: false) { _ in
            NSColor.black.setFill()
            for x in [1, 6, 11] {
                for y in [4, 10] { NSBezierPath(roundedRect: NSRect(x: x, y: y, width: 4, height: 4), xRadius: 1, yRadius: 1).fill() }
            }
            NSBezierPath(ovalIn: NSRect(x: 17, y: 6, width: 6, height: 6)).fill()
            return true
        }
        menuIcon.isTemplate = true
        status.button?.image = menuIcon
        status.button?.imagePosition = .imageLeading
        refreshMenu()

        var events = [EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed)), EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyReleased))]
        let pointer = Unmanaged.passUnretained(self).toOpaque()
        let installed = InstallEventHandler(GetApplicationEventTarget(), { _, event, context in
            guard let context = context else { return OSStatus(eventNotHandledErr) }
            let host = Unmanaged<Desktop>.fromOpaque(context).takeUnretainedValue()
            guard let event = event else { return OSStatus(eventNotHandledErr) }
            var identity = EventHotKeyID()
            guard GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size, nil, &identity) == noErr else { return OSStatus(eventNotHandledErr) }
            let released = GetEventKind(event) == UInt32(kEventHotKeyReleased)
            let id = identity.id
            DispatchQueue.main.async {
                if released { host.heldHotKeys.remove(id); return }
                guard host.heldHotKeys.insert(id).inserted else { return }
                if id == 1 && host.enabled { host.nextSetup() }
                if id == 2 && host.enabled { host.alternateClipboard() }
                if (3...8).contains(id) && host.enabled { host.multiTap(Int(id) - 2) }
            }
            return noErr
        }, 2, &events, pointer, &handler)
        let registered = installed == noErr ? RegisterEventHotKey(UInt32(kVK_F18), 0, EventHotKeyID(signature: 0x4449414C, id: 1), GetApplicationEventTarget(), 0, &hotKey) : installed
        let copyRegistered = installed == noErr ? RegisterEventHotKey(UInt32(kVK_F19), 0, EventHotKeyID(signature: 0x4449414C, id: 2), GetApplicationEventTarget(), 0, &copyHotKey) : installed
        var tapsReady = true
        for (index, code) in [kVK_F13, kVK_F14, kVK_F15, kVK_F16, kVK_F17, kVK_F20].enumerated() {
            var ref: EventHotKeyRef?
            let result = installed == noErr ? RegisterEventHotKey(UInt32(code), 0, EventHotKeyID(signature: 0x4449414C, id: UInt32(index + 3)), GetApplicationEventTarget(), 0, &ref) : installed
            if result != noErr { tapsReady = false }
            if let ref = ref { tapHotKeys.append(ref) }
        }
        hotKeyReady = registered == noErr && copyRegistered == noErr && tapsReady
        request("desktop-ready", body: ["ready": hotKeyReady, "error": "A Dialpad trigger (F13–F20) is unavailable. Close another app using these keys, then reopen."]) { state, error in
            if let state = state { self.update(state) }
        }
        timer = Timer.scheduledTimer(withTimeInterval: 0.6, repeats: true) { _ in self.poll() }
    }

    func poll() {
        guard !polling else { return }
        polling = true
        request("setups") { state, error in
            self.polling = false
            if let state = state { self.update(state) }
            else {
                self.enabled = false
                self.resetClipboard(); self.clipboardContext = ""
                self.currentName = "Disconnected"
                self.summary = "Dialpad is disconnected. Reopen the app to reconnect."
                self.currentProfile = nil
                self.refreshMenu()
            }
        }
    }

    func describe(_ action: [String: Any]) -> String {
        if action["type"] as? String == "multi_tap" {
            return ["single", "double", "triple"].enumerated().map { "\($0.offset + 1)× " + describe(action[$0.element] as? [String: Any] ?? [:]) }.joined(separator: " · ")
        }
        if action["type"] as? String == "copy_paste" { return "Copy ⇄ Paste" }
        if action["type"] as? String == "shortcut" {
            let symbols = ["ctrl": "⌃", "alt": "⌥", "cmd": "⌘", "shift": "⇧"]
            let modifiers = (action["modifiers"] as? [String] ?? []).map { symbols[$0] ?? $0 }.joined()
            let key = action["key"] as? String ?? ""
            return modifiers + (key == "NONE" ? "" : key)
        }
        return (action["action"] as? String ?? "").replacingOccurrences(of: "_", with: " ")
    }

    func update(_ state: [String: Any]) {
        if let request = state["show_request"] as? Int, request != showRequest {
            showRequest = request
            showEditor()
        }
        enabled = state["enabled"] as? Bool ?? false
        if let profile = state["current"] as? [String: Any], enabled {
            currentProfile = profile
            currentName = profile["name"] as? String ?? "Setup"
            let context = currentName + String(state["generation"] as? Int ?? 0)
            if context != clipboardContext { resetClipboard(); clipboardContext = context }
            let labels = profile["labels"] as? [String: String] ?? [:]
            let bindings = profile["bindings"] as? [String: [String: Any]] ?? [:]
            let rows = (1...6).map { i -> String in
                let key = "key\(i)"
                return "\(i)   \(labels[key] ?? key)   ·   \(describe(bindings[key] ?? [:]))"
            }
            summary = currentName + "\n\n" + rows.joined(separator: "\n\n") + "\n\n↶ \(describe(bindings["dial_ccw"] ?? [:]))   ↷ \(describe(bindings["dial_cw"] ?? [:]))\nPress dial → Next setup"
        } else {
            resetClipboard(); clipboardContext = ""
            currentProfile = nil
            currentName = "Cycling off"
            let error = state["error"] as? String ?? ""
            if !error.isEmpty { currentName = "Needs attention" }
            summary = error.isEmpty ? "Setup cycling is off.\n\nOpen the editor to save and enable setups.\n\nThe keypad keeps its last written bindings. Reapply a normal layout to restore the dial press." : error
        }
        refreshMenu()
    }

    func refreshMenu() {
        status.button?.title = " " + String(currentName.prefix(24))
        status.button?.toolTip = currentName + " · Click to view the keypad"
        menuPreview?.configure(profile: currentProfile, title: currentName, detail: summary)
        let fingerprint = currentName + summary + String(enabled)
        if fingerprint == menuFingerprint { return }
        menuFingerprint = fingerprint
        let menu = NSMenu()
        let diagram = NSMenuItem()
        menuPreview = KeypadPreview(frame: NSRect(x: 0, y: 0, width: 440, height: 280))
        menuPreview.configure(profile: currentProfile, title: currentName, detail: summary)
        diagram.view = menuPreview
        menu.addItem(diagram)
        menu.addItem(.separator())
        let next = menu.addItem(withTitle: "Next setup", action: #selector(nextSetup), keyEquivalent: "")
        next.target = self; next.isEnabled = enabled
        menu.addItem(withTitle: "Open editor", action: #selector(showEditor), keyEquivalent: "").target = self
        menu.addItem(withTitle: "Quit Dialpad", action: #selector(quit), keyEquivalent: "").target = self
        menu.autoenablesItems = false
        status.menu = menu
    }

    @objc func nextSetup() {
        guard enabled && !cycling else { return }
        resetClipboard()
        cycling = true
        request("setups/cycle", body: [:]) { state, error in
            self.cycling = false
            if let state = state, state["generation"] != nil { self.update(state) }
            if let error = error {
                self.currentName = "Switch failed"
                self.summary = error
                self.currentProfile = nil
                self.refreshMenu()
                self.poll()
            }
        }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.host == "127.0.0.1", message.body as? String == "hide" else { return }
        window.orderOut(nil)
    }
    func resetClipboard() {
        for task in tapTasks.values { task.cancel() }
        tapTasks.removeAll(); tapCounts.removeAll(); tapTimes.removeAll(); tapFocus.removeAll()
        clipboardTimer?.cancel(); clipboardTimer = nil
        clipboardGesture = ClipboardGesture(); clipboardFocus = nil; clipboardBusy = false
    }
    func multiTap(_ key: Int) {
        guard enabled, !cycling, !clipboardBusy,
              let bindings = currentProfile?["bindings"] as? [String: [String: Any]],
              let action = bindings["key\(key)"], action["type"] as? String == "multi_tap",
              let focus = NSWorkspace.shared.frontmostApplication?.processIdentifier else { return }
        let prompt = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        guard testTapActions != nil || AXIsProcessTrustedWithOptions(prompt) else {
            currentName = "Allow Accessibility"
            summary = "Allow Dialpad in System Settings → Privacy & Security → Accessibility, then try the key again."
            refreshMenu(); return
        }
        let now = ProcessInfo.processInfo.systemUptime
        let delay = Double(action["window_ms"] as? Int ?? 350) / 1000
        if tapFocus[key] != focus { cancelTap(key) }
        if let last = tapTimes[key], now - last > delay { finishTap(key, action: action) }
        tapTasks[key]?.cancel()
        tapFocus[key] = focus
        tapCounts[key] = (tapCounts[key] ?? 0) + 1
        tapTimes[key] = now
        if tapCounts[key] == 3 { finishTap(key, action: action); return }
        let context = clipboardContext
        let task = DispatchWorkItem { [weak self] in
            guard let self = self, self.clipboardContext == context else { return }
            self.finishTap(key, action: action)
        }
        tapTasks[key] = task
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: task)
    }
    func cancelTap(_ key: Int) {
        tapTasks.removeValue(forKey: key)?.cancel()
        tapCounts.removeValue(forKey: key); tapTimes.removeValue(forKey: key); tapFocus.removeValue(forKey: key)
    }
    func finishTap(_ key: Int, action: [String: Any]) {
        let count = tapCounts[key] ?? 0, focus = tapFocus[key]
        cancelTap(key)
        guard enabled, !cycling, (1...3).contains(count), focus != nil,
              NSWorkspace.shared.frontmostApplication?.processIdentifier == focus,
              let leaf = action[["single", "double", "triple"][count - 1]] as? [String: Any] else { return }
        if testTapActions != nil { testTapActions?.append(leaf); return }
        if leaf["type"] as? String == "clipboard" {
            performClipboard(leaf["action"] as? String ?? "copy", action: leaf, focus: focus)
        } else { emitAction(leaf) }
    }
    func emitAction(_ action: [String: Any]) {
        var flags = CGEventFlags()
        for modifier in action["modifiers"] as? [String] ?? [] {
            switch modifier {
            case "cmd": flags.insert(.maskCommand)
            case "ctrl": flags.insert(.maskControl)
            case "alt": flags.insert(.maskAlternate)
            case "shift": flags.insert(.maskShift)
            default: break
            }
        }
        if action["type"] as? String == "shortcut" {
            let key = (action["key"] as? String ?? "").uppercased()
            if key == "NONE" {
                let modifiers: [(CGEventFlags, Int)] = [(.maskControl,kVK_Control),(.maskShift,kVK_Shift),(.maskAlternate,kVK_Option),(.maskCommand,kVK_Command)]
                var active = CGEventFlags()
                for (flag, code) in modifiers where flags.contains(flag) {
                    active.insert(flag)
                    let event = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: true)
                    event?.type = .flagsChanged; event?.flags = active; event?.post(tap: .cghidEventTap)
                }
                for (flag, code) in modifiers.reversed() where flags.contains(flag) {
                    active.remove(flag)
                    let event = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: false)
                    event?.type = .flagsChanged; event?.flags = active; event?.post(tap: .cghidEventTap)
                }
                return
            }
            guard let code = tapKeyCodes[key] else { return }
            for down in [true, false] {
                let event = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: down)
                event?.flags = flags; event?.post(tap: .cghidEventTap)
            }
        } else if action["type"] as? String == "mouse" {
            let name = (action["action"] as? String ?? "").lowercased()
            if name.hasPrefix("wheel_") {
                let event = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: name == "wheel_up" ? 1 : -1, wheel2: 0, wheel3: 0)
                event?.flags = flags; event?.post(tap: .cghidEventTap)
            } else {
                let button: CGMouseButton = name == "right_click" ? .right : name == "middle_click" ? .center : .left
                let types: [CGEventType] = button == .right ? [.rightMouseDown,.rightMouseUp] : button == .center ? [.otherMouseDown,.otherMouseUp] : [.leftMouseDown,.leftMouseUp]
                let location = CGEvent(source: nil)?.location ?? .zero
                for type in types {
                    let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: location, mouseButton: button)
                    event?.flags = flags; event?.post(tap: .cghidEventTap)
                }
            }
        } else if action["type"] as? String == "media" {
            let codes = ["volume_up":0,"volume_down":1,"mute":7,"play_pause":16,"next":17,"previous":18]
            guard let code = codes[(action["action"] as? String ?? "").lowercased()] else { return }
            for state in [0xa, 0xb] {
                NSEvent.otherEvent(with: .systemDefined, location: .zero, modifierFlags: [], timestamp: 0, windowNumber: 0, context: nil, subtype: 8, data1: (code << 16) | (state << 8), data2: -1)?.cgEvent?.post(tap: .cghidEventTap)
            }
        }
    }
    func alternateClipboard() {
        guard !clipboardBusy, !cycling,
              let bindings = currentProfile?["bindings"] as? [String: [String: Any]],
              let action = bindings.values.first(where: { $0["type"] as? String == "copy_paste" }) else { return }
        let prompt = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        guard AXIsProcessTrustedWithOptions(prompt) else {
            currentName = "Allow Accessibility"
            summary = "Allow Dialpad in System Settings → Privacy & Security → Accessibility, then press Copy / Paste again."
            refreshMenu(); return
        }
        let focus = NSWorkspace.shared.frontmostApplication?.processIdentifier
        if clipboardGesture.pending != nil && focus != clipboardFocus { resetClipboard() }
        let now = ProcessInfo.processInfo.systemUptime
        if let pending = clipboardGesture.pending, now - pending > 0.320 {
            clipboardTimer?.cancel()
            performClipboard(clipboardGesture.flush(), action: action, focus: clipboardFocus)
            return
        }
        clipboardFocus = focus
        clipboardTimer?.cancel()
        if let operation = clipboardGesture.tap(now: now, reset: action["reset_seconds"] as? Int ?? 10, doubleTap: action["double_tap_cut"] as? Bool ?? true) {
            performClipboard(operation, action: action, focus: focus)
        } else {
            let context = clipboardContext
            let task = DispatchWorkItem { [weak self] in
                guard let self = self, self.enabled, context == self.clipboardContext else { return }
                self.performClipboard(self.clipboardGesture.flush(), action: action, focus: focus)
            }
            clipboardTimer = task
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.320, execute: task)
        }
    }
    func performClipboard(_ operation: String, action: [String: Any], focus: pid_t?) {
        guard enabled, !cycling, focus != nil, NSWorkspace.shared.frontmostApplication?.processIdentifier == focus else { resetClipboard(); return }
        var flags = CGEventFlags()
        for modifier in action["modifiers"] as? [String] ?? ["cmd"] {
            switch modifier.lowercased() {
            case "cmd": flags.insert(.maskCommand)
            case "ctrl": flags.insert(.maskControl)
            case "shift": flags.insert(.maskShift)
            default: break
            }
        }
        let code = CGKeyCode(operation == "cut" ? kVK_ANSI_X : operation == "copy" ? kVK_ANSI_C : kVK_ANSI_V)
        guard let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true),
              let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false) else { return }
        let before = NSPasteboard.general.changeCount
        down.flags = flags; up.flags = flags
        down.post(tap: .cghidEventTap); up.post(tap: .cghidEventTap)
        if operation == "paste" {
            clipboardGesture.complete(operation, now: ProcessInfo.processInfo.systemUptime)
            return
        }
        clipboardBusy = true
        finishCopy(operation, action: action, before: before, context: clipboardContext, focus: focus, attempts: 25)
    }
    func finishCopy(_ operation: String, action: [String: Any], before: Int, context: String, focus: pid_t?, attempts: Int) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.04) { [weak self] in
            guard let self = self, self.enabled, context == self.clipboardContext else { return }
            guard NSWorkspace.shared.frontmostApplication?.processIdentifier == focus else { self.resetClipboard(); return }
            let board = NSPasteboard.general
            if board.changeCount != before {
                if (action["formatting"] as? String ?? "plain") == "plain" { stripTextFormatting(board) }
                self.clipboardBusy = false
                self.clipboardGesture.complete(operation, now: ProcessInfo.processInfo.systemUptime)
            } else if attempts > 1 {
                self.finishCopy(operation, action: action, before: before, context: context, focus: focus, attempts: attempts - 1)
            } else {
                self.resetClipboard() // No new clipboard content: do not paste stale data on the next tap.
            }
        }
    }
    @objc func showEditor() { window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true) }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { showEditor(); return true }
    func applicationWillTerminate(_ notification: Notification) {
        for ref in tapHotKeys { UnregisterEventHotKey(ref) }
        if let copyHotKey = copyHotKey { UnregisterEventHotKey(copyHotKey) }
        if let hotKey = hotKey { UnregisterEventHotKey(hotKey) }
        if let handler = handler { RemoveEventHandler(handler) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if navigationAction.shouldPerformDownload { decisionHandler(.download); return }
        let destination = navigationAction.request.url
        decisionHandler(destination?.host == url.host && destination?.port == url.port && destination?.scheme == "http" ? .allow : .cancel)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let save = NSSavePanel()
        save.nameFieldStringValue = suggestedFilename
        save.beginSheetModal(for: window) { result in completionHandler(result == .OK ? save.url : nil) }
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let open = NSOpenPanel()
        open.allowsMultipleSelection = false
        open.canChooseDirectories = false
        open.beginSheetModal(for: window) { result in completionHandler(result == .OK ? open.urls : nil) }
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard CommandLine.arguments.contains("--smoke-test") else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            self.web.evaluateJavaScript("JSON.stringify({keys:document.querySelectorAll('.key').length,ready:runtime?.ready,connection:document.getElementById('connection').textContent,saved:document.getElementById('save-setup').textContent})") { result, error in
                guard let result = result as? String, let bytes = result.data(using: .utf8),
                      var status = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any] else {
                    print("Native smoke failed: \(String(describing: error))"); fflush(stdout); NSApp.terminate(nil); return
                }
                self.web.evaluateJavaScript("document.getElementById('background').click()") { _, _ in
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        status["background"] = !self.window.isVisible
                        status["hotkeys"] = self.hotKeyReady
                        status["floating"] = NSApp.windows.contains { $0 is NSPanel && $0.isVisible }
                        status["titlebar"] = self.window.titlebarAppearsTransparent
                        self.showEditor()
                        status["reopened"] = self.window.isVisible
                        if let data = try? JSONSerialization.data(withJSONObject: status), let text = String(data: data, encoding: .utf8) { print(text) }
                        fflush(stdout)
                        NSApp.terminate(nil)
                    }
                }
            }
        }
    }
}

if CommandLine.arguments.contains("--tap-runtime-test") {
    _ = NSApplication.shared
    let host = Desktop(url: URL(string: "http://127.0.0.1/#test")!)
    host.enabled = true; host.testTapActions = []
    let binding: [String: Any] = ["type":"multi_tap", "window_ms":350,
        "single":["type":"clipboard","action":"copy"],
        "double":["type":"clipboard","action":"paste"],
        "triple":["type":"clipboard","action":"cut"]]
    host.currentProfile = ["bindings":["key1":binding,"key2":binding]]
    func wait(_ seconds: Double) { RunLoop.main.run(until: Date(timeIntervalSinceNow: seconds)) }
    host.multiTap(1); wait(0.4)
    precondition(host.testTapActions?.last?["action"] as? String == "copy")
    host.testTapActions = []
    host.multiTap(1); wait(0.1); host.multiTap(1)
    precondition(host.testTapActions!.isEmpty)
    wait(0.4)
    precondition(host.testTapActions?.last?["action"] as? String == "paste")
    host.testTapActions = []
    host.multiTap(1); host.multiTap(1); host.multiTap(1)
    precondition(host.testTapActions?.count == 1 && host.testTapActions?.last?["action"] as? String == "cut")
    wait(0.4); precondition(host.testTapActions?.count == 1)
    host.testTapActions = []
    host.multiTap(1); host.multiTap(2); host.multiTap(2); wait(0.4)
    precondition(host.testTapActions?.count == 2)
    precondition(Set(host.testTapActions!.compactMap { $0["action"] as? String }) == Set(["copy","paste"]))
    host.testTapActions = []
    host.multiTap(1); host.resetClipboard(); wait(0.4)
    precondition(host.testTapActions!.isEmpty)
    host.multiTap(1); host.tapFocus[1] = -1; wait(0.4)
    precondition(host.testTapActions!.isEmpty)
    print("Native multi-tap runtime passed: single/double/triple, independent keys, cancellation and focus guard; no input emitted.")
    exit(0)
}

if CommandLine.arguments.contains("--clipboard-format-test") {
    let board = NSPasteboard.withUniqueName()
    defer { board.releaseGlobally() }
    let rich = NSPasteboardItem()
    rich.setString("Hello café 👋", forType: .string)
    rich.setString("<b>Hello café 👋</b>", forType: .html)
    board.writeObjects([rich])
    precondition(stripTextFormatting(board))
    precondition(board.string(forType: .string) == "Hello café 👋")
    precondition(board.string(forType: .html) == nil)
    let file = NSPasteboardItem()
    file.setString("file:///tmp/example.txt", forType: .fileURL)
    file.setString("example.txt", forType: .string)
    board.clearContents(); board.writeObjects([file])
    precondition(!stripTextFormatting(board))
    precondition(board.string(forType: .fileURL) != nil)
    let picture = NSPasteboardItem()
    picture.setData(Data([1, 2, 3]), forType: .png)
    picture.setString("image caption", forType: .string)
    board.clearContents(); board.writeObjects([picture])
    precondition(!stripTextFormatting(board))
    print("Formatting checks passed on a private test pasteboard; general clipboard untouched.")
    exit(0)
}

if CommandLine.arguments.contains("--clipboard-state-test") {
    var g = ClipboardGesture()
    precondition(g.tap(now: 0, reset: 10, doubleTap: true) == nil)
    precondition(g.tap(now: 0.2, reset: 10, doubleTap: true) == "cut")
    g.complete("cut", now: 0.2)
    precondition(g.tap(now: 1, reset: 10, doubleTap: false) == "paste")
    g.complete("paste", now: 1)
    precondition(g.tap(now: 2, reset: 10, doubleTap: true) == nil)
    precondition(g.flush() == "copy")
    g.complete("copy", now: 2.4)
    precondition(g.tap(now: 12.4, reset: 10, doubleTap: false) == "copy")
    g.complete("copy", now: 13)
    precondition(g.tap(now: 500, reset: 0, doubleTap: false) == "paste")
    print("Clipboard gesture checks passed; no keyboard or clipboard access.")
    exit(0)
}

// Render a supplied fixture for visual review, without starting the server or hotkey.
if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--render-layout" {
    _ = NSApplication.shared
    guard let line = readLine(), let data = line.data(using: .utf8),
          let profile = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { exit(2) }
    let view = KeypadPreview(frame: NSRect(x: 0, y: 0, width: 440, height: 280))
    view.configure(profile: profile, title: profile["name"] as? String ?? "Preview", detail: "Visual fixture only")
    let window = NSWindow(contentRect: view.bounds, styleMask: .borderless, backing: .buffered, defer: false)
    window.contentView = view
    guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { exit(2) }
    view.cacheDisplay(in: view.bounds, to: bitmap)
    guard let png = bitmap.representation(using: .png, properties: [:]) else { exit(2) }
    do { try png.write(to: URL(fileURLWithPath: CommandLine.arguments[2])) } catch { exit(2) }
    exit(0)
}

guard let line = readLine(), let url = URL(string: line), url.host == "127.0.0.1" else { exit(1) }
let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = Desktop(url: url)
application.delegate = delegate
application.run()
