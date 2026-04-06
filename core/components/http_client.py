from core.ecs import Component
import threading
import queue
import json
import urllib.request
import urllib.error
import urllib.parse


class HTTPResponse:
    """Represents an HTTP response returned by HTTPClientComponent."""
    __slots__ = ("status_code", "body", "headers", "error", "tag")

    def __init__(self, status_code: int = 0, body: str = "", headers: dict = None,
                 error: str = "", tag: str = ""):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
        self.error = error
        self.tag = tag

    def json(self):
        """Parse body as JSON. Returns None on failure."""
        try:
            return json.loads(self.body)
        except (json.JSONDecodeError, TypeError):
            return None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300 and not self.error


class HTTPClientComponent(Component):
    """
    Persistent HTTP client component for making async HTTP requests.

    Uses a background thread pool to perform requests without blocking
    the game loop. Results are queued and retrieved via poll().

    Usage in scripts:
        http = self.entity.get_component(HTTPClientComponent)

        # GET request
        http.get("https://api.example.com/data", tag="fetch_data")

        # POST request with JSON body
        http.post("https://api.example.com/submit",
                  body={"key": "value"}, tag="submit")

        # In on_update, poll for completed responses
        for response in http.poll():
            if response.ok:
                data = response.json()
                print(f"[{response.tag}] Got: {data}")
            else:
                print(f"[{response.tag}] Error: {response.error}")
    """

    def __init__(
        self,
        base_url: str = "",
        default_headers: dict = None,
        timeout: float = 30.0,
        max_concurrent: int = 4,
    ):
        self.entity = None
        self.base_url = str(base_url or "")
        self.default_headers = dict(default_headers) if default_headers else {}
        self.timeout = max(1.0, float(timeout))
        self.max_concurrent = max(1, int(max_concurrent))

        # Runtime state (not serialized)
        self._inbox: queue.Queue = queue.Queue()
        self._semaphore = threading.Semaphore(self.max_concurrent)
        self._active_threads: list[threading.Thread] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, url: str, headers: dict = None, tag: str = ""):
        """Perform an async GET request."""
        self._request("GET", url, headers=headers, tag=tag)

    def post(self, url: str, body=None, headers: dict = None, tag: str = ""):
        """Perform an async POST request. Body can be str, bytes, or dict (sent as JSON)."""
        self._request("POST", url, body=body, headers=headers, tag=tag)

    def put(self, url: str, body=None, headers: dict = None, tag: str = ""):
        """Perform an async PUT request."""
        self._request("PUT", url, body=body, headers=headers, tag=tag)

    def delete(self, url: str, headers: dict = None, tag: str = ""):
        """Perform an async DELETE request."""
        self._request("DELETE", url, headers=headers, tag=tag)

    def patch(self, url: str, body=None, headers: dict = None, tag: str = ""):
        """Perform an async PATCH request."""
        self._request("PATCH", url, body=body, headers=headers, tag=tag)

    def poll(self) -> list[HTTPResponse]:
        """
        Drain the response inbox. Call this in on_update.
        Returns a list of HTTPResponse objects for completed requests.
        """
        responses = []
        while not self._inbox.empty():
            try:
                responses.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        # Clean up finished threads
        self._active_threads = [t for t in self._active_threads if t.is_alive()]
        return responses

    def get_pending_count(self) -> int:
        """Return number of in-flight requests."""
        return len([t for t in self._active_threads if t.is_alive()])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _request(self, method: str, url: str, body=None, headers: dict = None, tag: str = ""):
        """Launch an HTTP request in a background thread."""
        full_url = self._resolve_url(url)
        merged_headers = dict(self.default_headers)
        if headers:
            merged_headers.update(headers)

        t = threading.Thread(
            target=self._do_request,
            args=(method, full_url, body, merged_headers, tag),
            daemon=True
        )
        self._active_threads.append(t)
        t.start()

    def _resolve_url(self, url: str) -> str:
        """Prepend base_url if url is a relative path."""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        base = self.base_url.rstrip("/")
        path = url.lstrip("/")
        return f"{base}/{path}" if base else path

    def _do_request(self, method: str, url: str, body, headers: dict, tag: str):
        """Execute the HTTP request (runs in a background thread)."""
        self._semaphore.acquire()
        try:
            # Prepare body
            data_bytes = None
            if body is not None:
                if isinstance(body, dict) or isinstance(body, list):
                    data_bytes = json.dumps(body).encode("utf-8")
                    headers.setdefault("Content-Type", "application/json")
                elif isinstance(body, str):
                    data_bytes = body.encode("utf-8")
                elif isinstance(body, bytes):
                    data_bytes = body

            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers=headers,
                method=method.upper()
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8", errors="replace")
                    resp_headers = dict(resp.headers)
                    self._inbox.put(HTTPResponse(
                        status_code=resp.status,
                        body=resp_body,
                        headers=resp_headers,
                        tag=tag
                    ))
            except urllib.error.HTTPError as e:
                resp_body = ""
                try:
                    resp_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                self._inbox.put(HTTPResponse(
                    status_code=e.code,
                    body=resp_body,
                    headers=dict(e.headers) if e.headers else {},
                    error=str(e.reason),
                    tag=tag
                ))
            except Exception as e:
                self._inbox.put(HTTPResponse(
                    error=str(e),
                    tag=tag
                ))
        finally:
            self._semaphore.release()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_destroy(self):
        """Wait briefly for pending threads to finish."""
        for t in self._active_threads:
            t.join(timeout=0.5)
        self._active_threads.clear()
