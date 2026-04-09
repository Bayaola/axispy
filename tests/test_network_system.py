import pytest
from unittest.mock import MagicMock, patch
from core.ecs import World
from core.components.websocket import WebSocketComponent
from core.components.http_request import HTTPRequestComponent
from core.components.webview import WebviewComponent
from core.components.webrtc import WebRTCComponent
from core.components.multiplayer import MultiplayerComponent
from core.components.network_identity import NetworkIdentityComponent
from core.systems.network_system import NetworkSystem


@pytest.fixture
def network_world():
    world = World()
    world.add_system(NetworkSystem())
    return world


# ---------------------------------------------------------------------------
# NetworkSystem integration tests
# ---------------------------------------------------------------------------

class TestNetworkSystemWebSocket:
    def test_autostart_websocket(self, network_world):
        entity = network_world.create_entity("WS")
        ws = WebSocketComponent.__new__(WebSocketComponent)
        ws.entity = None
        ws.autostart = True
        ws._autostart_handled = False
        ws.start = MagicMock()
        entity.components[WebSocketComponent] = ws
        ws.entity = entity
        network_world._component_cache.setdefault(WebSocketComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        ws.start.assert_called_once()
        assert ws._autostart_handled is True

    def test_autostart_not_repeated(self, network_world):
        entity = network_world.create_entity("WS")
        ws = WebSocketComponent.__new__(WebSocketComponent)
        ws.entity = None
        ws.autostart = True
        ws._autostart_handled = True  # Already handled
        ws.start = MagicMock()
        entity.components[WebSocketComponent] = ws
        ws.entity = entity
        network_world._component_cache.setdefault(WebSocketComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        ws.start.assert_not_called()


class TestNetworkSystemHTTP:
    def test_send_on_start(self, network_world):
        entity = network_world.create_entity("HTTP")
        req = HTTPRequestComponent.__new__(HTTPRequestComponent)
        req.entity = None
        req.send_on_start = True
        req._send_on_start_handled = False
        req.url = "http://example.com"
        req.send = MagicMock()
        entity.components[HTTPRequestComponent] = req
        req.entity = entity
        network_world._component_cache.setdefault(HTTPRequestComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        req.send.assert_called_once()

    def test_send_on_start_no_url(self, network_world):
        entity = network_world.create_entity("HTTP")
        req = HTTPRequestComponent.__new__(HTTPRequestComponent)
        req.entity = None
        req.send_on_start = True
        req._send_on_start_handled = False
        req.url = ""
        req.send = MagicMock()
        entity.components[HTTPRequestComponent] = req
        req.entity = entity
        network_world._component_cache.setdefault(HTTPRequestComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        req.send.assert_not_called()


class TestNetworkSystemWebview:
    def test_autoopen_webview(self, network_world):
        entity = network_world.create_entity("WV")
        wv = WebviewComponent.__new__(WebviewComponent)
        wv.entity = None
        wv.autoopen = True
        wv._autoopen_handled = False
        wv.open = MagicMock()
        entity.components[WebviewComponent] = wv
        wv.entity = entity
        network_world._component_cache.setdefault(WebviewComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        wv.open.assert_called_once()


class TestNetworkSystemWebRTC:
    def test_autostart_webrtc(self, network_world):
        entity = network_world.create_entity("RTC")
        rtc = WebRTCComponent.__new__(WebRTCComponent)
        rtc.entity = None
        rtc.autostart = True
        rtc._autostart_handled = False
        rtc.start = MagicMock()
        entity.components[WebRTCComponent] = rtc
        rtc.entity = entity
        network_world._component_cache.setdefault(WebRTCComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        rtc.start.assert_called_once()


class TestNetworkSystemMultiplayer:
    def test_multiplayer_poll(self, network_world):
        entity = network_world.create_entity("MP")
        mp = MultiplayerComponent.__new__(MultiplayerComponent)
        mp.entity = None
        mp._active = True
        mp.poll = MagicMock()
        entity.components[MultiplayerComponent] = mp
        mp.entity = entity
        network_world._component_cache.setdefault(MultiplayerComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        mp.poll.assert_called_once()

    def test_multiplayer_inactive_not_polled(self, network_world):
        entity = network_world.create_entity("MP")
        mp = MultiplayerComponent.__new__(MultiplayerComponent)
        mp.entity = None
        mp._active = False
        mp.poll = MagicMock()
        entity.components[MultiplayerComponent] = mp
        mp.entity = entity
        network_world._component_cache.setdefault(MultiplayerComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        mp.poll.assert_not_called()


class TestNetworkSystemNetworkIdentity:
    def test_network_identity_sync(self, network_world):
        entity = network_world.create_entity("NI")
        nid = NetworkIdentityComponent.__new__(NetworkIdentityComponent)
        nid.entity = None
        nid.network_id = "abc123"
        nid.update_sync = MagicMock()
        entity.components[NetworkIdentityComponent] = nid
        nid.entity = entity
        network_world._component_cache.setdefault(NetworkIdentityComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        nid.update_sync.assert_called_once_with(0.016)

    def test_network_identity_no_id_skipped(self, network_world):
        entity = network_world.create_entity("NI")
        nid = NetworkIdentityComponent.__new__(NetworkIdentityComponent)
        nid.entity = None
        nid.network_id = ""
        nid.update_sync = MagicMock()
        entity.components[NetworkIdentityComponent] = nid
        nid.entity = entity
        network_world._component_cache.setdefault(NetworkIdentityComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns.update(0.016, network_world.entities)
        nid.update_sync.assert_not_called()


class TestNetworkSystemStateSyncCallback:
    def test_on_state_sync_routes_to_entity(self, network_world):
        entity = network_world.create_entity("NI")
        nid = NetworkIdentityComponent.__new__(NetworkIdentityComponent)
        nid.entity = None
        nid.network_id = "target_id"
        nid.receive_state = MagicMock()
        entity.components[NetworkIdentityComponent] = nid
        nid.entity = entity
        network_world._component_cache.setdefault(NetworkIdentityComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns._on_state_sync({"net_id": "target_id", "state": {"x": 10}})
        nid.receive_state.assert_called_once_with({"x": 10})

    def test_on_state_sync_no_match(self, network_world):
        entity = network_world.create_entity("NI")
        nid = NetworkIdentityComponent.__new__(NetworkIdentityComponent)
        nid.entity = None
        nid.network_id = "other_id"
        nid.receive_state = MagicMock()
        entity.components[NetworkIdentityComponent] = nid
        nid.entity = entity
        network_world._component_cache.setdefault(NetworkIdentityComponent, set()).add(entity)
        ns = network_world.get_system(NetworkSystem)
        ns._on_state_sync({"net_id": "no_match", "state": {"x": 10}})
        nid.receive_state.assert_not_called()

    def test_on_state_sync_no_world(self):
        ns = NetworkSystem()
        ns._on_state_sync({"net_id": "x", "state": {"a": 1}})  # Should not crash


class TestNetworkSystemGeneral:
    def test_required_components(self):
        ns = NetworkSystem()
        assert WebSocketComponent in ns.required_components
        assert HTTPRequestComponent in ns.required_components
        assert MultiplayerComponent in ns.required_components
