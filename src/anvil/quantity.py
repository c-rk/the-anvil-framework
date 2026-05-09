"""
Quantity: a number with parallel dimension tracking.

Internally stores:
    _si_value  — numerical value in SI base units
    _dim       — Dim object tracking physical dimensions
    _unit_hint — the unit string the user originally typed (for display)

Arithmetic propagates dimensions automatically:
    Q(10, "kg") * Q(9.81, "m/s^2")  →  98.1 N  (Dim auto-resolves)

Unknown units create custom dimensions:
    Q(5, "flarps") * Q(3, "s")  →  15 [flarps][T]

Display:
    1. Cross-reference resulting Dim against unit database
    2. Found → show named unit (Pa, N, W, ...)
    3. Not found → show raw dimension expression [L2][M][T-3]
    4. Unit system (SI/Imperial) picks the preferred name
"""

from __future__ import annotations
import numpy as np
from typing import Optional, Union
from anvil.units import Dim, db as _db, get_system as _get_system

Numeric = Union[int, float, np.integer, np.floating, np.ndarray]


def _is_unit_stub(obj):
    """Duck-type check for UnitStub without circular import."""
    return (hasattr(obj, "_resolve") and hasattr(obj, "_name")
            and not isinstance(obj, Quantity))


class Quantity:

    __slots__ = ("_si_value", "_dim", "_unit_hint", "name", "bounds", "role", "desc")

    def __init__(
        self,
        value: Optional[Numeric] = None,
        unit: str = "",
        *,
        name: str = "",
        bounds: Optional[tuple] = None,
        role: str = "",
        desc: str = "",
    ):
        scale, dim = _db.lookup(unit)

        if value is None:
            self._si_value = None
        elif isinstance(value, np.ndarray):
            self._si_value = value.astype(np.float64) * scale
        else:
            self._si_value = np.float64(value) * scale

        self._dim = dim
        self._unit_hint = unit if unit in _db._forward else ""
        self.name = name
        self.bounds = bounds
        self.role = role
        self.desc = desc

    @classmethod
    def _raw(cls, si_value, dim, name="", unit_hint=""):
        """Internal constructor: create from SI value and Dim directly."""
        q = object.__new__(cls)
        q._si_value = si_value
        q._dim = dim
        q._unit_hint = unit_hint
        q.name = name
        q.bounds = None
        q.role = ""
        q.desc = ""
        return q

    # === Properties ===

    @property
    def si(self):
        """Value in SI base units."""
        return self._si_value

    @property
    def value(self):
        """Value in the display unit."""
        if self._si_value is None:
            return None
        unit_name, scale = self._resolve_display()
        return self._si_value / scale if scale != 0 else self._si_value

    @property
    def unit(self):
        """The display unit string (named unit or raw dimension)."""
        unit_name, _ = self._resolve_display()
        return unit_name

    @property
    def dim(self):
        """The Dim object."""
        return self._dim

    @property
    def dimensionless(self):
        return self._dim.is_dimensionless

    def _resolve_display(self):
        """
        Determine the display unit: name and scale.

        Priority:
            1. User's original unit hint (if still dimensionally compatible)
            2. Preferred unit from the active unit system
            3. Raw dimension string
        """
        # If user specified a unit and it matches the current dimension
        if self._unit_hint and self._unit_hint in _db._forward:
            hint_scale, hint_dim = _db._forward[self._unit_hint]
            if hint_dim == self._dim:
                return self._unit_hint, hint_scale

        # Cross-reference against database
        result = _db.find_unit(self._dim, _get_system())
        if result is not None:
            return result  # (name, scale)

        # Nothing found → raw dimension string
        return str(self._dim), 1.0

    # === Conversion ===

    def to(self, target_unit: str) -> Quantity:
        """Convert to a specific unit."""
        target_scale, target_dim = _db.lookup(target_unit)
        if target_dim != self._dim:
            raise ValueError(
                f"Cannot convert {self._dim} to '{target_unit}' ({target_dim}): "
                f"incompatible dimensions."
            )
        actual_name = target_unit if target_unit in _db._forward else ""
        q = Quantity._raw(self._si_value, self._dim, name=self.name, unit_hint=actual_name)
        q.bounds = self.bounds
        q.role = self.role
        q.desc = self.desc
        return q

    def in_bounds(self):
        if self.bounds is None or self._si_value is None:
            return True
        v = self.value
        if isinstance(v, np.ndarray):
            return bool(np.all(v >= self.bounds[0]) and np.all(v <= self.bounds[1]))
        return self.bounds[0] <= v <= self.bounds[1]

    # === Arithmetic — the mirror computation ===
    # Numerical values: standard math in SI
    # Dimensions: parallel propagation via Dim arithmetic

    def __add__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                raise ValueError(
                    f"Cannot add {self._dim} and {other._dim}: incompatible dimensions."
                )
            return Quantity._raw(self._si_value + other._si_value, self._dim,
                                  unit_hint=self._unit_hint)
        if not self.dimensionless:
            raise ValueError(f"Cannot add scalar to dimensional quantity ({self._dim}).")
        return Quantity._raw(self._si_value + other, self._dim)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                raise ValueError(f"Cannot subtract {other._dim} from {self._dim}.")
            return Quantity._raw(self._si_value - other._si_value, self._dim,
                                  unit_hint=self._unit_hint)
        if not self.dimensionless:
            raise ValueError(f"Cannot subtract scalar from dimensional quantity ({self._dim}).")
        return Quantity._raw(self._si_value - other, self._dim)

    def __rsub__(self, other):
        if isinstance(other, Quantity):
            return other.__sub__(self)
        if not self.dimensionless:
            raise ValueError(f"Cannot subtract dimensional quantity from scalar.")
        return Quantity._raw(other - self._si_value, self._dim)

    def __mul__(self, other):
        if isinstance(other, Quantity):
            new_dim = self._dim * other._dim
            return Quantity._raw(self._si_value * other._si_value, new_dim)
        # Q * UnitStub:  Q(2, "N") * m  →  Q(2, "N*m")
        if _is_unit_stub(other):
            o_scale, o_dim = other._resolve()
            new_dim = self._dim * o_dim
            new_si  = self._si_value * o_scale
            hint = (f"{self._unit_hint}*{other._name}"
                    if self._unit_hint else other._name)
            return Quantity._raw(new_si, new_dim, name=self.name, unit_hint=hint)
        return Quantity._raw(self._si_value * other, self._dim,
                              name=self.name, unit_hint=self._unit_hint)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, Quantity):
            new_dim = self._dim / other._dim
            return Quantity._raw(self._si_value / other._si_value, new_dim)
        # Q / UnitStub:  1.225 * kg / m**3  →  Q(1.225, "kg/m^3")
        if _is_unit_stub(other):
            o_scale, o_dim = other._resolve()
            new_dim = self._dim / o_dim
            new_si  = self._si_value / o_scale
            hint = (f"{self._unit_hint}/{other._name}"
                    if self._unit_hint else "")
            return Quantity._raw(new_si, new_dim, name=self.name, unit_hint=hint)
        return Quantity._raw(self._si_value / other, self._dim,
                              name=self.name, unit_hint=self._unit_hint)

    def __rtruediv__(self, other):
        if isinstance(other, Quantity):
            return other.__truediv__(self)
        new_dim = ~self._dim
        return Quantity._raw(other / self._si_value, new_dim)

    def __pow__(self, power):
        if isinstance(power, Quantity):
            if not power.dimensionless:
                raise ValueError("Exponent must be dimensionless.")
            power = float(power._si_value)
        new_dim = self._dim ** power  # parallel: dims scale
        return Quantity._raw(self._si_value ** power, new_dim)

    def __neg__(self):
        return Quantity._raw(-self._si_value, self._dim,
                              name=self.name, unit_hint=self._unit_hint)

    def __abs__(self):
        return Quantity._raw(np.abs(self._si_value), self._dim,
                              name=self.name, unit_hint=self._unit_hint)

    # === Comparison ===

    def __eq__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                return False
            return np.allclose(self._si_value, other._si_value)
        if self.dimensionless:
            return np.allclose(self._si_value, other)
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                raise TypeError(
                    f"Cannot compare {self._dim} < {other._dim}: incompatible dimensions. "
                    f"Convert to the same unit first."
                )
            return self._si_value < other._si_value
        return self._si_value < other if self.dimensionless else NotImplemented

    def __le__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                raise TypeError(
                    f"Cannot compare {self._dim} <= {other._dim}: incompatible dimensions."
                )
            return self._si_value <= other._si_value
        return self._si_value <= other if self.dimensionless else NotImplemented

    def __gt__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                raise TypeError(
                    f"Cannot compare {self._dim} > {other._dim}: incompatible dimensions. "
                    f"Convert to the same unit first."
                )
            return self._si_value > other._si_value
        return self._si_value > other if self.dimensionless else NotImplemented

    def __ge__(self, other):
        if isinstance(other, Quantity):
            if self._dim != other._dim:
                raise TypeError(
                    f"Cannot compare {self._dim} >= {other._dim}: incompatible dimensions."
                )
            return self._si_value >= other._si_value
        return self._si_value >= other if self.dimensionless else NotImplemented

    def __float__(self):
        if self._si_value is None:
            raise ValueError("Cannot convert undefined Quantity to float.")
        return float(self._si_value)

    def __format__(self, spec):
        """Support f-string format specs: f'{q:.4f}' formats the display value."""
        if spec and self._si_value is not None:
            val = self.value
            if isinstance(val, np.ndarray):
                return format(val, spec)
            return format(float(val), spec)
        return str(self)

    # === Display ===

    def __repr__(self):
        unit = self.unit
        val = self.value
        if val is None:
            val_str = "undefined"
        elif isinstance(val, np.ndarray) and val.ndim > 0:
            val_str = f"array{val.shape}"
        else:
            v = float(val)
            if v == 0:
                val_str = "0"
            elif abs(v) >= 1e6 or (abs(v) < 0.01 and abs(v) > 0):
                val_str = f"{v:.4e}"
            elif abs(v) >= 100:
                val_str = f"{v:.2f}"
            elif abs(v) >= 1:
                val_str = f"{v:.4f}"
            else:
                val_str = f"{v:.6f}"

        parts = [val_str]
        if unit:
            parts.append(unit)
        if self.name:
            parts.append(f"({self.name})")
        return " ".join(parts)

    def __str__(self):
        return self.__repr__()

    # === Jupyter / notebook display ===

    def _format_val_str(self):
        val = self.value
        if val is None:
            return "undefined"
        if isinstance(val, np.ndarray) and val.ndim > 0:
            return f"array{val.shape}"
        v = float(val)
        if v == 0:
            return "0"
        if abs(v) >= 1e6 or (abs(v) < 0.01 and abs(v) > 0):
            return f"{v:.4e}"
        if abs(v) >= 100:
            return f"{v:.2f}"
        if abs(v) >= 1:
            return f"{v:.4f}"
        return f"{v:.6f}"

    def _repr_html_(self):
        v = self._format_val_str()
        u = self.unit
        n = self.name
        unit_span = (f' <span style="color:#555;font-size:.9em">{u}</span>' if u else "")
        name_span = (f' <span style="color:#999;font-size:.85em">({n})</span>' if n else "")
        return (f'<code style="background:#f5f5f5;padding:2px 6px;border-radius:3px">'
                f'<b>{v}</b>{unit_span}{name_span}</code>')

    def _repr_latex_(self):
        v = self._format_val_str()
        u = self.unit
        if u:
            u_latex = u.replace("^", "^{").replace("m^{2}", "m^{2}") + ("}" if "^" in u else "")
            return f"${v}\\;\\mathrm{{{u}}}$"
        return f"${v}$"

    # === Convenience ===

    @staticmethod
    def linspace(start, stop, num, unit="", **kw):
        values = np.linspace(float(start), float(stop), int(num))
        return [Quantity(v, unit, **kw) for v in values]

    @staticmethod
    def array(values, unit="", **kw):
        return Quantity(np.asarray(values, dtype=np.float64), unit, **kw)


Q = Quantity
