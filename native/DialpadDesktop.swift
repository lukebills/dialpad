import Cocoa
import WebKit
import Carbon

// One scalable diagram is shared by the menu-bar preview and floating window.
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
final class Desktop: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    let url: URL
    let token: String
    var window: NSWindow!
    var web: WKWebView!
    var status: NSStatusItem!
    var panel: NSPanel!
    var panelPreview: KeypadPreview!
    var menuPreview: KeypadPreview!
    var currentProfile: [String: Any]?
    var menuFingerprint = ""
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
        web = WKWebView(frame: .zero)
        web.navigationDelegate = self
        web.uiDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1160, height: 830), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Dialpad"
        window.minSize = NSSize(width: 440, height: 560)
        window.isReleasedWhenClosed = false
        window.contentView = web
        window.center()
        web.load(URLRequest(url: url))
        showEditor()
        (panel, panelPreview) = makePanel(width: 440, height: 280)
        panel.isMovableByWindowBackground = true
        if UserDefaults.standard.bool(forKey: "floatingLayout") { panel.orderFrontRegardless() }
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

        var event = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let pointer = Unmanaged.passUnretained(self).toOpaque()
        let installed = InstallEventHandler(GetApplicationEventTarget(), { _, _, context in
            guard let context = context else { return OSStatus(eventNotHandledErr) }
            let host = Unmanaged<Desktop>.fromOpaque(context).takeUnretainedValue()
            DispatchQueue.main.async { if host.enabled { host.nextSetup() } }
            return noErr
        }, 1, &event, pointer, &handler)
        let registered = installed == noErr ? RegisterEventHotKey(UInt32(kVK_F18), 0, EventHotKeyID(signature: 0x4449414C, id: 1), GetApplicationEventTarget(), 0, &hotKey) : installed
        request("desktop-ready", body: ["ready": registered == noErr, "error": "F18 is unavailable. Close another Dialpad instance or app using F18, then reopen."]) { state, error in
            if let state = state { self.update(state) }
        }
        timer = Timer.scheduledTimer(withTimeInterval: 0.6, repeats: true) { _ in self.poll() }
    }

    func makePanel(width: CGFloat, height: CGFloat) -> (NSPanel, KeypadPreview) {
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: width, height: height), styleMask: [.nonactivatingPanel, .titled, .closable], backing: .buffered, defer: false)
        panel.title = "Dialpad · live layout"
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.backgroundColor = NSColor(calibratedRed: 0.96, green: 0.96, blue: 0.93, alpha: 1)
        let preview = KeypadPreview(frame: NSRect(x: 0, y: 0, width: width, height: height))
        preview.autoresizingMask = [.width, .height]
        panel.contentView = preview
        if let screen = NSScreen.main?.visibleFrame {
            panel.setFrameTopLeftPoint(NSPoint(x: screen.maxX - width - 24, y: screen.maxY - 35))
        }
        return (panel, preview)
    }

    func poll() {
        guard !polling else { return }
        polling = true
        request("setups") { state, error in
            self.polling = false
            if let state = state { self.update(state) }
            else {
                self.enabled = false
                self.currentName = "Disconnected"
                self.summary = "Dialpad is disconnected. Reopen the app to reconnect."
                self.currentProfile = nil
                self.refreshMenu()
            }
        }
    }

    func describe(_ action: [String: Any]) -> String {
        if action["type"] as? String == "shortcut" {
            let symbols = ["ctrl": "⌃", "alt": "⌥", "cmd": "⌘", "shift": "⇧"]
            let modifiers = (action["modifiers"] as? [String] ?? []).map { symbols[$0] ?? $0 }.joined()
            let key = action["key"] as? String ?? ""
            return modifiers + (key == "NONE" ? "" : key)
        }
        return (action["action"] as? String ?? "").replacingOccurrences(of: "_", with: " ")
    }

    func update(_ state: [String: Any]) {
        enabled = state["enabled"] as? Bool ?? false
        if let profile = state["current"] as? [String: Any], enabled {
            currentProfile = profile
            currentName = profile["name"] as? String ?? "Setup"
            let labels = profile["labels"] as? [String: String] ?? [:]
            let bindings = profile["bindings"] as? [String: [String: Any]] ?? [:]
            let rows = (1...6).map { i -> String in
                let key = "key\(i)"
                return "\(i)   \(labels[key] ?? key)   ·   \(describe(bindings[key] ?? [:]))"
            }
            summary = currentName + "\n\n" + rows.joined(separator: "\n\n") + "\n\n↶ \(describe(bindings["dial_ccw"] ?? [:]))   ↷ \(describe(bindings["dial_cw"] ?? [:]))\nPress dial → Next setup"
        } else {
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
        panelPreview.configure(profile: currentProfile, title: currentName, detail: summary)
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
        let floating = menu.addItem(withTitle: "Show / hide floating layout", action: #selector(togglePanel), keyEquivalent: "")
        floating.target = self
        menu.addItem(withTitle: "Open editor", action: #selector(showEditor), keyEquivalent: "").target = self
        menu.addItem(withTitle: "Quit Dialpad", action: #selector(quit), keyEquivalent: "").target = self
        menu.autoenablesItems = false
        status.menu = menu
    }

    @objc func nextSetup() {
        guard enabled && !cycling else { return }
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
    @objc func showEditor() { window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true) }
    @objc func togglePanel() {
        if panel.isVisible { panel.orderOut(nil) } else { panel.orderFrontRegardless() }
        UserDefaults.standard.set(panel.isVisible, forKey: "floatingLayout")
    }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { showEditor(); return true }
    func applicationWillTerminate(_ notification: Notification) {
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
                if let result = result as? String { print(result) }
                else { print("Native smoke failed: \(String(describing: error))") }
                fflush(stdout)
                NSApp.terminate(nil)
            }
        }
    }
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
