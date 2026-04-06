import math

class Vector2:
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y

    # -- Arithmetic operators ------------------------------------------------

    def __add__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x + other.x, self.y + other.y)
        return Vector2(self.x + other, self.y + other)

    def __radd__(self, other):
        return Vector2(other + self.x, other + self.y)

    def __iadd__(self, other):
        if isinstance(other, Vector2):
            self.x += other.x
            self.y += other.y
        else:
            self.x += other
            self.y += other
        return self

    def __sub__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x - other.x, self.y - other.y)
        return Vector2(self.x - other, self.y - other)

    def __rsub__(self, other):
        return Vector2(other - self.x, other - self.y)

    def __isub__(self, other):
        if isinstance(other, Vector2):
            self.x -= other.x
            self.y -= other.y
        else:
            self.x -= other
            self.y -= other
        return self

    def __mul__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x * other.x, self.y * other.y)
        return Vector2(self.x * other, self.y * other)

    def __rmul__(self, other):
        return Vector2(other * self.x, other * self.y)

    def __imul__(self, other):
        if isinstance(other, Vector2):
            self.x *= other.x
            self.y *= other.y
        else:
            self.x *= other
            self.y *= other
        return self
    
    def __truediv__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x / other.x, self.y / other.y)
        return Vector2(self.x / other, self.y / other)

    def __itruediv__(self, other):
        if isinstance(other, Vector2):
            self.x /= other.x
            self.y /= other.y
        else:
            self.x /= other
            self.y /= other
        return self

    def __neg__(self):
        return Vector2(-self.x, -self.y)

    # -- Comparison and hashing ----------------------------------------------

    def __eq__(self, other):
        if isinstance(other, Vector2):
            return self.x == other.x and self.y == other.y
        return NotImplemented

    def __hash__(self):
        return hash((self.x, self.y))

    def __bool__(self):
        return self.x != 0.0 or self.y != 0.0

    # -- Iteration and representation ----------------------------------------

    def __iter__(self):
        yield self.x
        yield self.y

    def __getitem__(self, index):
        if index == 0:
            return self.x
        if index == 1:
            return self.y
        raise IndexError(f"Vector2 index out of range: {index}")

    def __len__(self):
        return 2

    def __repr__(self):
        return f"Vector2({self.x}, {self.y})"

    # -- Core math -----------------------------------------------------------
    
    def magnitude(self):
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def sqr_magnitude(self):
        return self.x ** 2 + self.y ** 2
    
    def normalize(self):
        m = self.magnitude()
        if m == 0:
            return Vector2(0, 0)
        return Vector2(self.x / m, self.y / m)

    normalized = normalize

    def normalize_ip(self):
        """Normalize this vector in-place. Returns self for chaining."""
        m = self.magnitude()
        if m != 0:
            self.x /= m
            self.y /= m
        return self

    def dot(self, other):
        return self.x * other.x + self.y * other.y

    def cross(self, other):
        return self.x * other.y - self.y * other.x

    def copy(self):
        return Vector2(self.x, self.y)

    # -- Utility methods -----------------------------------------------------

    def distance_to(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def distance_to_squared(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        return dx * dx + dy * dy

    def lerp(self, other, t):
        t = max(0.0, min(1.0, t))
        return Vector2(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t
        )

    def angle(self):
        return math.degrees(math.atan2(self.y, self.x))

    def angle_to(self, other):
        return math.degrees(math.atan2(other.y - self.y, other.x - self.x))

    def rotate(self, degrees):
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        return Vector2(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a
        )

    def reflect(self, normal):
        d = 2.0 * self.dot(normal)
        return Vector2(self.x - d * normal.x, self.y - d * normal.y)

    # -- Class-level constants -----------------------------------------------

    @classmethod
    def zero(cls):
        return cls(0.0, 0.0)

    @classmethod
    def one(cls):
        return cls(1.0, 1.0)

    @classmethod
    def up(cls):
        return cls(0.0, -1.0)

    @classmethod
    def down(cls):
        return cls(0.0, 1.0)

    @classmethod
    def left(cls):
        return cls(-1.0, 0.0)

    @classmethod
    def right(cls):
        return cls(1.0, 0.0)
