"""
Dimension-first unit engine with parallel mirror computation.

Every Quantity carries a Dim object alongside its numerical value.
Dim propagates through all arithmetic automatically:

    Dim * Dim  →  exponents add       (force = mass * acceleration)
    Dim / Dim  →  exponents subtract  (velocity = distance / time)
    Dim ** n   →  exponents scale     (area = length^2)
    Dim + Dim  →  must match          (can't add meters to seconds)

After computation, the resulting Dim is cross-referenced against the
unit database. If a named unit exists, it's displayed. If not, the
raw dimensional expression is shown: [L2][M][T-3].

Unknown unit strings are assigned custom dimensions automatically.
They propagate through arithmetic and appear in results as-is.
"""

from __future__ import annotations
from typing import Optional


# ============================================================
# Dim: the dimension object
# ============================================================

class Dim:
    """
    An immutable dimension vector using dict for extensibility.

    Standard SI base dimensions: L, M, T, TH (Θ), N, I, J
    Custom dimensions: any string (e.g., "flarps", "widgets")

    Only non-zero exponents are stored.
    """

    __slots__ = ("_exp", "_hash")

    def __init__(self, _exp_dict=None, **exponents):
        if _exp_dict is not None:
            self._exp = {k: v for k, v in _exp_dict.items() if v != 0}
        else:
            self._exp = {k: v for k, v in exponents.items() if v != 0}
        self._hash = None  # lazy

    # === Arithmetic (the mirror computation) ===

    def __mul__(self, other):
        """Multiply dimensions → add exponents."""
        if not isinstance(other, Dim):
            return NotImplemented
        combined = dict(self._exp)
        for k, v in other._exp.items():
            combined[k] = combined.get(k, 0) + v
        return Dim(combined)

    def __truediv__(self, other):
        """Divide dimensions → subtract exponents."""
        if not isinstance(other, Dim):
            return NotImplemented
        combined = dict(self._exp)
        for k, v in other._exp.items():
            combined[k] = combined.get(k, 0) - v
        return Dim(combined)

    def __pow__(self, n):
        """Raise dimension to a power → scale exponents."""
        n = float(n)
        return Dim({k: v * n for k, v in self._exp.items()})

    def __invert__(self):
        """Invert dimension → negate exponents."""
        return Dim({k: -v for k, v in self._exp.items()})

    # === Comparison ===

    def __eq__(self, other):
        if not isinstance(other, Dim):
            return NotImplemented
        return self._exp == other._exp

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(frozenset(self._exp.items()))
        return hash(self._hash)

    # === Properties ===

    @property
    def is_dimensionless(self):
        return len(self._exp) == 0

    @property
    def exponents(self):
        """Dict of {dimension_symbol: exponent}."""
        return dict(self._exp)

    def to_key(self):
        """Hashable key for database lookup."""
        return frozenset(self._exp.items())

    # === Display ===

    def __repr__(self):
        if self.is_dimensionless:
            return "dimensionless"
        parts = []
        # Sort: standard dims first (L, M, T, TH, N, I, J), then custom
        standard_order = ["L", "M", "T", "TH", "N", "I", "J"]
        for sym in standard_order:
            if sym in self._exp:
                exp = self._exp[sym]
                display_sym = "Θ" if sym == "TH" else sym
                if exp == 1:
                    parts.append(f"[{display_sym}]")
                else:
                    parts.append(f"[{display_sym}{_format_exp(exp)}]")
        # Custom dims
        for sym in sorted(self._exp):
            if sym not in standard_order:
                exp = self._exp[sym]
                if exp == 1:
                    parts.append(f"[{sym}]")
                else:
                    parts.append(f"[{sym}{_format_exp(exp)}]")
        return "".join(parts)

    def __str__(self):
        return self.__repr__()

    # === Constructors ===

    @staticmethod
    def dimensionless():
        return _DIMENSIONLESS

    @staticmethod
    def parse(s):
        """
        Parse dimension strings. Supports:
            '[L-1][M][T-2]'   — standard (separate brackets)
            '[L2][T-2]'       — separate with exponents
            '[LMT-2]'         — compact (multiple dims in one bracket)
            '[L2MT-2]'        — compact with exponents
        """
        import re
        exp = {}
        bracket_contents = re.findall(r'\[([^\]]+)\]', s)
        if not bracket_contents:
            raise ValueError(f"Cannot parse dimension string: '{s}'")

        # Standard SI dimension symbols, longest first so TH matched before T
        _KNOWN = ['TH', 'Θ', 'θ', 'L', 'M', 'T', 'N', 'I', 'J']
        _NORMALIZE = {'Θ': 'TH', 'θ': 'TH'}

        for content in bracket_contents:
            pos = 0
            while pos < len(content):
                # Try to match a known symbol (2-char first, then 1-char)
                matched = None
                for sym in _KNOWN:
                    if content[pos:pos + len(sym)] == sym:
                        matched = sym
                        break
                if matched is None:
                    raise ValueError(
                        f"Unknown dimension symbol at position {pos} "
                        f"in bracket '{content}' of '{s}'"
                    )
                pos += len(matched)
                # Optional exponent: -?digits
                m = re.match(r'(-?[0-9]+)', content[pos:])
                e = int(m.group(1)) if m else 1
                if m:
                    pos += len(m.group(1))
                # Normalize symbol
                normalized = _NORMALIZE.get(matched, matched)
                exp[normalized] = exp.get(normalized, 0) + e

        return Dim({k: v for k, v in exp.items() if v != 0})


def _format_exp(exp):
    """Format an exponent for display. Integer if whole, else float."""
    if exp == int(exp):
        return str(int(exp))
    return f"{exp:g}"


# Singleton for dimensionless
_DIMENSIONLESS = Dim()


# ============================================================
# Unit database
# ============================================================

class UnitDB:
    """
    Central unit database.

    Each entry maps a unit string to (scale_to_SI, Dim).
    Reverse lookup maps Dim → list of (unit_name, scale) for display.
    """

    def __init__(self):
        self._forward = {}     # unit_str → (scale, Dim)
        self._reverse = {}     # Dim.to_key() → [(name, scale), ...]
        self._si_pref = {}     # Dim.to_key() → preferred SI unit name
        self._imp_pref = {}    # Dim.to_key() → preferred Imperial unit name
        self._custom_dims = set()  # custom dimension symbols we've created
        self._offsets = {}     # unit_str → additive SI offset (SI = value*scale + offset)

    def register(self, name, scale, dim, offset=0.0):
        """Register a unit. offset: additive SI offset (SI = value*scale + offset)."""
        if isinstance(dim, dict):
            dim = Dim(dim)
        self._forward[name] = (scale, dim)
        if offset:
            self._offsets[name] = offset
        key = dim.to_key()
        if key not in self._reverse:
            self._reverse[key] = []
        self._reverse[key].append((name, scale))

    def get_offset(self, unit_str):
        """Return the additive SI offset for a unit (0.0 for most units)."""
        return self._offsets.get(unit_str.strip(), 0.0)

    def set_preferred(self, dim, si_name, imperial_name=None):
        """Set the preferred display unit for a dimension in each system."""
        if isinstance(dim, dict):
            dim = Dim(dim)
        key = dim.to_key()
        self._si_pref[key] = si_name
        if imperial_name:
            self._imp_pref[key] = imperial_name

    def lookup(self, unit_str):
        """
        Look up a unit string.

        Returns (scale_to_SI, Dim).
        If not found, treats it as a custom dimension.
        """
        unit_str = unit_str.strip()

        # Empty → dimensionless
        if not unit_str:
            return 1.0, _DIMENSIONLESS

        # Known unit
        if unit_str in self._forward:
            return self._forward[unit_str]

        # Normalize Python power notation (**) → caret (^), check again
        normalized = unit_str.replace("**", "^")
        if normalized != unit_str and normalized in self._forward:
            self._forward[unit_str] = self._forward[normalized]
            return self._forward[unit_str]

        # Dimension category name (like "pressure", "velocity")
        if unit_str in _CATEGORIES:
            dim = _CATEGORIES[unit_str]
            key = dim.to_key()
            if key in self._si_pref:
                pref = self._si_pref[key]
                return self._forward[pref]
            return 1.0, dim

        # Raw dimension string: [L-1][M][T-2] or compact [LMT-2]
        if "[" in unit_str:
            dim = Dim.parse(unit_str)
            return 1.0, dim

        # Try parsing as compound unit expression: cm/s, g/s, m**3/s, cm^3, etc.
        parsed = _parse_compound_unit(normalized, self)
        if parsed is not None:
            scale, dim = parsed
            # Cache under both the original and normalized strings
            self._forward[unit_str] = (scale, dim)
            if normalized != unit_str:
                self._forward[normalized] = (scale, dim)
            key = dim.to_key()
            if key not in self._reverse:
                self._reverse[key] = []
            if not any(n == unit_str for n, _ in self._reverse[key]):
                self._reverse[key].append((unit_str, scale))
            return scale, dim

        # Unknown unit → create as custom dimension
        if unit_str not in self._custom_dims:
            self._custom_dims.add(unit_str)
            custom_dim = Dim({unit_str: 1})
            self._forward[unit_str] = (1.0, custom_dim)
            key = custom_dim.to_key()
            self._reverse[key] = [(unit_str, 1.0)]
            self._si_pref[key] = unit_str
            self._imp_pref[key] = unit_str
        return self._forward[unit_str]

    def find_unit(self, dim, system="SI"):
        """
        Cross-reference: given a Dim, find the best named unit.

        Returns (unit_name, scale) or None.
        """
        if isinstance(dim, dict):
            dim = Dim(dim)
        if dim.is_dimensionless:
            return ("", 1.0)

        key = dim.to_key()

        # Check preferred unit for the requested system
        pref_map = self._si_pref if system == "SI" else self._imp_pref
        if key in pref_map:
            name = pref_map[key]
            if name in self._forward:
                return (name, self._forward[name][0])

        # Fallback: any unit with scale=1.0
        if key in self._reverse:
            for name, scale in self._reverse[key]:
                if scale == 1.0:
                    return (name, scale)
            return self._reverse[key][0]

        # Not found → return None (caller will show raw dim)
        return None

    def conversion_factor(self, from_unit, to_unit):
        """Multiplicative factor to convert from_unit → to_unit."""
        s_from, d_from = self.lookup(from_unit)
        s_to, d_to = self.lookup(to_unit)
        if d_from != d_to:
            raise ValueError(
                f"Cannot convert '{from_unit}' ({d_from}) to '{to_unit}' ({d_to}): "
                f"incompatible dimensions."
            )
        return s_from / s_to

    def compatible(self, a, b):
        _, da = self.lookup(a)
        _, db = self.lookup(b)
        return da == db

    def list_units(self):
        return sorted(k for k in self._forward if k)

    def list_categories(self):
        return sorted(_CATEGORIES.keys())


# ============================================================
# Dimension categories — human-friendly aliases
# ============================================================

_CATEGORIES = {
    "dimensionless":      _DIMENSIONLESS,
    "length":             Dim(L=1),
    "area":               Dim(L=2),
    "volume":             Dim(L=3),
    "mass":               Dim(M=1),
    "time":               Dim(T=1),
    "temperature":        Dim(TH=1),
    "velocity":           Dim(L=1, T=-1),
    "acceleration":       Dim(L=1, T=-2),
    "force":              Dim(L=1, M=1, T=-2),
    "pressure":           Dim(L=-1, M=1, T=-2),
    "stress":             Dim(L=-1, M=1, T=-2),
    "energy":             Dim(L=2, M=1, T=-2),
    "power":              Dim(L=2, M=1, T=-3),
    "density":            Dim(L=-3, M=1),
    "dynamic_viscosity":  Dim(L=-1, M=1, T=-1),
    "kinematic_viscosity": Dim(L=2, T=-1),
    "frequency":          Dim(T=-1),
    "mass_flow":          Dim(M=1, T=-1),
    "specific_energy":    Dim(L=2, T=-2),
    "specific_heat":      Dim(L=2, T=-2, TH=-1),
    "thermal_conductivity": Dim(L=1, M=1, T=-3, TH=-1),
    "molar_mass":         Dim(M=1, N=-1),
    "angle":              _DIMENSIONLESS,
}


# ============================================================
# Compound unit expression parser
# ============================================================

def _parse_compound_unit(unit_str, db):
    """
    Parse a compound unit expression like 'cm/s', 'g/s^2', 'm^3/s', 'kg*m/s^2'.

    Rules:
      - '*' and '/' split terms; '/' negates subsequent exponents
      - '^' separates base unit from its exponent
      - Exponents can be negative integers or floats: s^-2, m^0.5
      - Returns (scale_to_SI, Dim) or None if any base unit is unknown.
    """
    import re

    tokens = re.split(r'([*/])', unit_str)
    if len(tokens) <= 1 and '^' not in unit_str:
        return None  # single token with no ^ → not compound; skip

    total_scale = 1.0
    total_dim = _DIMENSIONLESS
    sign = 1  # +1 = numerator, -1 = denominator

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token == '*':
            sign = 1
            continue
        if token == '/':
            sign = -1
            continue

        # Split on '^' to separate base and exponent
        if '^' in token:
            base, exp_str = token.rsplit('^', 1)
            base = base.strip()
            try:
                exp = float(exp_str.strip())
            except ValueError:
                return None
        else:
            base = token
            exp = 1.0

        if base not in db._forward:
            return None  # unknown base unit → can't parse

        base_scale, base_dim = db._forward[base]
        if sign == 1:
            total_scale *= base_scale ** exp
            total_dim = total_dim * (base_dim ** exp)
        else:
            total_scale /= base_scale ** exp
            total_dim = total_dim / (base_dim ** exp)

    return total_scale, total_dim


# ============================================================
# Build the global database singleton
# ============================================================

db = UnitDB()

def _r(name, scale, dim_kw, si=False, imp_name=None):
    """Helper to register a unit."""
    d = Dim(**dim_kw)
    db.register(name, scale, d)
    if si:
        db.set_preferred(d, name, imp_name)

def _ro(name, scale, dim_kw, offset):
    """Helper to register an offset unit (SI = value*scale + offset)."""
    d = Dim(**dim_kw)
    db.register(name, scale, d, offset=offset)

# --- Dimensionless ---
_r("", 1.0, {})
_r("rad", 1.0, {})
_r("deg", 3.141592653589793/180, {})

# --- Length ---
_r("m",   1.0,    dict(L=1), si=True, imp_name="ft")
_r("km",  1e3,    dict(L=1))
_r("cm",  1e-2,   dict(L=1))
_r("mm",  1e-3,   dict(L=1))
_r("um",  1e-6,   dict(L=1))
_r("in",  0.0254, dict(L=1))
_r("ft",  0.3048, dict(L=1))
_r("mi",  1609.344, dict(L=1))
_r("nmi", 1852.0,   dict(L=1))

# --- Mass ---
_r("kg",   1.0,         dict(M=1), si=True, imp_name="slug")
_r("g",    1e-3,        dict(M=1))
_r("mg",   1e-6,        dict(M=1))
_r("lb",   0.45359237,  dict(M=1))
_r("lbm",  0.45359237,  dict(M=1))
_r("slug", 14.593903,   dict(M=1))
_r("oz",   0.028349523125, dict(M=1))
_r("tonne",1e3,         dict(M=1))

# --- Time ---
_r("s",   1.0,  dict(T=1), si=True, imp_name="s")
_r("ms",  1e-3, dict(T=1))
_r("us",  1e-6, dict(T=1))
_r("min", 60.0, dict(T=1))
_r("hr",  3600.0, dict(T=1))

# --- Temperature ---
_r("K",     1.0,     dict(TH=1), si=True, imp_name="R")
_r("R",     5.0/9.0, dict(TH=1))
# Offset units: SI = value*scale + offset
_ro("degC", 1.0,     dict(TH=1), offset=273.15)
_ro("°C",   1.0,     dict(TH=1), offset=273.15)
_ro("degF", 5.0/9.0, dict(TH=1), offset=459.67 * 5.0/9.0)
_ro("°F",   5.0/9.0, dict(TH=1), offset=459.67 * 5.0/9.0)

# --- Amount ---
_r("mol",  1.0, dict(N=1), si=True)
_r("kmol", 1e3, dict(N=1))

# --- Current ---
_r("A",  1.0,  dict(I=1), si=True)
_r("mA", 1e-3, dict(I=1))

# --- Force ---
_r("N",   1.0,             dict(L=1, M=1, T=-2), si=True, imp_name="lbf")
_r("kN",  1e3,             dict(L=1, M=1, T=-2))
_r("MN",  1e6,             dict(L=1, M=1, T=-2))
_r("lbf", 4.4482216152605, dict(L=1, M=1, T=-2))

# --- Pressure ---
_r("Pa",   1.0,    dict(L=-1, M=1, T=-2), si=True, imp_name="psi")
_r("kPa",  1e3,    dict(L=-1, M=1, T=-2))
_r("MPa",  1e6,    dict(L=-1, M=1, T=-2))
_r("GPa",  1e9,    dict(L=-1, M=1, T=-2))
_r("bar",  1e5,    dict(L=-1, M=1, T=-2))
_r("atm",  101325.0, dict(L=-1, M=1, T=-2))
_r("psi",  6894.757293168, dict(L=-1, M=1, T=-2))
_r("psia", 6894.757293168, dict(L=-1, M=1, T=-2))
_r("torr", 133.32236842105, dict(L=-1, M=1, T=-2))

# --- Energy ---
_r("J",    1.0,        dict(L=2, M=1, T=-2), si=True, imp_name="BTU")
_r("kJ",   1e3,        dict(L=2, M=1, T=-2))
_r("MJ",   1e6,        dict(L=2, M=1, T=-2))
_r("Wh",   3600.0,     dict(L=2, M=1, T=-2))
_r("kWh",  3.6e6,      dict(L=2, M=1, T=-2))
_r("cal",  4.184,      dict(L=2, M=1, T=-2))
_r("kcal", 4184.0,     dict(L=2, M=1, T=-2))
_r("BTU",  1055.06,dict(L=2, M=1, T=-2))
_r("eV",   1.602176634e-19, dict(L=2, M=1, T=-2))

# --- Power ---
_r("W",  1.0,  dict(L=2, M=1, T=-3), si=True, imp_name="hp")
_r("kW", 1e3,  dict(L=2, M=1, T=-3))
_r("MW", 1e6,  dict(L=2, M=1, T=-3))
_r("hp", 745.69987158227, dict(L=2, M=1, T=-3))

# --- Velocity ---
_r("m/s",   1.0,       dict(L=1, T=-1), si=True, imp_name="ft/s")
_r("km/s",  1e3,       dict(L=1, T=-1))
_r("km/hr", 1.0/3.6,   dict(L=1, T=-1))
_r("ft/s",  0.3048,    dict(L=1, T=-1))
_r("mph",   0.44704,   dict(L=1, T=-1))
_r("kn",    0.514444,  dict(L=1, T=-1))

# --- Acceleration ---
_r("m/s^2",  1.0,    dict(L=1, T=-2), si=True, imp_name="ft/s^2")
_r("ft/s^2", 0.3048, dict(L=1, T=-2))

# --- Area ---
_r("m^2",  1.0,        dict(L=2), si=True, imp_name="ft^2")
_r("cm^2", 1e-4,       dict(L=2))
_r("mm^2", 1e-6,       dict(L=2))
_r("ft^2", 0.09290304, dict(L=2))
_r("in^2", 6.4516e-4,  dict(L=2))

# --- Volume ---
_r("m^3",  1.0,            dict(L=3), si=True, imp_name="ft^3")
_r("cm^3", 1e-6,           dict(L=3))
_r("L",    1e-3,           dict(L=3))
_r("ft^3", 0.028316846592, dict(L=3))
_r("gal",  3.785411784e-3, dict(L=3))

# --- Density ---
_r("kg/m^3",    1.0,           dict(L=-3, M=1), si=True, imp_name="slug/ft^3")
_r("g/cm^3",    1e3,           dict(L=-3, M=1))
_r("lb/ft^3",   16.01846337396,dict(L=-3, M=1))
_r("slug/ft^3", 515.3788184,   dict(L=-3, M=1))

# --- Viscosity ---
_r("Pa*s",  1.0, dict(L=-1, M=1, T=-1), si=True)
_r("poise", 0.1, dict(L=-1, M=1, T=-1))
_r("m^2/s", 1.0, dict(L=2, T=-1), si=True)

# --- Specific energy ---
_r("J/kg",   1.0,  dict(L=2, T=-2), si=True, imp_name="BTU/lb")
_r("kJ/kg",  1e3,  dict(L=2, T=-2))
_r("BTU/lb", 2326.0, dict(L=2, T=-2))

# --- Specific heat ---
_r("J/kg/K",   1.0,  dict(L=2, T=-2, TH=-1), si=True, imp_name="BTU/lb/R")
_r("kJ/kg/K",  1e3,  dict(L=2, T=-2, TH=-1))
_r("BTU/lb/R", 4186.8, dict(L=2, T=-2, TH=-1))

# --- Thermal conductivity ---
_r("W/m/K", 1.0, dict(L=1, M=1, T=-3, TH=-1), si=True)

# --- Molar ---
_r("kg/mol",  1.0,  dict(M=1, N=-1), si=True)
_r("g/mol",   1e-3, dict(M=1, N=-1))
_r("J/mol/K", 1.0,  dict(L=2, M=1, T=-2, TH=-1, N=-1), si=True)

# --- Mass flow ---
_r("kg/s", 1.0,         dict(M=1, T=-1), si=True, imp_name="lb/s")
_r("lb/s", 0.45359237,  dict(M=1, T=-1))

# --- Voltage ---
_r("V", 1.0, dict(L=2, M=1, T=-3, I=-1), si=True)

# --- Frequency ---
_r("Hz",  1.0,  dict(T=-1), si=True)
_r("kHz", 1e3,  dict(T=-1))
_r("MHz", 1e6,  dict(T=-1))


# ============================================================
# Module-level active unit system
# ============================================================

_active_system = "SI"

def set_system(name):
    global _active_system
    if name not in ("SI", "Imperial"):
        raise ValueError(f"Unknown unit system: '{name}'. Options: 'SI', 'Imperial'")
    _active_system = name

def get_system():
    return _active_system


# ============================================================
# Convenience functions (module-level API)
# ============================================================

def resolve(unit_str):
    """Resolve a unit string → (scale_to_SI, Dim)."""
    return db.lookup(unit_str)

def find_unit(dim, system=None):
    """Find the best named unit for a Dim."""
    return db.find_unit(dim, system or _active_system)

def compatible(a, b):
    return db.compatible(a, b)

def conversion_factor(from_unit, to_unit):
    return db.conversion_factor(from_unit, to_unit)

def list_units():
    return db.list_units()

def list_categories():
    return db.list_categories()


# ============================================================
# UnitStub — enables value * unit syntax
# ============================================================

import numpy as _np


class UnitStub:
    """
    A unit token enabling multiplication syntax.

    Usage:
        from anvil import K, Pa, m, s, kg, N, J, W
        T   = 300 * K            # → Q(300, "K")
        P   = 101325 * Pa        # → Q(101325, "Pa")
        v   = 340.0 * (m/s)      # → Q(340.0, "m/s")
        g   = 9.81 * m/s**2      # → Q(9.81, "m/s^2")   (no parens needed)
        rho = 1.225 * kg/m**3    # → Q(1.225, "kg/m^3") (no parens needed)

    Compound stubs carry their own scale and Dim, computed lazily from the
    unit database. So "s^2", "m/s^2", "kg/m^3" all work correctly even
    when the compound string is not directly registered.
    """
    __slots__ = ("_name", "_scale", "_dim")

    def __init__(self, unit_name: str, scale=None, dim=None):
        object.__setattr__(self, "_name",  unit_name)
        object.__setattr__(self, "_scale", scale)   # None = not yet resolved
        object.__setattr__(self, "_dim",   dim)

    def _resolve(self):
        """Lazy-resolve (scale, Dim) from the unit database."""
        if object.__getattribute__(self, "_scale") is None:
            s, d = db.lookup(object.__getattribute__(self, "_name"))
            object.__setattr__(self, "_scale", s)
            object.__setattr__(self, "_dim",   d)
        return (object.__getattribute__(self, "_scale"),
                object.__getattribute__(self, "_dim"))

    @property
    def name(self):
        return object.__getattribute__(self, "_name")

    # --- scalar × unit ---

    def __rmul__(self, value):
        """300 * K  →  Q(300, 'K')"""
        if isinstance(value, (_np.integer, _np.floating)):
            value = float(value)
        if isinstance(value, (int, float)):
            scale, dim = self._resolve()
            from anvil.quantity import Quantity
            return Quantity._raw(float(value) * scale, dim,
                                 unit_hint=self._name)
        return NotImplemented

    def __mul__(self, value):
        """K * 300 → Q;  Pa * s → UnitStub('Pa*s')"""
        if isinstance(value, (_np.integer, _np.floating)):
            value = float(value)
        if isinstance(value, (int, float)):
            return self.__rmul__(value)
        if isinstance(value, UnitStub):
            s_self, d_self = self._resolve()
            s_other, d_other = value._resolve()
            return UnitStub(f"{self._name}*{value._name}",
                            scale=s_self * s_other,
                            dim=d_self * d_other)
        return NotImplemented

    def __truediv__(self, other):
        """m / s → UnitStub('m/s')"""
        if isinstance(other, UnitStub):
            s_self, d_self = self._resolve()
            s_other, d_other = other._resolve()
            return UnitStub(f"{self._name}/{other._name}",
                            scale=s_self / s_other,
                            dim=d_self / d_other)
        return NotImplemented

    def __pow__(self, n):
        """m**2 → UnitStub('m^2')"""
        if isinstance(n, (int, float)):
            exp = int(n) if float(n) == int(n) else float(n)
            s, d = self._resolve()
            return UnitStub(f"{self._name}^{exp}",
                            scale=s ** n,
                            dim=d ** n)
        return NotImplemented

    def __repr__(self):
        return f"unit[{self._name}]"

    def __str__(self):
        return self._name


# ============================================================
# Common unit stubs — import what you need
# ============================================================
# Base SI
K    = UnitStub("K")
Pa   = UnitStub("Pa")
m    = UnitStub("m")
s    = UnitStub("s")
kg   = UnitStub("kg")
mol  = UnitStub("mol")
A    = UnitStub("A")
N    = UnitStub("N")
J    = UnitStub("J")
W    = UnitStub("W")
rad  = UnitStub("rad")
deg  = UnitStub("deg")

# Length prefixes
km   = UnitStub("km")
cm   = UnitStub("cm")
mm   = UnitStub("mm")
um   = UnitStub("um")

# Mass
g    = UnitStub("g")
tonne = UnitStub("tonne")

# Time
ms   = UnitStub("ms")
us   = UnitStub("us")
hr   = UnitStub("hr")

# Pressure
kPa  = UnitStub("kPa")
MPa  = UnitStub("MPa")
GPa  = UnitStub("GPa")
bar  = UnitStub("bar")
atm  = UnitStub("atm")
psi  = UnitStub("psi")

# Force / Energy / Power
kN   = UnitStub("kN")
kJ   = UnitStub("kJ")
MJ   = UnitStub("MJ")
kW   = UnitStub("kW")
BTU  = UnitStub("BTU")

# Imperial length/mass
ft   = UnitStub("ft")
inch = UnitStub("in")
in_  = UnitStub("in")   # 'in' is a Python keyword; use 'inch' or 'in_'
lb   = UnitStub("lb")
lbf  = UnitStub("lbf")

# Molar
kmol = UnitStub("kmol")
g_mol = UnitStub("g/mol")
kg_mol = UnitStub("kg/mol")
