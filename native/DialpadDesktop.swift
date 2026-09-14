import Cocoa
import WebKit
import Carbon

// The host receives the session URL on stdin, never through the process arguments.
final class Desktop: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    let url: URL
    let token: String
    var window: NSWindow!
    var web: WKWebView!
    var status: NSStatusItem!
    var panel: NSPanel!
    var panelText: NSTextField!
    var toast: NSPanel!
    var toastText: NSTextField!
    var hotKey: EventHotKeyRef?
    var handler: EventHandlerRef?
    var timer: Timer?
    var toastTimer: Timer?
    var generation = -1
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
        (panel, panelText) = makePanel(width: 350, height: 315)
        panel.isMovableByWindowBackground = true
        (toast, toastText) = makePanel(width: 350, height: 85)
        toast.ignoresMouseEvents = true
        if UserDefaults.standard.bool(forKey: "floatingLayout") { panel.orderFrontRegardless() }
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
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
            if registered != noErr { self.showToast("Dial shortcut unavailable", "F18 is already in use. See the editor.") }
        }
        timer = Timer.scheduledTimer(withTimeInterval: 0.6, repeats: true) { _ in self.poll() }
    }

    func makePanel(width: CGFloat, height: CGFloat) -> (NSPanel, NSTextField) {
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: width, height: height), styleMask: [.nonactivatingPanel, .titled, .closable], backing: .buffered, defer: false)
        panel.title = "Dialpad · live layout"
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.backgroundColor = NSColor(calibratedRed: 0.96, green: 0.96, blue: 0.93, alpha: 1)
        let text = NSTextField(wrappingLabelWithString: summary)
        text.frame = NSRect(x: 18, y: 12, width: width - 36, height: height - 24)
        text.autoresizingMask = [.width, .height]
        text.font = .systemFont(ofSize: 13)
        text.textColor = NSColor(calibratedRed: 0.16, green: 0.24, blue: 0.18, alpha: 1)
        panel.contentView?.addSubview(text)
        if let screen = NSScreen.main?.visibleFrame {
            panel.setFrameTopLeftPoint(NSPoint(x: screen.maxX - width - 24, y: screen.maxY - 35))
        }
        return (panel, text)
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
                self.panelText.stringValue = self.summary
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
        let nextGeneration = state["generation"] as? Int ?? 0
        let changed = generation != nextGeneration
        generation = nextGeneration
        if let profile = state["current"] as? [String: Any], enabled {
            currentName = profile["name"] as? String ?? "Setup"
            let labels = profile["labels"] as? [String: String] ?? [:]
            let bindings = profile["bindings"] as? [String: [String: Any]] ?? [:]
            let rows = (1...6).map { i -> String in
                let key = "key\(i)"
                return "\(i)   \(labels[key] ?? key)   ·   \(describe(bindings[key] ?? [:]))"
            }
            summary = currentName + "\n\n" + rows.joined(separator: "\n\n") + "\n\n↶ \(describe(bindings["dial_ccw"] ?? [:]))   ↷ \(describe(bindings["dial_cw"] ?? [:]))\nPress dial → Next setup"
            if changed { showToast(currentName, "Layout sent · press the dial for the next setup") }
        } else {
            currentName = "Cycling off"
            let error = state["error"] as? String ?? ""
            summary = error.isEmpty ? "Setup cycling is off.\n\nOpen the editor to save and enable setups.\n\nThe keypad keeps its last written bindings. Reapply a normal layout to restore the dial press." : error
            if changed && !error.isEmpty { showToast("Dialpad needs attention", error) }
        }
        panelText.stringValue = summary
        refreshMenu()
    }

    func refreshMenu() {
        status.button?.title = "◉ " + String(currentName.prefix(24))
        status.button?.toolTip = summary
        let menu = NSMenu()
        let heading = NSMenuItem(title: currentName, action: nil, keyEquivalent: "")
        menu.addItem(heading)
        for line in summary.components(separatedBy: "\n").filter({ !$0.isEmpty }).dropFirst() {
            menu.addItem(NSMenuItem(title: line, action: nil, keyEquivalent: ""))
        }
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

    func showToast(_ title: String, _ detail: String) {
        toastText.stringValue = title + "\n" + detail
        toast.orderFrontRegardless()
        toastTimer?.invalidate()
        toastTimer = Timer.scheduledTimer(withTimeInterval: 3, repeats: false) { _ in self.toast.orderOut(nil) }
    }

    @objc func nextSetup() {
        guard enabled && !cycling else { return }
        cycling = true
        request("setups/cycle", body: [:]) { state, error in
            self.cycling = false
            if let state = state, state["generation"] != nil { self.update(state) }
            if let error = error { self.showToast("Setup did not change", error); self.poll() }
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

guard let line = readLine(), let url = URL(string: line), url.host == "127.0.0.1" else { exit(1) }
let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = Desktop(url: url)
application.delegate = delegate
application.run()
