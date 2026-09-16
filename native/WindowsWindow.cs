// Native Windows shell for the same local editor used on Mac. No browser tab or console.
using System;
using System.Drawing;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Collections.Generic;

sealed class DialpadWindow : Form
{
    readonly WebView2 web = new WebView2();
    readonly NotifyIcon tray = new NotifyIcon();
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    readonly HttpClient http = new HttpClient(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false });
    readonly Uri address;
    readonly string userData;
    readonly bool smoke;
    readonly ToolStripMenuItem layoutItem = new ToolStripMenuItem("Dialpad is starting…");
    bool exiting, loaded;

    [DllImport("dwmapi.dll")]
    static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

    public DialpadWindow(Dictionary<string, object> config)
    {
        address = new Uri((string)config["url"]);
        if (address.Scheme != "http" || address.Host != "127.0.0.1" || address.Fragment.Length < 2)
            throw new ArgumentException("Invalid local app address.");
        userData = (string)config["user_data"];
        smoke = config.ContainsKey("smoke") && (bool)config["smoke"];
        http.BaseAddress = new Uri(address.GetLeftPart(UriPartial.Authority) + "/api/");
        http.Timeout = TimeSpan.FromSeconds(15);
        http.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", address.Fragment.Substring(1));
        Text = "Dialpad";
        BackColor = Color.FromArgb(245, 244, 239);
        ClientSize = new Size(1100, 800);
        MinimumSize = new Size(480, 600);
        StartPosition = FormStartPosition.CenterScreen;
        Icon = new Icon(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Dialpad.ico"));
        web.Dock = DockStyle.Fill;
        web.DefaultBackgroundColor = BackColor;
        Controls.Add(web);
        var menu = new ContextMenuStrip();
        layoutItem.Enabled = false;
        menu.Items.Add(layoutItem);
        menu.Items.Add("Open Dialpad", null, (sender, e) => ShowEditor());
        menu.Items.Add("Quit Dialpad", null, async (sender, e) => await QuitApp());
        tray.Icon = Icon;
        tray.Text = "Dialpad";
        tray.ContextMenuStrip = menu;
        tray.DoubleClick += (sender, e) => ShowEditor();
        tray.Visible = true;
        FormClosing += (sender, e) => {
            if (!exiting && e.CloseReason == CloseReason.UserClosing) { e.Cancel = true; HideEditor(); }
        };
        Shown += async (sender, e) => { if (!loaded) { loaded = true; await Initialize(); } };
        HandleCreated += (sender, e) => {
            // Windows 11 supports these; older Windows keeps its standard title bar.
            try {
                int color = ColorTranslator.ToWin32(BackColor), dark = 0;
                DwmSetWindowAttribute(Handle, 20, ref dark, 4);
                DwmSetWindowAttribute(Handle, 35, ref color, 4);
            } catch (DllNotFoundException) { }
        };
    }

    bool IsLocal(string value)
    {
        Uri target;
        return Uri.TryCreate(value, UriKind.Absolute, out target) &&
            target.Scheme == address.Scheme && target.Host == address.Host && target.Port == address.Port;
    }

    void Report(object value)
    {
        Console.Out.WriteLine(json.Serialize(value));
        Console.Out.Flush();
    }

    public void ShowEditor()
    {
        Show();
        if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
        Activate();
        Report(new { kind = "visibility", visible = true });
    }

    void HideEditor()
    {
        Hide();
        Report(new { kind = "visibility", visible = false });
    }

    async Task QuitApp()
    {
        try { await http.PostAsync("quit", new StringContent("{}", System.Text.Encoding.UTF8, "application/json")); }
        catch (HttpRequestException) { }
        catch (TaskCanceledException) { }
        exiting = true;
        Close();
    }

    async Task Initialize()
    {
        try {
            var environment = await CoreWebView2Environment.CreateAsync(null, userData);
            await web.EnsureCoreWebView2Async(environment);
            var core = web.CoreWebView2;
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = false;
            core.Settings.IsStatusBarEnabled = false;
            core.Settings.IsZoomControlEnabled = false;
            core.NavigationStarting += (sender, e) => { if (!IsLocal(e.Uri)) e.Cancel = true; };
            core.FrameNavigationStarting += (sender, e) => { e.Cancel = true; };
            core.NewWindowRequested += (sender, e) => { e.Handled = true; };
            core.PermissionRequested += (sender, e) => { e.State = CoreWebView2PermissionState.Deny; };
            core.WebMessageReceived += (sender, e) => {
                if (!IsLocal(e.Source)) return;
                if (e.TryGetWebMessageAsString() == "hide") HideEditor();
            };
            core.DownloadStarting += (sender, e) => {
                // Profile export uses a local blob; always let the user choose the file.
                if (!e.DownloadOperation.Uri.StartsWith("blob:" + address.GetLeftPart(UriPartial.Authority) + "/", StringComparison.Ordinal)) {
                    e.Cancel = true; return;
                }
                using (var dialog = new SaveFileDialog()) {
                    dialog.Filter = "Dialpad setup (*.json)|*.json";
                    dialog.FileName = Path.GetFileName(e.ResultFilePath);
                    if (dialog.ShowDialog(this) != DialogResult.OK) { e.Cancel = true; return; }
                    e.ResultFilePath = dialog.FileName;
                    e.Handled = true;
                }
            };
            core.NavigationCompleted += async (sender, e) => {
                if (!e.IsSuccess) {
                    Report(new { kind = "error", message = "The local editor could not load." });
                    return;
                }
                // Wait for the app's own async initialization; a loaded document alone is insufficient.
                for (int attempt = 0; attempt < 100; attempt++) {
                    var result = await core.ExecuteScriptAsync("document.querySelectorAll('.key').length === 6 && document.getElementById('autosave-status').textContent === 'Saved in app'");
                    if (result == "true") {
                        bool hidden = false, reopened = false;
                        if (smoke) { HideEditor(); hidden = !Visible; ShowEditor(); reopened = Visible; }
                        Report(new { kind = "ready", ready = true, keys = 6, native = true, hidden = hidden, reopened = reopened });
                        return;
                    }
                    await Task.Delay(100);
                }
                Report(new { kind = "error", message = "The editor did not finish loading." });
            };
            core.Navigate(address.AbsoluteUri);
            return;
        } catch (WebView2RuntimeNotFoundException) {
            Report(new { kind = "error", message = "Microsoft Edge WebView2 Runtime is missing." });
            MessageBox.Show(this, "Dialpad needs Microsoft Edge WebView2 Runtime to display its Windows window.\n\nInstall the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2 then reopen Dialpad. A standard user can install it for their own account.", "WebView2 Runtime required", MessageBoxButtons.OK, MessageBoxIcon.Information);
        } catch (Exception) {
            Report(new { kind = "error", message = "The Windows editor could not start." });
            MessageBox.Show(this, "The Windows editor could not start. Keep the whole Dialpad folder together and check that Microsoft Edge WebView2 Runtime is installed.", "Dialpad", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        await QuitApp();
    }

    public void Listen()
    {
        Task.Run(() => {
            string line;
            while ((line = Console.ReadLine()) != null) {
                var command = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(line);
                BeginInvoke((Action)(() => {
                    var kind = (string)command["kind"];
                    if (kind == "show") ShowEditor();
                    else if (kind == "status") {
                        var name = (string)command["name"];
                        Text = "Dialpad · " + name;
                        layoutItem.Text = name;
                        var tip = "Dialpad · " + name;
                        tray.Text = tip.Substring(0, Math.Min(63, tip.Length));
                    } else if (kind == "quit") { exiting = true; Close(); }
                }));
            }
            // Parent termination must not strand a tray process.
            if (!IsDisposed) BeginInvoke((Action)(() => { exiting = true; Close(); }));
        });
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) { tray.Visible = false; tray.Dispose(); http.Dispose(); }
        base.Dispose(disposing);
    }

    [STAThread]
    static void Main()
    {
        try {
            var config = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(Console.ReadLine());
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (var window = new DialpadWindow(config)) {
                var unused = window.Handle;
                window.Listen();
                Application.Run(window);
            }
        } catch (Exception) {
            Console.Out.WriteLine("{\"kind\":\"error\",\"message\":\"Windows window failed to initialize.\"}");
            Environment.ExitCode = 1;
        }
    }
}
