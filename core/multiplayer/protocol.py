"""
Multiplayer protocol definitions.
Defines message types and serialization for network communication.
"""
import json
import time


class MessageType:
    # Connection
    JOIN_REQUEST = "join_request"
    JOIN_ACCEPTED = "join_accepted"
    JOIN_REJECTED = "join_rejected"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    DISCONNECT = "disconnect"

    # Lobby
    LOBBY_STATE = "lobby_state"
    PLAYER_READY = "player_ready"
    GAME_START = "game_start"

    # State sync
    STATE_SYNC = "state_sync"
    STATE_UPDATE = "state_update"
    SPAWN_ENTITY = "spawn_entity"
    DESPAWN_ENTITY = "despawn_entity"
    OWNERSHIP_TRANSFER = "ownership_transfer"

    # RPC
    RPC_CALL = "rpc_call"

    # Ping
    PING = "ping"
    PONG = "pong"

    # Custom
    CUSTOM = "custom"


def encode_message(msg_type: str, data: dict = None, sender_id: str = "") -> str:
    """Encode a multiplayer message to JSON string."""
    msg = {
        "t": msg_type,
        "ts": time.time(),
    }
    if sender_id:
        msg["from"] = sender_id
    if data:
        msg["d"] = data
    return json.dumps(msg, separators=(",", ":"))


def decode_message(raw: str) -> dict | None:
    """Decode a JSON string to a multiplayer message dict."""
    try:
        msg = json.loads(raw)
        return {
            "type": msg.get("t", ""),
            "timestamp": msg.get("ts", 0),
            "sender": msg.get("from", ""),
            "data": msg.get("d", {}),
        }
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None
