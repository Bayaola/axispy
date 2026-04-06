from core.ecs import Component
import asyncio
import threading
import json
import queue


class WebRTCComponent(Component):
    """
    WebRTC component for peer-to-peer data channel communication.

    Supports creating and joining peer connections with data channels
    for low-latency game networking. Uses aiortc under the hood.
    A signaling mechanism (e.g. WebSocket) is needed to exchange
    offers/answers/ICE candidates between peers.

    Usage in scripts:
        rtc = self.entity.get_component(WebRTCComponent)

        # Create an offer (caller side)
        rtc.create_offer()

        # Poll for signaling data to send to the remote peer
        for sender, msg in rtc.poll():
            if sender == "local":
                # msg is a dict like {"type": "offer", "sdp": "..."} or
                # {"type": "candidate", ...}
                # Send this to the remote peer via your signaling channel
                ws.send_json(msg)

        # On the remote side, set the remote description from received signaling
        rtc.set_remote_description(offer_dict)  # triggers answer creation

        # Feed ICE candidates from the remote peer
        rtc.add_ice_candidate(candidate_dict)

        # Send data over the data channel
        rtc.send("Hello peer!")
        rtc.send_json({"action": "move", "x": 10})

        # Poll for incoming data channel messages
        for sender, msg in rtc.poll():
            if sender == "datachannel":
                print("Received:", msg)

        # Close
        rtc.close()
    """

    def __init__(
        self,
        ice_servers: str = "stun:stun.l.google.com:19302",
        data_channel_label: str = "game",
        ordered: bool = True,
        max_retransmits: int = -1,
        autostart: bool = False,
        max_queue_size: int = 1024,
    ):
        self.entity = None
        self.ice_servers = str(ice_servers or "stun:stun.l.google.com:19302")
        self.data_channel_label = str(data_channel_label or "game")
        self.ordered = bool(ordered)
        self.max_retransmits = int(max_retransmits)
        self.autostart = bool(autostart)
        self.max_queue_size = max(1, int(max_queue_size))

        # Runtime state (not serialized)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._inbox: queue.Queue = queue.Queue(maxsize=self.max_queue_size)
        self._running = False
        self._started = False
        self._autostart_handled = False

        self._pc = None  # RTCPeerConnection
        self._dc = None  # RTCDataChannel
        self._connected = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Initialize the peer connection and background event loop."""
        if self._started:
            return
        self._started = True
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def close(self):
        """Close the peer connection and stop the event loop."""
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
        self._pc = None
        self._dc = None
        self._connected = False

    def is_connected(self) -> bool:
        """Return True if the data channel is open."""
        return self._connected

    def is_running(self) -> bool:
        """Return True if the WebRTC component is actively running."""
        return self._running and self._started

    def poll(self) -> list[tuple]:
        """
        Drain the inbox and return a list of (sender, message) tuples.
        Call this in on_update.

        Sender types:
          - "local": signaling data to forward to the remote peer
                     (offer, answer, or ICE candidate dicts)
          - "datachannel": data received from the remote peer
          - "system": connection state events like
                      {"event": "connected"}, {"event": "disconnected"},
                      {"event": "error", "message": "..."}
        """
        messages = []
        while not self._inbox.empty():
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return messages

    def create_offer(self):
        """Create an SDP offer (caller side). Results appear in poll() as local signaling."""
        if not self._running or not self._loop:
            return
        self._schedule(self._create_offer())

    def create_answer(self):
        """Create an SDP answer (callee side). Results appear in poll() as local signaling."""
        if not self._running or not self._loop:
            return
        self._schedule(self._create_answer())

    def set_remote_description(self, sdp_dict: dict):
        """
        Set the remote SDP description received from the signaling channel.
        sdp_dict should have keys "type" ("offer" or "answer") and "sdp".
        If type is "offer", an answer is automatically created.
        """
        if not self._running or not self._loop:
            return
        self._schedule(self._set_remote_description(sdp_dict))

    def add_ice_candidate(self, candidate_dict: dict):
        """
        Add an ICE candidate received from the signaling channel.
        candidate_dict should have keys like "candidate", "sdpMid", "sdpMLineIndex".
        """
        if not self._running or not self._loop:
            return
        self._schedule(self._add_ice_candidate(candidate_dict))

    def send(self, message: str):
        """Send a string message over the data channel."""
        if not self._connected or not self._dc:
            return
        try:
            self._dc.send(message)
        except Exception as e:
            print(f"[WebRTC] Send error: {e}")

    def send_json(self, data):
        """Send a JSON-serializable object as a string message."""
        try:
            self.send(json.dumps(data))
        except (TypeError, ValueError) as e:
            print(f"[WebRTC] Failed to serialize JSON: {e}")

    def send_bytes(self, data: bytes):
        """Send raw bytes over the data channel."""
        if not self._connected or not self._dc:
            return
        try:
            self._dc.send(data)
        except Exception as e:
            print(f"[WebRTC] Send bytes error: {e}")

    # ------------------------------------------------------------------
    # Internal: event loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Entry point for the background thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._init_peer_connection())
            self._loop.run_forever()
        except Exception as e:
            if self._running:
                print(f"[WebRTC] Loop error: {e}")
                self._enqueue("system", {"event": "error", "message": str(e)})
        finally:
            if self._pc:
                try:
                    self._loop.run_until_complete(self._pc.close())
                except Exception:
                    pass
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
            pass

    # ------------------------------------------------------------------
    # Internal: peer connection setup
    # ------------------------------------------------------------------

    async def _init_peer_connection(self):
        try:
            from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer
        except ImportError:
            print("[WebRTC] 'aiortc' package not installed. Run: pip install aiortc")
            self._enqueue("system", {"event": "error", "message": "aiortc not installed"})
            self._running = False
            return

        ice_list = []
        for server_url in self.ice_servers.split(","):
            url = server_url.strip()
            if url:
                ice_list.append(RTCIceServer(urls=[url]))

        config = RTCConfiguration(iceServers=ice_list) if ice_list else RTCConfiguration()
        self._pc = RTCPeerConnection(configuration=config)

        @self._pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if candidate:
                self._enqueue("local", {
                    "type": "candidate",
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                })

        @self._pc.on("connectionstatechange")
        async def on_connection_state_change():
            state = self._pc.connectionState
            if state == "connected":
                self._connected = True
                self._enqueue("system", {"event": "connected"})
                print("[WebRTC] Peer connected")
            elif state in ("disconnected", "failed", "closed"):
                self._connected = False
                self._enqueue("system", {"event": "disconnected", "state": state})
                print(f"[WebRTC] Connection state: {state}")

        @self._pc.on("datachannel")
        def on_datachannel(channel):
            self._dc = channel
            self._setup_data_channel_events(channel)
            print(f"[WebRTC] Remote data channel received: {channel.label}")

    def _setup_data_channel_events(self, channel):
        @channel.on("open")
        def on_open():
            self._connected = True
            self._enqueue("system", {"event": "datachannel_open", "label": channel.label})
            print(f"[WebRTC] Data channel '{channel.label}' open")

        @channel.on("close")
        def on_close():
            self._connected = False
            self._enqueue("system", {"event": "datachannel_close", "label": channel.label})

        @channel.on("message")
        def on_message(message):
            self._enqueue("datachannel", message)

    # ------------------------------------------------------------------
    # Internal: signaling
    # ------------------------------------------------------------------

    async def _create_offer(self):
        try:
            from aiortc import RTCSessionDescription
        except ImportError:
            return

        # Create data channel (caller creates it)
        dc_options = {}
        if not self.ordered:
            dc_options["ordered"] = False
        if self.max_retransmits >= 0:
            dc_options["maxRetransmits"] = self.max_retransmits

        self._dc = self._pc.createDataChannel(self.data_channel_label, **dc_options)
        self._setup_data_channel_events(self._dc)

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        self._enqueue("local", {
            "type": "offer",
            "sdp": self._pc.localDescription.sdp,
        })
        print("[WebRTC] Offer created")

    async def _create_answer(self):
        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)

        self._enqueue("local", {
            "type": "answer",
            "sdp": self._pc.localDescription.sdp,
        })
        print("[WebRTC] Answer created")

    async def _set_remote_description(self, sdp_dict: dict):
        try:
            from aiortc import RTCSessionDescription
        except ImportError:
            return

        sdp_type = sdp_dict.get("type", "")
        sdp = sdp_dict.get("sdp", "")
        if not sdp_type or not sdp:
            return

        rd = RTCSessionDescription(sdp=sdp, type=sdp_type)
        await self._pc.setRemoteDescription(rd)
        print(f"[WebRTC] Remote description set ({sdp_type})")

        if sdp_type == "offer":
            await self._create_answer()

    async def _add_ice_candidate(self, candidate_dict: dict):
        try:
            from aiortc import RTCIceCandidate
        except ImportError:
            return

        candidate_str = candidate_dict.get("candidate", "")
        if not candidate_str:
            return

        sdp_mid = candidate_dict.get("sdpMid", "")
        sdp_mline_index = candidate_dict.get("sdpMLineIndex", 0)

        try:
            candidate = RTCIceCandidate(
                candidate=candidate_str,
                sdpMid=sdp_mid,
                sdpMLineIndex=sdp_mline_index,
            )
            await self._pc.addIceCandidate(candidate)
        except Exception as e:
            print(f"[WebRTC] Failed to add ICE candidate: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_destroy(self):
        """Called when the entity is destroyed."""
        self.close()
