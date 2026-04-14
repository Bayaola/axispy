Networking Tutorial
===================

This tutorial introduces AxisPy's networking stack: WebSockets for transport, a high-level Multiplayer manager with lobby/RPC/state sync, peer-to-peer WebRTC data channels, and HTTP utilities. All network I/O runs off the main thread; you consume events by polling components or subscribing to world events.

.. contents:: On this page
   :local:
   :depth: 2

Overview
--------

AxisPy provides component-based networking that integrates with the ECS and the global event system.

- :class:`~core.components.websocket.WebSocketComponent` — client/server WebSocket transport with inbox polling.
- :class:`~core.components.multiplayer.MultiplayerComponent` — high-level multiplayer room, players, RPC, spawn/state sync (uses WebSocket under the hood).
- :class:`~core.components.network_identity.NetworkIdentityComponent` — marks entities for network replication with ownership and synced vars.
- :class:`~core.components.webrtc.WebRTCComponent` — peer-to-peer data channels (requires a signaling channel like WebSocket).
- :class:`~core.components.http_client.HTTPClientComponent` and :class:`~core.components.http_request.HTTPRequestComponent` — async HTTP utilities.

The :class:`~core.systems.network_system.NetworkSystem` is added by the runtime player and will:

- Autostart components with their auto flags (e.g. WebSocket `autostart`, WebRTC `autostart`, HTTPRequest `send_on_start`).
- Call :meth:`~core.components.multiplayer.MultiplayerComponent.poll` each frame.
- Route ``mp_state_sync`` events to matching :class:`~core.components.network_identity.NetworkIdentityComponent`.

Editor workflow (no code)
-------------------------

- **Add networking components (Inspector)**
  - Select an entity → Add Component → Network → choose the component:
    - ``WebSocket`` — transport layer (client/server modes).
    - ``Multiplayer`` — high-level lobby/RPC/spawn management.
    - ``Network Identity`` — marks entities for replication with ownership.
    - ``WebRTC`` — peer-to-peer data channels.
    - ``HTTP Client`` — persistent HTTP client with base URL.
    - ``HTTP Request`` — one-shot HTTP request component.

- **Configure WebSocket**
  - ``Mode``: client or server.
  - ``Host`` / ``Port``: bind address for server; target for client.
  - ``URL``: optional full URL override (e.g., ``ws://host:port/path``).
  - ``Autostart``: begins connection automatically when the entity enters the world.
  - ``Max Queue Size``: inbox message buffer limit.

- **Configure Multiplayer**
  - ``Player Name``: local player display name.
  - ``Max Players``: lobby capacity (2–64).
  - ``Sync Rate``: network update frequency in Hz.
  - ``Port``: server listen port when hosting.
  - Scripts handle ``host_game(room)`` / ``join_game(url, name)``; see snippets below.

- **Configure Network Identity**
  - ``Network ID`` / ``Owner ID``: usually auto-assigned by the host at runtime.
  - ``Sync Interval``: seconds between state updates.
  - ``Sync Transform``: replicate position/rotation automatically.
  - ``Interpolate``: smooth remote updates.
  - Use ``nid.is_mine()`` in scripts to check ownership before authoring movement.

- **Configure WebRTC**
  - ``ICE Servers``: comma-separated STUN/TURN servers.
  - ``Channel Label``: data channel name.
  - ``Ordered`` / ``Max Retransmits``: reliability settings.
  - ``Autostart``: initiate peer connection automatically.

- **Configure HTTP**
  - ``HTTP Client``: set ``Base URL``, ``Timeout``, and ``Max Concurrent`` requests.
  - ``HTTP Request``: set ``URL``, ``Method`` (GET/POST/PUT/DELETE/PATCH), ``Request Body``, ``Content Type``, ``Timeout``, and ``Send on Start`` to fire automatically.

- **Testing networking**
  - Enter Play Mode; components with ``Autostart`` connect automatically.
  - Use the Console dock to view logs from ``self.logger.info()``.
  - Monitor connection events via subscribed world events (e.g., ``mp_connected``, ``mp_disconnected``).

WebSocket Basics
----------------

Client/server WebSocket with an inbox you drain each frame.

.. code-block:: python

   from core.components.websocket import WebSocketComponent

   class NetConsole:
       def on_start(self):
           ws = self.entity.get_component(WebSocketComponent)
           if not ws:
               ws = WebSocketComponent(mode="server", host="0.0.0.0", port=8765)
               self.entity.add_component(ws)
           ws.start()

       def on_update(self, dt: float):
           ws = self.entity.get_component(WebSocketComponent)
           if not ws or not ws.is_running():
               return
           for sender, msg in ws.poll():
               if sender == "system":
                   self.logger.info("WS event", event=msg)
               else:
                   self.logger.info("WS message", sender=sender, msg=msg)
           # Send/broadcast
           # ws.send("Hello")
           # ws.broadcast("Server says hi")

- Server mode: set ``mode="server"``; use ``broadcast`` and ``send_to(client_id, msg)``.
- Client mode: set ``mode="client"`` or just provide a ``url``; use ``send``.
- System messages come via ``sender == "system"`` (connected/disconnected, etc.).

Multiplayer Quickstart (Lobby, Players, RPC)
--------------------------------------------

Attach :class:`~core.components.multiplayer.MultiplayerComponent` to a manager entity. It will ensure a :class:`~core.components.websocket.WebSocketComponent` exists on the same entity and use it for transport.

.. code-block:: python

   from core.components.multiplayer import MultiplayerComponent

   class MultiplayerSetup:
       def on_start(self):
           self.mp = self.entity.get_component(MultiplayerComponent)
           if not self.mp:
               self.mp = MultiplayerComponent(player_name="Player1", max_players=8)
               self.entity.add_component(self.mp)

           # Host or join
           # self.mp.host_game("MyRoom")
           # or
           # self.mp.join_game("ws://127.0.0.1:8765", player_name="Alice")

           # Subscribe to multiplayer events (global world events)
           self.subscribe_to_event("mp_connected", self._on_connected)
           self.subscribe_to_event("mp_joined", self._on_joined)
           self.subscribe_to_event("mp_player_joined", self._on_player_joined)
           self.subscribe_to_event("mp_game_started", self._on_game_started)
           self.subscribe_to_event("mp_disconnected", self._on_disconnected)

           # Register an RPC handler
           self.mp.register_rpc("take_damage", self._rpc_take_damage)

       # -- Event handlers --
       def _on_connected(self, data):
           self.logger.info("Connected", mode=data.get("mode"))

       def _on_joined(self, data):
           room = data.get("room", {})
           self.logger.info("Joined room", players=len(room.get("players", {})))

       def _on_player_joined(self, data):
           p = data.get("player", {})
           self.logger.info("Player joined", name=p.get("name"))

       def _on_game_started(self, data):
           self.logger.info("Game started")

       def _on_disconnected(self, data):
           self.logger.warning("Disconnected", reason=data.get("reason", ""))

       # -- RPC example --
       def _rpc_take_damage(self, sender_id: str, args: dict):
           amount = int(args.get("amount", 0))
           self.logger.info("RPC: take_damage", from_player=sender_id, amount=amount)

       def on_update(self, dt: float):
           # When running with RuntimePlayer, NetworkSystem already calls mp.poll().
           # If you embed AxisPy differently and don't use NetworkSystem, uncomment below:
           # if self.mp and self.mp.is_active:
           #     self.mp.poll()
           pass

Lobby and Player APIs
---------------------

.. code-block:: python

   mp = self.entity.get_component(MultiplayerComponent)
   mp.set_ready(True)
   # Host-only, starts when all players are ready
   mp.start_game()

   for player in mp.get_players():
       self.logger.info("Player", id=player.id, name=player.name, ready=player.is_ready)

Remote Procedure Calls (RPC)
----------------------------

- Register: ``mp.register_rpc(method_name, handler)`` where handler is ``handler(sender_id: str, args: dict)``.
- Call all: ``mp.rpc("method", { ... })`` (broadcast, also invoked locally).
- Call specific: ``mp.rpc_to(player_id, "method", { ... })``.
- Call host: ``mp.rpc_to_host("method", { ... })``.

Custom Channels
---------------

Send arbitrary channel payloads and handle them via events.

.. code-block:: python

   mp.send_custom("chat", {"text": "Hello!"})
   # Listen via: self.subscribe_to_event("mp_custom", self._on_custom)
   # data: {"channel": "chat", "payload": {...}, "sender": "<player_id>"}

Networked Entities and State Sync
---------------------------------

Use :class:`~core.components.network_identity.NetworkIdentityComponent` on entities that should replicate.

- Ownership: ``net_id.is_mine()`` determines who can author state locally.
- Transform: if ``sync_transform`` is True, x/y/rotation are replicated.
- Variables: ``set_var(key, value)`` marks vars as dirty and they replicate; read with ``get_var``.

Spawning on the Host and Applying on Clients
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from core.components.network_identity import NetworkIdentityComponent
   from core.components.multiplayer import MultiplayerComponent

   class Spawner:
       def on_start(self):
           # Host requests a spawn that all clients will receive
           mp = self.find("GameManager").get_component(MultiplayerComponent)
           if mp and mp.is_host:
               mp.request_spawn("prefabs/enemy.json", owner_id=mp.local_player_id, data={"hp": 100})
           # Listen once for spawn events
           self.subscribe_to_event("mp_spawn", self._on_spawn)

       def on_update(self, dt: float):
           pass

       def _on_spawn(self, data: dict):
           spawned = self.spawn_prefab(data.get("prefab", ""))
           if not spawned:
               return
           nid = spawned.get_component(NetworkIdentityComponent)
           if not nid:
               nid = NetworkIdentityComponent()
               spawned.add_component(nid)
           nid.network_id = data.get("net_id", "")
           nid.owner_id = data.get("owner", "")
           # Initialize synced vars if any
           for k, v in (data.get("data", {}) or {}).items():
               nid.set_var(k, v)

Authoritative Updates
~~~~~~~~~~~~~~~~~~~~~

Author only moves local entities; remote state is applied automatically when received.

.. code-block:: python

   from core.components import Transform
   from core.components.network_identity import NetworkIdentityComponent

   class NetMover:
       SPEED = 200
       def on_update(self, dt: float):
           nid = self.entity.get_component(NetworkIdentityComponent)
           if not nid or not nid.is_mine():
               return
           t = self.entity.get_component(Transform)
           if t:
               t.x += self.SPEED * dt
               # Optional custom var
               nid.set_var("energy", 75)

WebRTC Data Channels (Advanced)
-------------------------------

Use WebRTC for peer-to-peer messaging. You need a signaling path (e.g. your WebSocket) to exchange SDP offers/answers and ICE candidates.

.. code-block:: python

   from core.components.webrtc import WebRTCComponent
   from core.components.websocket import WebSocketComponent

   class P2P:
       def on_start(self):
           import json
           self.rtc = self.entity.get_component(WebRTCComponent) or WebRTCComponent(autostart=True)
           self.ws = self.entity.get_component(WebSocketComponent) or WebSocketComponent(mode="client", url="ws://127.0.0.1:8765")
           if not self.entity.get_component(WebRTCComponent):
               self.entity.add_component(self.rtc)
           if not self.entity.get_component(WebSocketComponent):
               self.entity.add_component(self.ws)
           self.rtc.start()
           self.ws.start()
           # Caller side would typically do:
           # self.rtc.create_offer()

       def on_update(self, dt: float):
           # Send local signaling out via WebSocket
           for sender, msg in self.rtc.poll():
               if sender == "local":
                   # Wrap for app-level routing
                   self.ws.send_json({"type": "webrtc", "payload": msg})
               elif sender == "datachannel":
                   self.logger.info("P2P message", data=msg)

           # Receive signaling from WebSocket and feed into RTC
           for sender, raw in self.ws.poll():
               if sender != "server":
                   continue
               try:
                   data = json.loads(raw)
               except Exception:
                   continue
               if data.get("type") != "webrtc":
                   continue
               payload = data.get("payload", {})
               t = payload.get("type")
               if t in ("offer", "answer"):
                   self.rtc.set_remote_description(payload)
               elif t == "candidate":
                   self.rtc.add_ice_candidate(payload)

HTTP Utilities
--------------

One-off request with :class:`~core.components.http_request.HTTPRequestComponent`:

.. code-block:: python

   from core.components.http_request import HTTPRequestComponent

   class Fetcher:
       def on_start(self):
           req = self.entity.get_component(HTTPRequestComponent) or HTTPRequestComponent()
           if not self.entity.get_component(HTTPRequestComponent):
               self.entity.add_component(req)
           req.url = "https://api.example.com/data"
           req.method = HTTPRequestComponent.METHOD_GET
           req.send()

       def on_update(self, dt: float):
           req = self.entity.get_component(HTTPRequestComponent)
           if req and req.is_done():
               if req.ok:
                   self.logger.info("Fetched", data=req.json())
               else:
                   self.logger.error("HTTP error", status=req.status_code, err=req.error)

Or a persistent client with :class:`~core.components.http_client.HTTPClientComponent`:

.. code-block:: python

   from core.components.http_client import HTTPClientComponent

   class ApiClient:
       def on_start(self):
           http = self.entity.get_component(HTTPClientComponent) or HTTPClientComponent(base_url="https://api.example.com")
           if not self.entity.get_component(HTTPClientComponent):
               self.entity.add_component(http)
           http.get("/status", tag="status")
           http.post("/submit", body={"value": 123}, tag="submit")

       def on_update(self, dt: float):
           http = self.entity.get_component(HTTPClientComponent)
           if not http:
               return
           for resp in http.poll():
               if resp.ok:
                   self.logger.info("HTTP ok", tag=resp.tag, data=resp.json())
               else:
                   self.logger.error("HTTP fail", tag=resp.tag, code=resp.status_code, err=resp.error)

Script Editor snippets you may need
-----------------------------------

- **Quick HTTP GET with one-shot component**

.. code-block:: python

   from core.components.http_request import HTTPRequestComponent

   class QuickFetch:
       def on_start(self):
           req = self.entity.get_component(HTTPRequestComponent)
           if not req:
               req = HTTPRequestComponent()
               self.entity.add_component(req)
           req.url = "https://api.example.com/status"
           req.method = HTTPRequestComponent.METHOD_GET
           req.send_on_start = True
           req.send()

       def on_update(self, dt: float):
           req = self.entity.get_component(HTTPRequestComponent)
           if req and req.is_done():
               if req.ok:
                   self.logger.info("status", data=req.json())
               else:
                   self.logger.error("fetch failed", status=req.status_code)
               req.clear()  # reset to allow re-trigger

- **Send a reliable RPC when a key is pressed**

.. code-block:: python

   import pygame
   from core.input import Input
   from core.components.multiplayer import MultiplayerComponent

   class ChatSender:
       def on_start(self):
           self.mp = self.entity.get_component(MultiplayerComponent)
           if self.mp:
               self.mp.register_rpc("chat", self._on_chat)

       def _on_chat(self, sender_id: str, args: dict):
           self.logger.info("chat", from_player=sender_id, msg=args.get("text"))

       def on_update(self, dt: float):
           if not self.mp:
               return
           if Input.get_key_down(pygame.K_RETURN):
               self.mp.rpc("chat", {"text": "Hello from " + self.mp.player_name})

- **Host or join from a script**

.. code-block:: python

   import pygame
   from core.input import Input
   from core.components.multiplayer import MultiplayerComponent

   class QuickLobby:
       def on_start(self):
           self.mp = self.entity.get_component(MultiplayerComponent)
           if not self.mp:
               return
           # Example: H to host, J to join localhost
           self.subscribe_to_event("mp_connected", lambda d: self.logger.info("connected", mode=d.get("mode")))
           self.subscribe_to_event("mp_disconnected", lambda d: self.logger.warning("disconnected"))

       def on_update(self, dt: float):
           if not self.mp:
               return
           if Input.get_key_down(pygame.K_h):
               self.mp.host_game("MyRoom")
               self.logger.info("hosting")
           if Input.get_key_down(pygame.K_j):
               self.mp.join_game("ws://127.0.0.1:8765", player_name="Client")
               self.logger.info("joining")

- **Check ownership and move a networked entity**

.. code-block:: python

   from core.components import Transform
   from core.components.network_identity import NetworkIdentityComponent
   from core.input import Input
   import pygame

   class NetMove:
       SPEED = 200
       def on_update(self, dt: float):
           nid = self.entity.get_component(NetworkIdentityComponent)
           if not nid or not nid.is_mine():
               return
           t = self.entity.get_component(Transform)
           if not t:
               return
           dx = (Input.get_key(pygame.K_d) - Input.get_key(pygame.K_a))
           dy = (Input.get_key(pygame.K_s) - Input.get_key(pygame.K_w))
           t.x += dx * self.SPEED * dt
           t.y += dy * self.SPEED * dt
           # Optional: mark a custom var dirty so it replicates
           nid.set_var("input_dir", {"x": dx, "y": dy})
