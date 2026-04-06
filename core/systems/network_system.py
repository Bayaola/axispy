from core.ecs import System, Entity
from core.components.websocket import WebSocketComponent
from core.components.http_request import HTTPRequestComponent
from core.components.webview import WebviewComponent
from core.components.webrtc import WebRTCComponent
from core.components.multiplayer import MultiplayerComponent
from core.components.network_identity import NetworkIdentityComponent


class NetworkSystem(System):
    """Handles autostart for network components and multiplayer sync."""
    required_components = (WebSocketComponent, HTTPRequestComponent, WebviewComponent,
                           WebRTCComponent, MultiplayerComponent, NetworkIdentityComponent)

    def __init__(self):
        super().__init__()
        self._state_sync_subscribed = False

    def _query(self, component_type, entities: list[Entity]) -> list[Entity]:
        if self.world:
            return self.world.get_entities_with(component_type)
        return [e for e in entities if e.get_component(component_type)]

    def update(self, dt: float, entities: list[Entity]):
        for entity in self._query(WebSocketComponent, entities):
            ws = entity.get_component(WebSocketComponent)
            if ws and ws.autostart and not ws._autostart_handled:
                ws._autostart_handled = True
                ws.start()

        for entity in self._query(HTTPRequestComponent, entities):
            req = entity.get_component(HTTPRequestComponent)
            if req and req.send_on_start and not req._send_on_start_handled:
                req._send_on_start_handled = True
                if req.url:
                    req.send()

        for entity in self._query(WebviewComponent, entities):
            wv = entity.get_component(WebviewComponent)
            if wv and wv.autoopen and not wv._autoopen_handled:
                wv._autoopen_handled = True
                wv.open()

        for entity in self._query(WebRTCComponent, entities):
            rtc = entity.get_component(WebRTCComponent)
            if rtc and rtc.autostart and not rtc._autostart_handled:
                rtc._autostart_handled = True
                rtc.start()

        # Multiplayer polling
        for entity in self._query(MultiplayerComponent, entities):
            mp = entity.get_component(MultiplayerComponent)
            if mp and mp.is_active:
                mp.poll()
                # Subscribe to state sync events once
                if not self._state_sync_subscribed and self.world:
                    self.world.events.subscribe("mp_state_sync", self._on_state_sync)
                    self._state_sync_subscribed = True

        # NetworkIdentity sync
        for entity in self._query(NetworkIdentityComponent, entities):
            net_id = entity.get_component(NetworkIdentityComponent)
            if net_id and net_id.network_id:
                net_id.update_sync(dt)

    def _on_state_sync(self, data: dict):
        """Route incoming state updates to the correct NetworkIdentityComponent."""
        if not self.world:
            return
        net_id_str = data.get("net_id", "")
        state = data.get("state", {})
        if not net_id_str or not state:
            return
        for entity in self.world.entities:
            nid = entity.get_component(NetworkIdentityComponent)
            if nid and nid.network_id == net_id_str:
                nid.receive_state(state)
                break
