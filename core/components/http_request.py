from core.ecs import Component
import threading
import json
import urllib.request
import urllib.error


class HTTPRequestComponent(Component):
    """
    Lightweight single-request component. Configure in the inspector or script,
    fire it, and poll for the result.

    Usage in scripts:
        req = self.entity.get_component(HTTPRequestComponent)

        # Configure and send
        req.url = "https://api.example.com/data"
        req.method = "GET"
        req.send()

        # In on_update, check if done
        if req.is_done():
            print(req.status_code, req.response_body)
            if req.ok:
                data = req.json()

        # Or send with body
        req.url = "https://api.example.com/submit"
        req.method = "POST"
        req.request_body = '{"key": "value"}'
        req.send()
    """

    METHOD_GET = "GET"
    METHOD_POST = "POST"
    METHOD_PUT = "PUT"
    METHOD_DELETE = "DELETE"
    METHOD_PATCH = "PATCH"
    _VALID_METHODS = {METHOD_GET, METHOD_POST, METHOD_PUT, METHOD_DELETE, METHOD_PATCH}

    def __init__(
        self,
        url: str = "",
        method: str = "GET",
        request_body: str = "",
        content_type: str = "application/json",
        timeout: float = 30.0,
        send_on_start: bool = False,
    ):
        self.entity = None
        self.url = str(url or "")
        self.method = method.upper() if method.upper() in self._VALID_METHODS else self.METHOD_GET
        self.request_body = str(request_body or "")
        self.content_type = str(content_type or "application/json")
        self.timeout = max(1.0, float(timeout))
        self.send_on_start = bool(send_on_start)

        # Custom headers (set from script)
        self.headers: dict = {}

        # Response state (read-only from scripts)
        self.status_code: int = 0
        self.response_body: str = ""
        self.response_headers: dict = {}
        self.error: str = ""

        # Internal
        self._thread: threading.Thread | None = None
        self._done = False
        self._sending = False
        self._send_on_start_handled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self):
        """Fire the HTTP request in a background thread."""
        if self._sending:
            return
        if not self.url:
            self.error = "No URL specified"
            self._done = True
            return

        self._done = False
        self._sending = True
        self.status_code = 0
        self.response_body = ""
        self.response_headers = {}
        self.error = ""

        self._thread = threading.Thread(target=self._do_request, daemon=True)
        self._thread.start()

    def is_done(self) -> bool:
        """Return True if the request has completed (success or error)."""
        return self._done

    def is_sending(self) -> bool:
        """Return True if a request is currently in flight."""
        return self._sending and not self._done

    @property
    def ok(self) -> bool:
        """Return True if the last request was successful (2xx)."""
        return self._done and 200 <= self.status_code < 300 and not self.error

    def json(self):
        """Parse response_body as JSON. Returns None on failure."""
        try:
            return json.loads(self.response_body)
        except (json.JSONDecodeError, TypeError):
            return None

    def reset(self):
        """Reset the response state for reuse."""
        self.status_code = 0
        self.response_body = ""
        self.response_headers = {}
        self.error = ""
        self._done = False
        self._sending = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_request(self):
        """Execute the HTTP request (runs in background thread)."""
        try:
            merged_headers = dict(self.headers)
            data_bytes = None

            if self.request_body and self.method in ("POST", "PUT", "PATCH"):
                data_bytes = self.request_body.encode("utf-8")
                merged_headers.setdefault("Content-Type", self.content_type)

            req = urllib.request.Request(
                self.url,
                data=data_bytes,
                headers=merged_headers,
                method=self.method
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    self.response_body = resp.read().decode("utf-8", errors="replace")
                    self.response_headers = dict(resp.headers)
                    self.status_code = resp.status
            except urllib.error.HTTPError as e:
                self.status_code = e.code
                try:
                    self.response_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                self.response_headers = dict(e.headers) if e.headers else {}
                self.error = str(e.reason)
            except Exception as e:
                self.error = str(e)
        finally:
            self._done = True
            self._sending = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_destroy(self):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
