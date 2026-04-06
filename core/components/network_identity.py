from core.ecs import Component
import time


class NetworkIdentityComponent(Component):
    """
    Marks an entity as network-synchronized across multiplayer sessions.

    Attach to any entity that should be replicated. Works with
    MultiplayerComponent on a manager entity to sync transform,
    custom properties, and ownership.

    Usage in scripts:
        net_id = self.entity.get_component(NetworkIdentityComponent)

        # Check ownership
        if net_id.is_mine():
            # Only the owner should move this entity
            transform.x += speed * dt

        # Set a synced variable (auto-replicated to all peers)
        net_id.set_var("health", 100)
        net_id.set_var("score", 42)

        # Read synced variable
        health = net_id.get_var("health", default=100)

        # Transfer ownership (host authority)
        net_id.transfer_ownership(new_player_id)

    Auto-sync behavior:
        - Transform (x, y, rotation) is synced automatically based on
          sync_transform flag.
        - Custom variables set via set_var() are synced when changed.
        - Sync happens at the rate configured on the MultiplayerComponent.
    """

    def __init__(
        self,
        network_id: str = "",
        owner_id: str = "",
        sync_transform: bool = True,
        sync_interval: float = 0.05,
        interpolate: bool = True,
    ):
        self.entity = None
        self.network_id = str(network_id or "")
        self.owner_id = str(owner_id or "")
        self.sync_transform = bool(sync_transform)
        self.sync_interval = max(0.01, float(sync_interval))
        self.interpolate = bool(interpolate)

        # Synced variables
        self._synced_vars: dict = {}
        self._dirty_vars: set = set()

        # Transform interpolation state
        self._remote_x: float = 0.0
        self._remote_y: float = 0.0
        self._remote_rotation: float = 0.0
        self._has_remote_state = False
        self._lerp_speed: float = 10.0

        # Internal
        self._sync_timer: float = 0.0
        self._last_sent_state: dict = {}
        self._registered = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_mine(self) -> bool:
        """Check if the local player owns this entity."""
        mp = self._get_multiplayer()
        if not mp:
            return True  # No multiplayer = local by default
        return self.owner_id == mp.local_player_id

    def set_var(self, key: str, value):
        """Set a synced variable. Changes are replicated to all peers."""
        old = self._synced_vars.get(key)
        self._synced_vars[key] = value
        if old != value:
            self._dirty_vars.add(key)

    def get_var(self, key: str, default=None):
        """Get a synced variable value."""
        return self._synced_vars.get(key, default)

    def get_all_vars(self) -> dict:
        """Get a copy of all synced variables."""
        return dict(self._synced_vars)

    def transfer_ownership(self, new_owner_id: str):
        """Transfer ownership of this entity to another player (host authority)."""
        from core.multiplayer.protocol import MessageType, encode_message
        mp = self._get_multiplayer()
        if not mp:
            return
        self.owner_id = new_owner_id
        if mp.is_host:
            msg = encode_message(MessageType.OWNERSHIP_TRANSFER, {
                "net_id": self.network_id,
                "new_owner": new_owner_id,
            }, mp.local_player_id)
            mp._broadcast(msg)

    # ------------------------------------------------------------------
    # Sync — called by NetworkSystem
    # ------------------------------------------------------------------

    def update_sync(self, dt: float):
        """Called each frame by the network system to handle sync logic."""
        if not self.entity:
            return

        mp = self._get_multiplayer()
        if not mp or not mp.is_active:
            return

        if self.is_mine():
            self._sync_timer += dt
            if self._sync_timer >= self.sync_interval:
                self._sync_timer = 0.0
                self._send_state(mp)
        else:
            if self.interpolate and self._has_remote_state and self.sync_transform:
                self._interpolate_transform(dt)

    def receive_state(self, state_data: dict):
        """Apply received state from the network."""
        if self.is_mine():
            return  # Don't apply remote state to locally-owned entities

        # Transform
        if self.sync_transform:
            if "x" in state_data:
                self._remote_x = float(state_data["x"])
            if "y" in state_data:
                self._remote_y = float(state_data["y"])
            if "r" in state_data:
                self._remote_rotation = float(state_data["r"])
            self._has_remote_state = True

            if not self.interpolate:
                self._apply_transform_directly()

        # Synced variables
        vars_data = state_data.get("vars", {})
        for k, v in vars_data.items():
            self._synced_vars[k] = v

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_multiplayer(self):
        """Find the MultiplayerComponent in the world."""
        if not self.entity or not self.entity.world:
            return None
        from core.components.multiplayer import MultiplayerComponent
        for entity in self.entity.world.entities:
            mp = entity.get_component(MultiplayerComponent)
            if mp and mp.is_active:
                return mp
        return None

    def _send_state(self, mp):
        """Owner: send current state to all peers."""
        from core.components import Transform
        state = {}

        if self.sync_transform:
            transform = self.entity.get_component(Transform)
            if transform:
                state["x"] = round(float(transform.x), 2)
                state["y"] = round(float(transform.y), 2)
                state["r"] = round(float(transform.rotation), 2)

        # Synced variables (only send dirty ones, or all on first sync)
        if self._dirty_vars or not self._last_sent_state:
            vars_to_send = {}
            if not self._last_sent_state:
                vars_to_send = dict(self._synced_vars)
            else:
                for key in self._dirty_vars:
                    if key in self._synced_vars:
                        vars_to_send[key] = self._synced_vars[key]
            if vars_to_send:
                state["vars"] = vars_to_send
            self._dirty_vars.clear()

        # Only send if state changed
        if state == self._last_sent_state:
            return
        self._last_sent_state = dict(state)

        mp.send_state(self.network_id, state)

    def _interpolate_transform(self, dt: float):
        """Smoothly interpolate toward remote transform state."""
        from core.components import Transform
        transform = self.entity.get_component(Transform)
        if not transform:
            return

        t = min(1.0, self._lerp_speed * dt)
        transform.x = transform.x + (self._remote_x - transform.x) * t
        transform.y = transform.y + (self._remote_y - transform.y) * t
        transform.rotation = transform.rotation + (self._remote_rotation - transform.rotation) * t

    def _apply_transform_directly(self):
        """Snap transform to remote state (no interpolation)."""
        from core.components import Transform
        transform = self.entity.get_component(Transform) if self.entity else None
        if not transform:
            return
        transform.x = self._remote_x
        transform.y = self._remote_y
        transform.rotation = self._remote_rotation
