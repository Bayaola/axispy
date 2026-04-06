from core.ecs import Component
from core.multiplayer.protocol import MessageType, encode_message, decode_message
from core.multiplayer.room import Room, Player
import uuid
import time
import queue
from core.logger import get_logger

_mp_logger = get_logger("multiplayer")


class MultiplayerComponent(Component):
    """
    High-level multiplayer manager component.

    Attach to a single entity (e.g. a GameManager) to manage multiplayer
    sessions. Uses a WebSocketComponent on the same entity for transport.
    Provides lobby management, player tracking, RPCs, and state sync.

    Modes:
        - "host": Creates a WebSocket server, manages the room as authority.
        - "client": Connects to a host's WebSocket server.

    Usage in scripts:
        mp = self.entity.get_component(MultiplayerComponent)

        # Host a game
        mp.host_game("MyRoom")

        # Or join a game
        mp.join_game("ws://192.168.1.10:8765", "PlayerName")

        # In on_update, pump the network
        mp.poll()

        # Check players
        for player in mp.get_players():
            print(player.name, player.is_ready)

        # Set ready
        mp.set_ready(True)

        # Start game (host only, when all ready)
        mp.start_game()

        # Send RPC to all players
        mp.rpc("take_damage", {"amount": 10})

        # Send RPC to specific player
        mp.rpc_to(player_id, "heal", {"amount": 5})

        # Send RPC to host only
        mp.rpc_to_host("request_spawn", {"prefab": "bullet"})

        # Send custom data
        mp.send_custom("chat", {"text": "Hello!"})

        # Listen for events (via global event system)
        self.subscribe_to_event("mp_player_joined", self.on_player_joined)
        self.subscribe_to_event("mp_player_left", self.on_player_left)
        self.subscribe_to_event("mp_game_started", self.on_game_started)
        self.subscribe_to_event("mp_rpc", self.on_rpc)
        self.subscribe_to_event("mp_custom", self.on_custom)
        self.subscribe_to_event("mp_state_sync", self.on_state_sync)
        self.subscribe_to_event("mp_disconnected", self.on_disconnected)
    """

    MODE_HOST = "host"
    MODE_CLIENT = "client"

    def __init__(
        self,
        player_name: str = "Player",
        max_players: int = 8,
        sync_rate: float = 20.0,
        port: int = 8765,
    ):
        self.entity = None
        self.player_name = str(player_name or "Player")
        self.max_players = max(2, int(max_players))
        self.sync_rate = max(1.0, float(sync_rate))
        self.port = max(1, min(65535, int(port)))

        # Runtime state (not serialized)
        self._mode: str = ""
        self._room: Room | None = None
        self._local_player_id: str = ""
        self._connected = False
        self._active = False
        self._sync_timer = 0.0
        self._sync_interval = 1.0 / self.sync_rate
        self._rpc_handlers: dict[str, callable] = {}
        self._pending_events: list[tuple] = []

    # ------------------------------------------------------------------
    # Public API — Connection
    # ------------------------------------------------------------------

    def host_game(self, room_name: str = "Room"):
        """Start hosting a multiplayer game. Sets up WebSocket server."""
        if self._active:
            return

        from core.components.websocket import WebSocketComponent
        ws = self._ensure_websocket()
        ws.mode = "server"
        ws.host = "0.0.0.0"
        ws.port = self.port
        ws.start()

        self._mode = self.MODE_HOST
        self._local_player_id = str(uuid.uuid4())
        self._room = Room(room_name=room_name, max_players=self.max_players)

        local_player = Player(
            player_id=self._local_player_id,
            name=self.player_name,
            client_id=0,
            is_host=True,
            is_local=True,
        )
        self._room.add_player(local_player)
        self._active = True
        self._connected = True
        self._emit("mp_connected", {"mode": "host"})

    def join_game(self, url: str, player_name: str = None):
        """Join a hosted game as a client."""
        if self._active:
            return

        if player_name:
            self.player_name = player_name

        from core.components.websocket import WebSocketComponent
        ws = self._ensure_websocket()
        ws.mode = "client"
        ws.url = url
        ws.start()

        self._mode = self.MODE_CLIENT
        self._local_player_id = str(uuid.uuid4())
        self._active = True

    def disconnect(self):
        """Disconnect from the multiplayer session."""
        if not self._active:
            return

        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent) if self.entity else None

        if ws and self._connected:
            msg = encode_message(MessageType.DISCONNECT, {
                "player_id": self._local_player_id
            }, self._local_player_id)
            ws.send(msg)

        if ws:
            ws.stop()

        self._active = False
        self._connected = False
        self._room = None
        self._mode = ""
        self._emit("mp_disconnected", {})

    # ------------------------------------------------------------------
    # Public API — Lobby
    # ------------------------------------------------------------------

    def set_ready(self, ready: bool = True):
        """Set local player's ready state."""
        if not self._active or not self._room:
            return
        local = self._room.get_player(self._local_player_id)
        if local:
            local.is_ready = ready
        msg = encode_message(MessageType.PLAYER_READY, {
            "player_id": self._local_player_id,
            "ready": ready,
        }, self._local_player_id)
        self._send(msg)

    def start_game(self):
        """Host only: Start the game if all players are ready."""
        if self._mode != self.MODE_HOST or not self._room:
            return
        if not self._room.all_ready():
            return
        self._room.started = True
        msg = encode_message(MessageType.GAME_START, {}, self._local_player_id)
        self._broadcast(msg)
        self._emit("mp_game_started", {})

    def kick_player(self, player_id: str):
        """Host only: Kick a player from the room."""
        if self._mode != self.MODE_HOST or not self._room:
            return
        player = self._room.remove_player(player_id)
        if not player:
            return
        msg = encode_message(MessageType.PLAYER_LEFT, {
            "player_id": player_id,
            "reason": "kicked",
        }, self._local_player_id)
        self._broadcast(msg)
        # Disconnect the client
        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent) if self.entity else None
        if ws and player.client_id:
            ws.send_to(player.client_id, encode_message(MessageType.DISCONNECT, {
                "reason": "kicked"
            }))

    # ------------------------------------------------------------------
    # Public API — Players
    # ------------------------------------------------------------------

    def get_players(self) -> list[Player]:
        """Return list of all players in the room."""
        if not self._room:
            return []
        return list(self._room.players.values())

    def get_player(self, player_id: str) -> Player | None:
        """Get a specific player by ID."""
        if not self._room:
            return None
        return self._room.get_player(player_id)

    def get_local_player(self) -> Player | None:
        """Get the local player."""
        if not self._room:
            return None
        return self._room.get_player(self._local_player_id)

    def get_player_count(self) -> int:
        return self._room.get_player_count() if self._room else 0

    @property
    def local_player_id(self) -> str:
        return self._local_player_id

    @property
    def is_host(self) -> bool:
        return self._mode == self.MODE_HOST

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def room(self) -> Room | None:
        return self._room

    # ------------------------------------------------------------------
    # Public API — RPC
    # ------------------------------------------------------------------

    def register_rpc(self, method_name: str, handler: callable):
        """Register an RPC handler function."""
        self._rpc_handlers[method_name] = handler

    def rpc(self, method: str, data: dict = None):
        """Send an RPC to all players (including self)."""
        msg = encode_message(MessageType.RPC_CALL, {
            "method": method,
            "args": data or {},
            "target": "all",
        }, self._local_player_id)
        self._broadcast(msg)
        # Also invoke locally
        self._handle_rpc(method, data or {}, self._local_player_id)

    def rpc_to(self, player_id: str, method: str, data: dict = None):
        """Send an RPC to a specific player."""
        payload = {
            "method": method,
            "args": data or {},
            "target": player_id,
        }
        if player_id == self._local_player_id:
            self._handle_rpc(method, data or {}, self._local_player_id)
            return
        msg = encode_message(MessageType.RPC_CALL, payload, self._local_player_id)
        if self._mode == self.MODE_HOST and self._room:
            player = self._room.get_player(player_id)
            if player and player.client_id:
                from core.components.websocket import WebSocketComponent
                ws = self.entity.get_component(WebSocketComponent) if self.entity else None
                if ws:
                    ws.send_to(player.client_id, msg)
        else:
            self._send(msg)

    def rpc_to_host(self, method: str, data: dict = None):
        """Send an RPC to the host."""
        if self._mode == self.MODE_HOST:
            self._handle_rpc(method, data or {}, self._local_player_id)
            return
        msg = encode_message(MessageType.RPC_CALL, {
            "method": method,
            "args": data or {},
            "target": "host",
        }, self._local_player_id)
        self._send(msg)

    # ------------------------------------------------------------------
    # Public API — Custom Messages & State
    # ------------------------------------------------------------------

    def send_custom(self, channel: str, data: dict = None):
        """Send a custom message to all players."""
        msg = encode_message(MessageType.CUSTOM, {
            "channel": channel,
            "payload": data or {},
        }, self._local_player_id)
        self._broadcast(msg)
        self._emit("mp_custom", {"channel": channel, "payload": data or {},
                                  "sender": self._local_player_id})

    def send_state(self, entity_net_id: str, state_data: dict):
        """Send entity state data (used by NetworkIdentityComponent)."""
        msg = encode_message(MessageType.STATE_UPDATE, {
            "net_id": entity_net_id,
            "state": state_data,
        }, self._local_player_id)
        self._broadcast(msg)

    def request_spawn(self, prefab_path: str, owner_id: str = "", data: dict = None):
        """Host only: Request spawning a networked entity."""
        if self._mode != self.MODE_HOST:
            self.rpc_to_host("_mp_spawn_request", {
                "prefab": prefab_path,
                "owner": owner_id or self._local_player_id,
                "data": data or {},
            })
            return
        net_id = str(uuid.uuid4())[:8]
        msg = encode_message(MessageType.SPAWN_ENTITY, {
            "net_id": net_id,
            "prefab": prefab_path,
            "owner": owner_id or self._local_player_id,
            "data": data or {},
        }, self._local_player_id)
        self._broadcast(msg)
        self._emit("mp_spawn", {
            "net_id": net_id,
            "prefab": prefab_path,
            "owner": owner_id or self._local_player_id,
            "data": data or {},
        })

    def request_despawn(self, entity_net_id: str):
        """Host only: Despawn a networked entity."""
        msg = encode_message(MessageType.DESPAWN_ENTITY, {
            "net_id": entity_net_id,
        }, self._local_player_id)
        self._broadcast(msg)
        self._emit("mp_despawn", {"net_id": entity_net_id})

    # ------------------------------------------------------------------
    # Poll — call every frame
    # ------------------------------------------------------------------

    def poll(self):
        """
        Process incoming WebSocket messages. Call this in on_update.
        Emits global events for game scripts to handle.
        """
        if not self._active or not self.entity:
            return

        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent)
        if not ws:
            return

        for sender, raw in ws.poll():
            if sender == "system":
                self._handle_system_event(raw)
                continue
            msg = decode_message(raw) if isinstance(raw, str) else None
            if not msg:
                continue
            self._handle_message(msg, sender)

    # ------------------------------------------------------------------
    # Internal — message handling
    # ------------------------------------------------------------------

    def _handle_system_event(self, event_data):
        """Handle WebSocket system events (connect/disconnect)."""
        if not isinstance(event_data, dict):
            return
        event = event_data.get("event", "")

        if event == "connected":
            if self._mode == self.MODE_CLIENT:
                self._connected = True
                msg = encode_message(MessageType.JOIN_REQUEST, {
                    "player_id": self._local_player_id,
                    "player_name": self.player_name,
                })
                self._send(msg)
                self._emit("mp_connected", {"mode": "client"})

        elif event == "disconnected":
            client_id = event_data.get("client_id", 0)
            if self._mode == self.MODE_HOST and client_id and self._room:
                player = self._room.get_player_by_client(client_id)
                if player:
                    self._room.remove_player(player.id)
                    leave_msg = encode_message(MessageType.PLAYER_LEFT, {
                        "player_id": player.id,
                        "reason": "disconnected",
                    }, self._local_player_id)
                    self._broadcast(leave_msg)
                    self._emit("mp_player_left", {"player": player.to_dict(), "reason": "disconnected"})
            elif self._mode == self.MODE_CLIENT:
                self._connected = False
                self._emit("mp_disconnected", {"reason": event_data.get("reason", "")})

    def _handle_message(self, msg: dict, sender):
        """Route a decoded multiplayer message."""
        msg_type = msg["type"]
        data = msg["data"]
        sender_id = msg.get("sender", "")

        if msg_type == MessageType.JOIN_REQUEST:
            self._on_join_request(data, sender)
        elif msg_type == MessageType.JOIN_ACCEPTED:
            self._on_join_accepted(data)
        elif msg_type == MessageType.JOIN_REJECTED:
            self._emit("mp_join_rejected", data)
        elif msg_type == MessageType.PLAYER_JOINED:
            self._on_player_joined(data)
        elif msg_type == MessageType.PLAYER_LEFT:
            self._on_player_left(data)
        elif msg_type == MessageType.LOBBY_STATE:
            self._on_lobby_state(data)
        elif msg_type == MessageType.PLAYER_READY:
            self._on_player_ready(data)
        elif msg_type == MessageType.GAME_START:
            if self._room:
                self._room.started = True
            self._emit("mp_game_started", data)
        elif msg_type == MessageType.STATE_UPDATE:
            self._emit("mp_state_sync", data)
        elif msg_type == MessageType.SPAWN_ENTITY:
            self._emit("mp_spawn", data)
        elif msg_type == MessageType.DESPAWN_ENTITY:
            self._emit("mp_despawn", data)
        elif msg_type == MessageType.RPC_CALL:
            self._on_rpc_call(data, sender_id, sender)
        elif msg_type == MessageType.CUSTOM:
            self._emit("mp_custom", {
                "channel": data.get("channel", ""),
                "payload": data.get("payload", {}),
                "sender": sender_id,
            })
        elif msg_type == MessageType.PING:
            pong = encode_message(MessageType.PONG, {"ts": data.get("ts", 0)}, self._local_player_id)
            self._send(pong)
        elif msg_type == MessageType.PONG:
            if self._room:
                player = self._room.get_player(sender_id)
                if player:
                    player.latency_ms = (time.time() - data.get("ts", 0)) * 1000
        elif msg_type == MessageType.DISCONNECT:
            pass  # handled by system events

    # ------------------------------------------------------------------
    # Internal — specific handlers
    # ------------------------------------------------------------------

    def _on_join_request(self, data: dict, client_sender):
        """Host: handle a client's join request."""
        if self._mode != self.MODE_HOST or not self._room:
            return

        player_id = data.get("player_id", "")
        player_name = data.get("player_name", "Player")
        client_id = client_sender if isinstance(client_sender, int) else 0

        if self._room.is_full():
            reject = encode_message(MessageType.JOIN_REJECTED, {"reason": "Room is full"})
            from core.components.websocket import WebSocketComponent
            ws = self.entity.get_component(WebSocketComponent) if self.entity else None
            if ws and client_id:
                ws.send_to(client_id, reject)
            return

        new_player = Player(
            player_id=player_id,
            name=player_name,
            client_id=client_id,
            is_host=False,
        )
        self._room.add_player(new_player)

        # Send accept + full room state to the new client
        accept = encode_message(MessageType.JOIN_ACCEPTED, {
            "player_id": player_id,
            "room": self._room.to_dict(),
        })
        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent) if self.entity else None
        if ws and client_id:
            ws.send_to(client_id, accept)

        # Broadcast to all other clients
        joined_msg = encode_message(MessageType.PLAYER_JOINED, {
            "player": new_player.to_dict(),
        }, self._local_player_id)
        self._broadcast(joined_msg, exclude_client=client_id)

        self._emit("mp_player_joined", {"player": new_player.to_dict()})

    def _on_join_accepted(self, data: dict):
        """Client: handle join acceptance from host."""
        self._connected = True
        room_data = data.get("room", {})
        self._room = Room.from_dict(room_data)
        # Mark local player
        local = self._room.get_player(self._local_player_id)
        if local:
            local.is_local = True
        self._emit("mp_joined", {"room": room_data})

    def _on_player_joined(self, data: dict):
        """Handle a new player joining."""
        pdata = data.get("player", {})
        if not self._room:
            return
        player = Player.from_dict(pdata)
        self._room.add_player(player)
        self._emit("mp_player_joined", {"player": pdata})

    def _on_player_left(self, data: dict):
        """Handle a player leaving."""
        player_id = data.get("player_id", "")
        reason = data.get("reason", "")
        if self._room:
            player = self._room.remove_player(player_id)
            if player:
                self._emit("mp_player_left", {"player": player.to_dict(), "reason": reason})

    def _on_lobby_state(self, data: dict):
        """Client: receive full lobby state update."""
        room_data = data.get("room", {})
        if room_data:
            self._room = Room.from_dict(room_data)
            local = self._room.get_player(self._local_player_id)
            if local:
                local.is_local = True
        self._emit("mp_lobby_state", {"room": room_data})

    def _on_player_ready(self, data: dict):
        """Handle player ready state change."""
        player_id = data.get("player_id", "")
        ready = data.get("ready", False)
        if self._room:
            player = self._room.get_player(player_id)
            if player:
                player.is_ready = ready

        # Host relays to all
        if self._mode == self.MODE_HOST:
            relay = encode_message(MessageType.PLAYER_READY, data, self._local_player_id)
            self._broadcast(relay)

        self._emit("mp_player_ready", {"player_id": player_id, "ready": ready})

    def _on_rpc_call(self, data: dict, sender_id: str, raw_sender):
        """Handle an incoming RPC call."""
        method = data.get("method", "")
        args = data.get("args", {})
        target = data.get("target", "all")

        # Host relays RPCs to appropriate targets
        if self._mode == self.MODE_HOST and target == "all":
            relay = encode_message(MessageType.RPC_CALL, data, sender_id)
            exclude = raw_sender if isinstance(raw_sender, int) else 0
            self._broadcast(relay, exclude_client=exclude)

        # Check if this RPC is for us
        if target == "all" or target == self._local_player_id or \
           (target == "host" and self._mode == self.MODE_HOST):
            self._handle_rpc(method, args, sender_id)

    def _handle_rpc(self, method: str, args: dict, sender_id: str):
        """Invoke a registered RPC handler or emit an event."""
        handler = self._rpc_handlers.get(method)
        if handler:
            try:
                handler(sender_id, args)
            except Exception as e:
                _mp_logger.error("RPC handler error", method=method, error=str(e))
        self._emit("mp_rpc", {"method": method, "args": args, "sender": sender_id})

    # ------------------------------------------------------------------
    # Internal — transport helpers
    # ------------------------------------------------------------------

    def _ensure_websocket(self):
        """Get or create a WebSocketComponent on this entity."""
        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent) if self.entity else None
        if not ws and self.entity:
            ws = WebSocketComponent()
            self.entity.add_component(ws)
        return ws

    def _send(self, msg: str):
        """Send a message (client sends to server, host broadcasts)."""
        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent) if self.entity else None
        if ws:
            ws.send(msg)

    def _broadcast(self, msg: str, exclude_client: int = 0):
        """Host: broadcast to all connected clients (optionally excluding one)."""
        from core.components.websocket import WebSocketComponent
        ws = self.entity.get_component(WebSocketComponent) if self.entity else None
        if not ws:
            return
        if self._mode == self.MODE_HOST:
            for cid in ws.get_client_ids():
                if cid != exclude_client:
                    ws.send_to(cid, msg)
        else:
            ws.send(msg)

    def _emit(self, event_name: str, data: dict):
        """Emit a global event through the entity's world event system."""
        if self.entity and self.entity.world:
            self.entity.world.events.emit(event_name, data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_destroy(self):
        self.disconnect()
