# Quantity (`Q`)

`Quantity` (aliased as `Q`) is the core value type in Anvil. It stores:
- `_si_value` — the numerical value in SI base units (float64 or ndarray)
- `_dim` — a `Dim` object tracking physical dimensions
- `_unit_hint` — the unit string the user originally specified (for display)

All arithmetic on `Q` objects propagates dimensions in parallel with the numerical computation.

---

## Construction

### String unit

```python
from anvil import Q

p = Q(101325, "Pa")
T = Q(300, "K")
v = Q(340, "m/s")
mdot = Q(1.5, "g/s")       # compound unit — parsed automatically
vol  = Q(5,   "cm^3")      # ** also accepted: "cm**3"
flux = Q(200, "W/m^2")
```

### Category alias

```python
p = Q(101325, "pressure")   # → Pa internally
T = Q(300, "temperature")   # → K internally
v = Q(10, "velocity")       # → m/s internally
```

Category aliases resolve to the preferred SI unit for that dimension. Full list: see [Unit Engine](03_units.md#categories).

### Raw dimension string

```python
# Standard (separate brackets)
d1 = Q(1, "[L][M][T-2]")   # → 1 N
# Compact (all in one bracket)
d2 = Q(1, "[LMT-2]")       # → same
# Both produce identical Dim objects
assert d1._dim == d2._dim   # True
```

### Unit-stub syntax

```python
from anvil import K, Pa, m, s, kg, mol, N, J, W
from anvil import km, cm, mm, g, kPa, MPa, GPa, bar, atm, psi
from anvil import kN, kJ, MJ, kW, BTU, ft, inch, in_, lb, lbf, hr

T   = 300 * K           # Q(300, "K")
P   = 101325 * Pa       # Q(101325, "Pa")
v   = 340 * (m/s)       # Q(340, "m/s")
g   = 9.81 * m/s**2     # Q(9.81, "m/s^2") — parens optional
rho = 1.225 * kg/m**3   # Q(1.225, "kg/m^3")
```

Stubs can be combined with `*`, `/`, `**`:

```python
Pa*s    # → unit for dynamic viscosity
J/kg/K  # → specific heat unit stub
m**3    # → volume unit stub
```

### Numpy arrays

```python
import numpy as np
from anvil import Q

pressures = Q(np.array([100e3, 150e3, 200e3]), "Pa")
print(pressures)         # array(3,) Pa
print(pressures.si)      # array([100000. 150000. 200000.])

# Linspace helper
qs = Q.linspace(100, 300, 5, unit="K")  # list of 5 Quantity objects
```

### `Q(None, unit)` — undefined quantity

```python
q = Q(None, "Pa")
print(q.value)  # None
print(q.si)     # None
```

Used internally for variables declared but not yet computed. `float(Q(None, ...))` raises `ValueError`.

---

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `.si` | `float` or `ndarray` | Value in SI base units (always) |
| `.value` | `float` or `ndarray` | Value in display unit |
| `.unit` | `str` | Display unit name, or raw dim string if no named unit |
| `.dim` | `Dim` | Physical dimension object |
| `.dimensionless` | `bool` | True if no dimensions |
| `.name` | `str` | Optional label (set by System or user) |
| `.bounds` | `tuple` or `None` | (lo, hi) bounds for validation |

```python
T = 300 * K
print(T.si)            # 300.0
print(T.value)         # 300.0 (K is SI for temperature)
print(T.unit)          # "K"
print(T.dim)           # [Θ]

p_psi = Q(14.696, "psi")
print(p_psi.si)        # 101325.0 (converted to Pa internally)
print(p_psi.value)     # 14.696  (display in psi)
print(p_psi.unit)      # "psi"
```

### Display priority

1. User's original unit hint (if dimensionally compatible with current value)
2. Preferred unit from active unit system (SI or Imperial)
3. Raw dimension string `[L][M][T-2]` as fallback

```python
anvil.set_units("Imperial")
Q(101325, "Pa").unit   # "psi" — preferred Imperial unit for pressure
anvil.set_units("SI")
Q(101325, "Pa").unit   # "Pa"
```

---

## Arithmetic

All arithmetic propagates dimensions automatically. Operations work between:
- `Q` × `Q`
- `Q` × `float/int`
- `Q` × `UnitStub`

### Addition / subtraction

Same-dimension only:

```python
Q(100, "Pa") + Q(50, "Pa")      # → 150.00 Pa
Q(1000, "N") - Q(200, "N")      # → 800.00 N

# Dimensionless Q + scalar
Q(1.4) + 0.1                    # → 1.5 (dimensionless)

# Cross-dimension → ValueError
Q(10, "N") + Q(5, "K")          # ValueError: incompatible dimensions

# Dimensional Q + scalar → ValueError
Q(10, "N") + 5                  # ValueError: Cannot add scalar to dimensional quantity
```

### Multiplication / division

Dimensions combine:

```python
Q(100, "N") * Q(0.1, "m")       # → Q(10, "N*m") → displayed as J (energy)
Q(100, "N") / Q(0.01, "m^2")    # → Q(10000, "Pa")
Q(10, "kg") * Q(9.81, "m/s^2")  # → Q(98.1, "N")

# Scale
Q(100, "Pa") * 2                 # → Q(200, "Pa")
Q(100, "Pa") / 4                 # → Q(25, "Pa")
```

### Powers

Integer, float, dimensionless Q exponents:

```python
Q(3, "m") ** 2                   # → Q(9, "m^2")
Q(9, "m^2") ** 0.5               # → Q(3, "m")
Q(3, "m") ** Q(2)                # → Q(9, "m^2") — Q must be dimensionless

Q(3, "m") ** Q(2, "N")          # ValueError: exponent must be dimensionless
```

### Negation / abs

```python
-Q(100, "N")          # → Q(-100, "N")
abs(Q(-100, "N"))     # → Q(100, "N")
```

### Comparison

```python
Q(100, "Pa") == Q(100, "Pa")    # True
Q(100, "Pa") < Q(200, "Pa")     # True
Q(100, "Pa") <= Q(200, "Pa")    # True  (__le__ supported)
Q(200, "Pa") >= Q(100, "Pa")    # True  (__ge__ supported)
Q(100, "Pa") == 100             # True (dimensionless check)
```

Comparison between Q objects uses SI values. Comparing incompatible dimensions raises `TypeError`. Comparing a dimensional Q with a plain float returns `NotImplemented`.

```python
Q(10, "N") < Q(5, "K")
# TypeError: Cannot compare [L][M][T-2] < [Θ]: incompatible dimensions.
#            Convert to the same unit first.
```

---

## Unit Conversion

```python
q.to("unit_string")   # returns new Quantity; original unchanged
```

```python
Q(101325, "Pa").to("atm")      # 1.0000 atm
Q(101325, "Pa").to("psi")      # 14.6959 psi
Q(101325, "Pa").to("kPa")      # 101.3250 kPa
Q(300,    "K").to("R")         # 540.00 R
Q(1000,   "N").to("lbf")       # 224.81 lbf
Q(10,     "m/s").to("cm/s")    # 1000.00 cm/s
Q(10,     "m/s").to("mph")     # 22.37 mph
Q(0.001,  "kg/s").to("g/s")    # 1.0000 g/s
Q(1e-6,   "m^3").to("cm^3")    # 1.0000 cm^3
Q(100,    "J").to("BTU")       # 0.0948 BTU
```

Incompatible dimensions raise `ValueError`:

```python
Q(100, "N").to("K")
# ValueError: Cannot convert [L][M][T-2] to 'K' ([Θ]): incompatible dimensions.
```

---

## Bounds

```python
T = Q(350, "K", bounds=(200, 500))
T.in_bounds()       # True

T_hot = Q(600, "K", bounds=(200, 500))
T_hot.in_bounds()   # False

# System validation checks bounds automatically
sys.add("T", 350, "K", bounds=(200, 500))
sys.validate()      # warns if any quantity is outside bounds
```

---

## f-string formatting

```python
T = 300 * K
print(f"Temperature: {T:.2f}")   # Temperature: 300.00 (formats display value)
print(f"Temperature: {T:.4e}")   # Temperature: 3.0000e+02
```

---

## Jupyter / Notebook display

In Jupyter cells, `Q` objects render as styled inline badges:

```python
Q(340, "m/s")     # → styled HTML: 340.0000 m/s
```

`_repr_latex_()` renders LaTeX: `$340.0000\;\mathrm{m/s}$`

---

## Static constructors

### `Q.linspace(start, stop, num, unit="")`

Returns a Python list of `num` Quantity objects:

```python
temps = Q.linspace(200, 500, 4, unit="K")
# [200.00 K, 300.00 K, 400.00 K, 500.00 K]
```

### `Q.array(values, unit="")`

Wraps a numpy array:

```python
ps = Q.array([100e3, 200e3, 300e3], unit="Pa")
# array(3,) Pa
print(ps.si)   # [100000. 200000. 300000.]
```

---

## Known Limits and Gotchas

### `Q(Q_obj, unit)` — not a double-wrap

Passing a `Q` as the value to `Q()` is **not** double-wrapping. The `Quantity.__init__` always does `float(value) * scale`, which calls `__float__` on the inner Q, returning its SI value. The result is dimensionally correct:

```python
q1 = Q(100, "Pa")
q2 = Q(q1, "Pa")     # works: q2.si == 100.0
```

**However**, this is confusing and should be avoided. Always pass raw numbers.

### Adding scalar to dimensional Q

```python
Q(10, "N") + 5     # ValueError — non-dimensionless Q can't add to scalar
Q(1.4) + 0.1       # OK — dimensionless
```

### Units not in database → custom dimension

```python
q = Q(5, "flarps")
r = q * Q(3, "s")
print(r)            # 15.0000 [T][flarps]  — custom dim preserved
```

Custom dims propagate through arithmetic but can never be converted to a named unit.

### Comparison across dimensions raises `TypeError`

```python
Q(10, "N") < Q(5, "K")
# TypeError: Cannot compare [L][M][T-2] < [Θ]: incompatible dimensions.

Q(10, "N") >= Q(5, "K")
# TypeError: Cannot compare [L][M][T-2] >= [Θ]: incompatible dimensions.
```

`<`, `<=`, `>`, `>=` all raise `TypeError` when dimensions differ. `==` returns `False` (no exception) for dimension mismatches — this matches Python convention where equality across types is usually `False`, not an error.

### `Q ** non-dimensionless Q` → ValueError

```python
Q(3, "m") ** Q(2, "N")    # ValueError: Exponent must be dimensionless.
```

### ndarray Quantities in System solvers

The `_forward()` method calls `float(q._si_value)` on all workspace values. This **fails silently** if the value is an ndarray with ndim > 0 — it will be stored as-is in the workspace, and downstream float arithmetic will fail.

Only scalar Quantities should be system inputs.
