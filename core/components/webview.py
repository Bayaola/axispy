from core.ecs import Component
import threading
import queue


class WebviewComponent(Component):
    """
    Webview component that opens a native browser window using pywebview.

    Supports loading a URL or raw HTML content. The webview runs in a
    background thread so it doesn't block the game loop. Communication
    between the game and webview is done via message queues.

    Usage in scripts:
        wv = self.entity.get_component(WebviewComponent)

        # Open a URL
        wv.open()

        # Or open with specific URL
        wv.url = "https://example.com"
        wv.open()

        # Load raw HTML
        wv.load_html("<h1>Hello from engine!</h1>")

        # Evaluate JavaScript in the webview
        wv.evaluate_js("document.title")

        # Poll for JS evaluation results in on_update
        for result in wv.poll():
            print("JS result:", result)

        # Close the webview
        wv.close()
    """

    def __init__(
        self,
        url: str = "",
        title: str = "Webview",
        width: int = 800,
        height: int = 600,
        resizable: bool = True,
        frameless: bool = False,
        autoopen: bool = False,
    ):
        self.entity = None
        self.url = str(url or "")
        self.title = str(title or "Webview")
        self.width = max(100, int(width))
        self.height = max(100, int(height))
        self.resizable = bool(resizable)
        self.frameless = bool(frameless)
        self.autoopen = bool(autoopen)

        # Runtime state (not serialized)
        self._thread: threading.Thread | None = None
        self._window = None
        self._inbox: queue.Queue = queue.Queue()
        self._running = False
        self._autoopen_handled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, url: str = None):
        """Open the webview window. Optionally override the URL."""
        if self._running:
            return
        if url:
            self.url = url
        self._running = True
        self._thread = threading.Thread(target=self._run_webview, daemon=True)
        self._thread.start()

    def close(self):
        """Close the webview window."""
        if not self._running:
            return
        self._running = False
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._window = None

    def is_open(self) -> bool:
        """Return True if the webview window is currently open."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def load_url(self, url: str):
        """Navigate the webview to a new URL."""
        self.url = url
        if self._window:
            try:
                self._window.load_url(url)
            except Exception as e:
                print(f"[Webview] Failed to load URL: {e}")

    def load_html(self, html: str):
        """Load raw HTML content into the webview."""
        if self._window:
            try:
                self._window.load_html(html)
            except Exception as e:
                print(f"[Webview] Failed to load HTML: {e}")

    def evaluate_js(self, script: str):
        """
        Evaluate JavaScript in the webview. Results are queued
        and retrieved via poll().
        """
        if not self._window:
            return
        t = threading.Thread(target=self._eval_js_thread, args=(script,), daemon=True)
        t.start()

    def set_title(self, title: str):
        """Change the webview window title."""
        self.title = title
        if self._window:
            try:
                self._window.set_title(title)
            except Exception:
                pass

    def poll(self) -> list:
        """
        Drain the inbox and return a list of JS evaluation results.
        Call this in on_update.
        """
        results = []
        while not self._inbox.empty():
            try:
                results.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return results

    def get_url(self) -> str:
        """Return the current URL of the webview (if available)."""
        if self._window:
            try:
                return self._window.get_current_url() or self.url
            except Exception:
                pass
        return self.url

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_webview(self):
        """Entry point for the background thread."""
        try:
            import webview
        except ImportError:
            print("[Webview] 'pywebview' package not installed. Run: pip install pywebview")
            self._running = False
            return

        try:
            self._window = webview.create_window(
                self.title,
                url=self.url if self.url else None,
                width=self.width,
                height=self.height,
                resizable=self.resizable,
                frameless=self.frameless,
            )
            webview.start()
        except Exception as e:
            print(f"[Webview] Error: {e}")
        finally:
            self._running = False
            self._window = None

    def _eval_js_thread(self, script: str):
        """Evaluate JS and enqueue the result."""
        try:
            result = self._window.evaluate_js(script)
            self._inbox.put(result)
        except Exception as e:
            self._inbox.put({"error": str(e)})

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_destroy(self):
        """Called when the entity is destroyed."""
        self.close()
