from core.ecs import Component
import asyncio
import threading
import json
import queue


class WebSocketComponent(Component):
    """
    WebSocket component supporting both server and client modes.

    Modes:
        - "server": Listens on host:port, accepts client connections.
        - "client": Connects to a remote WebSocket server.

    Usage in scripts:
        # Access the component
        ws = self.entity.get_component(WebSocketComponent)

        # Start the connection (call once, e.g. in on_start)
        ws.start()

        # In on_update, poll for incoming messages
        for sender, message in ws.poll():
            print(f"Received: {message}")

        # Send data
        ws.send("Hello")              # Client: send to server. Server: broadcast to all.
        ws.send_json({"key": "val"})  # Send a JSON-serializable dict.
        ws.broadcast("Hi everyone")   # Server only: broadcast to all clients.
        ws.send_to(client_id, "Hi")   # Server only: send to a specific client.

        # Stop cleanly
        ws.stop()
    """

    MODE_SERVER = "server"
    MODE_CLIENT = "client"
    _VALID_MODES = {MODE_SERVER, MODE_CLIENT}

    def __init__(
        self,
        mode: str = "client",
        host: str = "localhost",
        port: int = 8765,
        url: str = "",
        autostart: bool = False,
        max_queue_size: int = 1024,
    ):
        self.entity = None
        self.mode = mode if mode in self._VALID_MODES else self.MODE_CLIENT
        self.host = str(host or "localhost")
        self.port = max(1, min(65535, int(port)))
        self.url = str(url or "")
        self.autostart = bool(autostart)
        self.max_queue_size = max(1, int(max_queue_size))

        # Runtime state (not serialized)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._inbox: queue.Queue = queue.Queue(maxsize=self.max_queue_size)
        self._running = False
        self._started = False
        self._autostart_handled = False

        # Server state
        self._server = None
        self._clients: dict[int, object] = {}  # id -> websocket
        self._next_client_id = 1

        # Client state
        self._ws = None

        # Callbacks (set from user scripts)
        self.on_message_callback = None
        self.on_connect_callback = None
        self.on_disconnect_callback = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the WebSocket server or client in a background thread."""
        if self._started:
            return
        self._started = True
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the WebSocket server or client cleanly."""
        if not self._started:
            return
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._started = False
        self._loop = None
        self._thread = None
        self._server = None
        self._clients.clear()
        self._ws = None

    def is_running(self) -> bool:
        """Return True if the WebSocket is actively running."""
        return self._running and self._started

    def poll(self) -> list[tuple]:
        """
        Drain the inbox and return a list of (sender, message) tuples.
        Call this in on_update to process incoming messages on the game thread.

        For server mode, sender is the client_id (int).
        For client mode, sender is "server".
        Connection/disconnection events use sender "system" with message
        dicts like {"event": "connected", "client_id": id} or
        {"event": "disconnected", "client_id": id}.
        """
        messages = []
        while not self._inbox.empty():
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return messages

    def send(self, message: str):
        """
        Client mode: Send a message to the server.
        Server mode: Broadcast a message to all connected clients.
        """
        if not self._running or not self._loop:
            return
        if self.mode == self.MODE_CLIENT:
            self._schedule(self._client_send(message))
        else:
            self._schedule(self._server_broadcast(message))

    def send_json(self, data):
        """Send a JSON-serializable object as a string message."""
        try:
            self.send(json.dumps(data))
        except (TypeError, ValueError) as e:
            print(f"[WebSocket] Failed to serialize JSON: {e}")

    def broadcast(self, message: str):
        """Server only: Broadcast a message to all connected clients."""
        if self.mode != self.MODE_SERVER or not self._running or not self._loop:
            return
        self._schedule(self._server_broadcast(message))

    def send_to(self, client_id: int, message: str):
        """Server only: Send a message to a specific client by ID."""
        if self.mode != self.MODE_SERVER or not self._running or not self._loop:
            return
        self._schedule(self._server_send_to(client_id, message))

    def get_client_count(self) -> int:
        """Server only: Return the number of connected clients."""
        return len(self._clients)

    def get_client_ids(self) -> list[int]:
        """Server only: Return a list of connected client IDs."""
        return list(self._clients.keys())

    def get_url(self) -> str:
        """Return the effective WebSocket URL."""
        if self.mode == self.MODE_CLIENT:
            return self.url or f"ws://{self.host}:{self.port}"
        return f"ws://{self.host}:{self.port}"

    # ------------------------------------------------------------------
    # Internal: event loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Entry point for the background thread."""
        asyncio.set_event_loop(self._loop)
        try:
            if self.mode == self.MODE_SERVER:
                self._loop.run_until_complete(self._run_server())
            else:
                self._loop.run_until_complete(self._run_client())
        except Exception as e:
            if self._running:
                print(f"[WebSocket] Loop error: {e}")
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()

    def _schedule(self, coro):
        """Schedule a coroutine on the event loop from the game thread."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _enqueue(self, sender, message):
        """Put a message into the inbox queue (thread-safe)."""
        try:
            self._inbox.put_nowait((sender, message))
        except queue.Full:
            pass  # drop oldest not implemented; just drop new if full

    # ------------------------------------------------------------------
    # Server mode
    # ------------------------------------------------------------------

    async def _run_server(self):
        try:
            import websockets
        except ImportError:
            print("[WebSocket] 'websockets' package not installed. Run: pip install websockets")
            return

        async def handler(websocket):
            client_id = self._next_client_id
            self._next_client_id += 1
            self._clients[client_id] = websocket
            self._enqueue("system", {"event": "connected", "client_id": client_id})
            try:
                async for message in websocket:
                    self._enqueue(client_id, message)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self._clients.pop(client_id, None)
                self._enqueue("system", {"event": "disconnected", "client_id": client_id})

        try:
            self._server = await websockets.serve(handler, self.host, self.port)
            print(f"[WebSocket] Server started on ws://{self.host}:{self.port}")
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[WebSocket] Server error: {e}")
        finally:
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                print(f"[WebSocket] Server stopped")

    async def _server_broadcast(self, message: str):
        try:
            import websockets
        except ImportError:
            return
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.send(message)
            except Exception:
                self._clients.pop(client_id, None)

    async def _server_send_to(self, client_id: int, message: str):
        ws = self._clients.get(client_id)
        if ws is None:
            return
        try:
            await ws.send(message)
        except Exception:
            self._clients.pop(client_id, None)

    # ------------------------------------------------------------------
    # Client mode
    # ------------------------------------------------------------------

    async def _run_client(self):
        try:
            import websockets
        except ImportError:
            print("[WebSocket] 'websockets' package not installed. Run: pip install websockets")
            return

        target_url = self.url or f"ws://{self.host}:{self.port}"
        retry_delay = 1.0
        max_retry_delay = 30.0

        while self._running:
            try:
                async with websockets.connect(target_url) as ws:
                    self._ws = ws
                    retry_delay = 1.0
                    self._enqueue("system", {"event": "connected", "url": target_url})
                    print(f"[WebSocket] Client connected to {target_url}")
                    async for message in ws:
                        self._enqueue("server", message)
            except Exception as e:
                self._ws = None
                if self._running:
                    self._enqueue("system", {"event": "disconnected", "url": target_url, "reason": str(e)})
                    print(f"[WebSocket] Client disconnected: {e}. Retrying in {retry_delay:.1f}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)
                else:
                    break
        self._ws = None

    async def _client_send(self, message: str):
        if self._ws:
            try:
                await self._ws.send(message)
            except Exception as e:
                print(f"[WebSocket] Send error: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_destroy(self):
        """Called when the entity is destroyed."""
        self.stop()
