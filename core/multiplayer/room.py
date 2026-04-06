"""
Room and Player management for multiplayer sessions.
"""
import time


class Player:
    """Represents a connected player in a multiplayer session."""
    __slots__ = ("id", "name", "client_id", "is_host", "is_ready", "is_local",
                 "latency_ms", "custom_data", "_last_ping_time")

    def __init__(self, player_id: str = "", name: str = "Player", client_id: int = 0,
                 is_host: bool = False, is_local: bool = False):
        self.id = player_id
        self.name = name
        self.client_id = client_id
        self.is_host = is_host
        self.is_ready = False
        self.is_local = is_local
        self.latency_ms = 0.0
        self.custom_data: dict = {}
        self._last_ping_time = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "client_id": self.client_id,
            "is_host": self.is_host,
            "is_ready": self.is_ready,
            "custom_data": self.custom_data,
        }

    @staticmethod
    def from_dict(data: dict) -> "Player":
        p = Player(
            player_id=data.get("id", ""),
            name=data.get("name", "Player"),
            client_id=data.get("client_id", 0),
            is_host=data.get("is_host", False),
        )
        p.is_ready = data.get("is_ready", False)
        p.custom_data = data.get("custom_data", {})
        return p


class Room:
    """Manages a multiplayer room/lobby with player tracking."""

    def __init__(self, room_name: str = "Room", max_players: int = 8):
        self.name = room_name
        self.max_players = max(2, int(max_players))
        self.players: dict[str, Player] = {}  # player_id -> Player
        self._client_to_player: dict[int, str] = {}  # client_id -> player_id
        self.started = False

    def add_player(self, player: Player) -> bool:
        """Add a player to the room. Returns False if full."""
        if len(self.players) >= self.max_players:
            return False
        self.players[player.id] = player
        if player.client_id:
            self._client_to_player[player.client_id] = player.id
        return True

    def remove_player(self, player_id: str) -> Player | None:
        """Remove a player by ID. Returns the removed Player or None."""
        player = self.players.pop(player_id, None)
        if player and player.client_id in self._client_to_player:
            del self._client_to_player[player.client_id]
        return player

    def get_player(self, player_id: str) -> Player | None:
        return self.players.get(player_id)

    def get_player_by_client(self, client_id: int) -> Player | None:
        pid = self._client_to_player.get(client_id)
        return self.players.get(pid) if pid else None

    def get_player_count(self) -> int:
        return len(self.players)

    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    def all_ready(self) -> bool:
        """Return True if all players are marked as ready."""
        if not self.players:
            return False
        return all(p.is_ready for p in self.players.values())

    def get_host(self) -> Player | None:
        for p in self.players.values():
            if p.is_host:
                return p
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_players": self.max_players,
            "started": self.started,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
        }

    @staticmethod
    def from_dict(data: dict) -> "Room":
        room = Room(
            room_name=data.get("name", "Room"),
            max_players=data.get("max_players", 8),
        )
        room.started = data.get("started", False)
        for pid, pdata in data.get("players", {}).items():
            room.players[pid] = Player.from_dict(pdata)
        return room
