# Unit Engine

Anvil's unit engine is built around the `Dim` class and the `UnitDB` singleton (`anvil.units.db`). Every `Quantity` carries a `Dim` object that tracks physical dimensions independently of the numerical value.

---

## Dim — Physical Dimension Object

`Dim` stores dimensions as a dict of `{symbol: exponent}`. Only non-zero exponents are stored.

**Standard SI symbols:**

| Symbol | Dimension |
|--------|-----------|
| `L` | Length |
| `M` | Mass |
| `T` | Time |
| `TH` (displayed as Θ) | Temperature |
| `N` | Amount of substance |
| `I` | Electric current |
| `J` | Luminous intensity |

### Creating Dim objects

```python
from anvil.units import Dim

force     = Dim(L=1, M=1, T=-2)     # Newton: [L][M][T-2]
pressure  = Dim(L=-1, M=1, T=-2)    # Pascal: [L-1][M][T-2]
dimless   = Dim()                    # dimensionless (empty)
dimless   = Dim.dimensionless()      # singleton version

# Parse from string
d = Dim.parse("[L][M][T-2]")        # standard
d = Dim.parse("[LMT-2]")            # compact — same result
d = Dim.parse("[L2][T-2]")          # with exponents
```

### Dim arithmetic

```python
velocity  = Dim(L=1) / Dim(T=1)         # [L][T-1]
kinetic_e = Dim(M=1) * Dim(L=1, T=-1)**2 # [L2][M][T-2] = J

force = Dim(L=1, M=1, T=-2)
area  = Dim(L=2)
pressure = force / area                 # [L-1][M][T-2] = Pa
```

| Operation | Dim result |
|-----------|-----------|
| `d1 * d2` | Exponents add |
| `d1 / d2` | Exponents subtract |
| `d ** n`  | Exponents scale by n |
| `~d`      | Exponents negate (invert) |

### Dim comparison

```python
Dim(L=1, M=1, T=-2) == Dim(L=1, M=1, T=-2)   # True
Dim(L=1) == Dim(T=1)                            # False
hash(d)                                          # hashable — usable as dict key
```

---

## UnitDB — The Unit Database

`anvil.units.db` is a singleton `UnitDB` instance. It maps unit strings → (scale_to_SI, Dim) pairs and provides reverse lookup (Dim → named unit).

### `db.lookup(unit_str)` → `(scale, Dim)`

```python
from anvil.units import db

scale, dim = db.lookup("Pa")
# scale = 1.0, dim = Dim(L=-1, M=1, T=-2)

scale, dim = db.lookup("psi")
# scale = 6894.757, dim = Dim(L=-1, M=1, T=-2)

scale, dim = db.lookup("cm/s")
# scale = 0.01, dim = Dim(L=1, T=-1)  — parsed as compound

scale, dim = db.lookup("flarps")
# scale = 1.0, dim = Dim(flarps=1)    — custom dimension created
```

### `db.find_unit(dim, system)` → `(name, scale)` or `None`

Reverse lookup: given a `Dim`, find the preferred display unit for "SI" or "Imperial".

```python
from anvil.units import Dim
db.find_unit(Dim(L=1, M=1, T=-2), "SI")        # ("N", 1.0)
db.find_unit(Dim(L=1, M=1, T=-2), "Imperial")   # ("lbf", 4.448...)
db.find_unit(Dim(L=-1, M=1, T=-2), "SI")        # ("Pa", 1.0)
```

### `db.conversion_factor(from_unit, to_unit)` → float

```python
db.conversion_factor("Pa", "psi")   # 1/6894.757 ≈ 0.000145
db.conversion_factor("m/s", "ft/s") # 1/0.3048  ≈ 3.28084
```

### `db.get_offset(unit_str)` → float

Returns the additive SI offset for a unit. Returns `0.0` for all non-offset units.

```python
db.get_offset("degC")   # 273.15
db.get_offset("°C")     # 273.15
db.get_offset("degF")   # 255.3722...  (= 459.67 × 5/9)
db.get_offset("K")      # 0.0
db.get_offset("Pa")     # 0.0
```

### `db.compatible(a, b)` → bool

```python
db.compatible("Pa", "psi")  # True — same dimension
db.compatible("Pa", "K")    # False
db.compatible("degC", "K")  # True — same [Θ] dimension
db.compatible("degF", "R")  # True
```

---

## Compound Unit Parser

Units not in the database are parsed at runtime from their components using `_parse_compound_unit()`.

**Rules:**
- `*` separates numerator factors
- `/` separates denominator factors (negates exponents of all following terms)
- `^` or `**` raises base to power
- Exponents can be negative or float: `s^-2`, `m^0.5`
- Each base unit must be individually registered

**Examples:**

```python
from anvil import Q

Q(1.5, "g/s")       # → 0.0015 kg/s     [M][T-1]
Q(10,  "cm/s")      # → 0.1 m/s         [L][T-1]
Q(5,   "cm^3")      # → 5e-6 m^3        [L3]
Q(5,   "cm**3")     # ** also accepted
Q(200, "W/m^2")     # → W/m^2           [M][T-3]
Q(1e-3,"Pa*s")      # → Pa·s            [L-1][M][T-1]
Q(1,   "kg*m/s^2")  # → 1 N             [L][M][T-2]
Q(1,   "J/kg/K")    # → J/kg/K          [L2][T-2][Θ-1]
Q(1,   "m^0.5")     # fractional exponent OK
```

**Limitation:** Every base token must be a known unit. `Q(1, "flarps/s")` creates a custom dimension `flarps` and parses `/s` correctly, but `flarps` will have an unknown dimension unless explicitly registered.

---

## Category Aliases

Pass a category name as the unit string to get the default SI unit for that dimension:

| Category | Resolves to | Dim |
|----------|------------|-----|
| `"length"` | m | [L] |
| `"area"` | m^2 | [L2] |
| `"volume"` | m^3 | [L3] |
| `"mass"` | kg | [M] |
| `"time"` | s | [T] |
| `"temperature"` | K | [Θ] |
| `"velocity"` | m/s | [L][T-1] |
| `"acceleration"` | m/s^2 | [L][T-2] |
| `"force"` | N | [L][M][T-2] |
| `"pressure"` | Pa | [L-1][M][T-2] |
| `"stress"` | Pa | [L-1][M][T-2] |
| `"energy"` | J | [L2][M][T-2] |
| `"power"` | W | [L2][M][T-3] |
| `"density"` | kg/m^3 | [L-3][M] |
| `"dynamic_viscosity"` | Pa*s | [L-1][M][T-1] |
| `"kinematic_viscosity"` | m^2/s | [L2][T-1] |
| `"frequency"` | Hz | [T-1] |
| `"mass_flow"` | kg/s | [M][T-1] |
| `"specific_energy"` | J/kg | [L2][T-2] |
| `"specific_heat"` | J/kg/K | [L2][T-2][Θ-1] |
| `"thermal_conductivity"` | W/m/K | [L][M][T-3][Θ-1] |
| `"molar_mass"` | kg/mol | [M][N-1] |
| `"angle"` | (dimensionless) | {} |

---

## Complete Unit Table

### Length
| Unit | SI scale | Notes |
|------|----------|-------|
| `m` | 1.0 | SI preferred |
| `km` | 1000.0 | |
| `cm` | 0.01 | |
| `mm` | 0.001 | |
| `um` | 1e-6 | micrometers |
| `in` | 0.0254 | also `inch`, `in_` (Python keyword workaround) |
| `ft` | 0.3048 | Imperial preferred |
| `mi` | 1609.344 | miles |
| `nmi` | 1852.0 | nautical miles |

### Mass
| Unit | SI scale | Notes |
|------|----------|-------|
| `kg` | 1.0 | SI preferred |
| `g` | 0.001 | |
| `mg` | 1e-6 | |
| `lb` | 0.45359237 | pound-mass |
| `lbm` | 0.45359237 | alias |
| `slug` | 14.5939 | Imperial preferred |
| `oz` | 0.028350 | ounce |
| `tonne` | 1000.0 | metric ton |

### Time
| Unit | SI scale |
|------|----------|
| `s` | 1.0 |
| `ms` | 0.001 |
| `us` | 1e-6 |
| `min` | 60.0 |
| `hr` | 3600.0 |

### Temperature
| Unit | Scale (K per unit) | SI offset (K) | Notes |
|------|--------------------|---------------|-------|
| `K` | 1.0 | 0 | Kelvin, SI preferred |
| `R` | 5/9 ≈ 0.5556 | 0 | Rankine, Imperial preferred |
| `degC` | 1.0 | +273.15 | Celsius — full offset arithmetic |
| `°C` | 1.0 | +273.15 | Unicode alias for `degC` |
| `degF` | 5/9 | +255.372 | Fahrenheit — full offset arithmetic |
| `°F` | 5/9 | +255.372 | Unicode alias for `degF` |

**Storage formula:** `SI_value = input_value × scale + offset`
**Display formula:** `display_value = (SI_value − offset) / scale`

```python
from anvil import Q

Q(25, "degC").si          # 298.15  (stored as K)
Q(25, "degC").value       # 25.0    (display in °C)
Q(25, "degC").to("K")     # 298.15 K
Q(25, "degC").to("degF")  # 77.00 degF
Q(100, "degC").to("degF") # 212.00 degF
Q(32,  "degF").to("K")    # 273.15 K
Q(373.15, "K").to("degC") # 100.00 degC

# Unicode forms
Q(0, "°C").si             # 273.15
Q(32, "°F").to("°C")      # 0.00 °C
```

> **Note:** `degC`/`degF` share the `[Θ]` dimension with `K` and `R` — all conversions and dimension checks work normally. Arithmetic between temperature quantities (e.g., `Q(100,"degC") + Q(50,"degC")`) operates on the SI (Kelvin) values, which is the physically correct behaviour for absolute-scale arithmetic. For temperature *differences* the result is correct; for absolute sums the meaning is ambiguous (as it is in any unit system).

### Force
| Unit | SI scale |
|------|----------|
| `N` | 1.0 |
| `kN` | 1000.0 |
| `MN` | 1e6 |
| `lbf` | 4.4482216 |

### Pressure
| Unit | SI scale |
|------|----------|
| `Pa` | 1.0 |
| `kPa` | 1000.0 |
| `MPa` | 1e6 |
| `GPa` | 1e9 |
| `bar` | 1e5 |
| `atm` | 101325.0 |
| `psi` | 6894.757 |
| `psia` | 6894.757 (alias) |
| `torr` | 133.322 |

### Energy
| Unit | SI scale | Notes |
|------|----------|-------|
| `J` | 1.0 | |
| `kJ` | 1000.0 | |
| `MJ` | 1e6 | |
| `Wh` | 3600.0 | watt-hour |
| `kWh` | 3.6e6 | kilowatt-hour |
| `cal` | 4.184 | |
| `kcal` | 4184.0 | |
| `BTU` | 1055.06 | |
| `eV` | 1.602e-19 | |

### Power
| Unit | SI scale |
|------|----------|
| `W` | 1.0 |
| `kW` | 1000.0 |
| `MW` | 1e6 |
| `hp` | 745.70 |

### Velocity
| Unit | SI scale |
|------|----------|
| `m/s` | 1.0 |
| `km/s` | 1000.0 |
| `km/hr` | 0.27778 |
| `ft/s` | 0.3048 |
| `mph` | 0.44704 |
| `kn` | 0.51444 |

### Density
| Unit | SI scale |
|------|----------|
| `kg/m^3` | 1.0 |
| `g/cm^3` | 1000.0 |
| `lb/ft^3` | 16.0185 |
| `slug/ft^3` | 515.379 |

### Specific heat / specific energy
| Unit | SI scale |
|------|----------|
| `J/kg/K` | 1.0 |
| `kJ/kg/K` | 1000.0 |
| `BTU/lb/R` | 4186.8 |
| `J/kg` | 1.0 |
| `kJ/kg` | 1000.0 |
| `BTU/lb` | 2326.0 |

### Viscosity
| Unit | SI scale | Dim |
|------|----------|-----|
| `Pa*s` | 1.0 | dynamic |
| `poise` | 0.1 | dynamic |
| `m^2/s` | 1.0 | kinematic |

### Molar
| Unit | SI scale |
|------|----------|
| `mol` | 1.0 |
| `kmol` | 1000.0 |
| `kg/mol` | 1.0 |
| `g/mol` | 0.001 |
| `J/mol/K` | 1.0 |

### Other
| Unit | SI scale | Dim |
|------|----------|-----|
| `V` | 1.0 | Voltage [L2][M][T-3][I-1] |
| `Hz` | 1.0 | Frequency [T-1] |
| `kHz` | 1000.0 | |
| `MHz` | 1e6 | |
| `rad` | 1.0 | Angle (dimensionless); SI value is radians |
| `deg` | π/180 | Angle (dimensionless); `.si` returns radians |
| `A` | 1.0 | Current [I] |
| `mA` | 0.001 | |

### Acceleration, Area, Volume
| Unit | SI scale |
|------|----------|
| `m/s^2` | 1.0 |
| `ft/s^2` | 0.3048 |
| `m^2` | 1.0 |
| `cm^2` | 1e-4 |
| `mm^2` | 1e-6 |
| `ft^2` | 0.0929 |
| `in^2` | 6.4516e-4 |
| `m^3` | 1.0 |
| `cm^3` | 1e-6 |
| `L` | 0.001 |
| `ft^3` | 0.0283 |
| `gal` | 3.785e-3 |

### Mass flow
| Unit | SI scale |
|------|----------|
| `kg/s` | 1.0 |
| `lb/s` | 0.45359 |

---

## UnitStub — Value × Unit Syntax

`UnitStub` objects can be combined to form compound stubs before multiplying by a value:

```python
from anvil import m, s, kg, Pa

v_stub   = m/s          # UnitStub("m/s")
g_stub   = m/s**2       # UnitStub("m/s^2")
rho_stub = kg/m**3      # UnitStub("kg/m^3")

v   = 340 * v_stub      # Q(340, "m/s")
g   = 9.81 * g_stub     # Q(9.81, "m/s^2")
rho = 1.225 * rho_stub  # Q(1.225, "kg/m^3")
```

**Available stubs** (directly importable from `anvil`):

```
K, Pa, m, s, kg, mol, A, N, J, W, rad, deg
km, cm, mm, um, g, tonne, ms, us, hr
kPa, MPa, GPa, bar, atm, psi
kN, kJ, MJ, kW, BTU
ft, inch, in_, lb, lbf
kmol, g_mol, kg_mol
```

> **`in` vs `inch` vs `in_`:** `in` is a Python keyword. Use `inch` or `in_` as stubs. String form `Q(5, "in")` still works.

---

## Display System

```python
anvil.set_units("SI")        # Pa, N, m/s, K, kg, J, W  (default)
anvil.set_units("Imperial")  # psi, lbf, ft/s, R, slug, BTU, hp
```

Affects only display (`.value`, `.unit`, `repr()`). Internal SI storage is unchanged.

---

## Custom Dimensions

Unknown unit strings automatically create custom dimensions:

```python
from anvil import Q
q1 = Q(5, "flarps")     # custom dim: Dim(flarps=1)
q2 = Q(3, "widgets")    # custom dim: Dim(widgets=1)

r = q1 * q2             # Dim(flarps=1, widgets=1) → displayed as "[flarps][widgets]"
r2 = q1 / Q(2, "s")    # Dim(T=-1, flarps=1) → "[T-1][flarps]"
```

Custom dims propagate correctly through all arithmetic but can never be displayed as a named unit.

---

## Angles and RSQ Conventions

Angles are dimensionless in Anvil's dimension system. `Q(45, "deg").si` returns 0.7854 (radians). `Q(1, "rad").si` returns 1.0.

Built-in RSQs that accept angles in degrees (parameters named `_deg`) accept **either** a plain `float` (treated as degrees) **or** a `Q(value, "deg")` object:

```python
# Both are equivalent:
anvil.R.j2_precession(a=6878e3, e=0.001, i_deg=97.4)
anvil.R.j2_precession(a=6878e3, e=0.001, i_deg=Q(97.4, "deg"))

# Also works from a System:
sys.add("i_deg", 97.4, "deg")   # stored as Q(97.4, "deg")
sys.use("j2_precession")         # RSQ receives the Q and converts correctly
```

When a System stores an angle as `Q(97.4, "deg")`, `.si` = 1.699 rad. The RSQ uses `.si` directly (skips the degrees→radians conversion) so results are correct either way.

---

## Module-level Functions

```python
from anvil import units

units.resolve("Pa")                  # (1.0, Dim(L=-1, M=1, T=-2))
units.find_unit(Dim(L=1, M=1, T=-2)) # ("N", 1.0)
units.compatible("Pa", "psi")        # True
units.conversion_factor("m", "ft")   # 3.28084
units.list_units()                   # sorted list of all registered unit strings
units.list_categories()              # sorted list of category names
units.set_system("Imperial")
units.get_system()                   # "Imperial"
```
