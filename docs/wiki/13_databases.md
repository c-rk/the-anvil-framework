# Built-in Databases

Anvil ships three read-only databases:

| Database | Access | Contents |
|----------|--------|---------|
| `anvil.db.const` | `anvil.db.const.c`, `.R`, etc. | Physical constants |
| `anvil.db.fluids` | `anvil.fluids.get("air", T=300)` | Fluid property tables |
| `anvil.db.materials` | `anvil.materials.get("Al-6061-T6")` | Structural material properties |

```python
from anvil.db import fluids, materials, const
# or
import anvil
anvil.fluids.get("water", T=350)
anvil.materials.get("steel-4340")
```

---

## Physical Constants (`anvil.db.const`)

```python
from anvil.db import const

const.c       # Q(299792458.0, "m/s") — speed of light
const.h       # Q(6.626e-34, "J")    — Planck constant
const.k_B     # Q(1.381e-23, "J/kg/K") — Boltzmann
const.R       # Q(8.314, "J/mol/K")  — gas constant
const.N_A     # Q(6.022e23, "")      — Avogadro
const.g0      # Q(9.80665, "m/s^2")  — standard gravity
const.sigma   # Q(5.67e-8, "W")      — Stefan-Boltzmann
const.atm     # Q(101325.0, "Pa")    — standard atmosphere
const.T_sl    # Q(288.15, "K")       — sea-level temperature
const.rho_sl  # Q(1.225, "kg/m^3")  — sea-level density
const.a_sl    # Q(340.294, "m/s")   — sea-level speed of sound
const.gamma_air # Q(1.4, "")         — air heat ratio
const.R_air   # Q(287.058, "J/kg/K") — air gas constant
const.M_air   # Q(0.0289647, "kg/mol") — air molar mass
const.cp_air  # Q(1005.0, "J/kg/K") — air specific heat
const.pi      # Q(3.14159, "")       — π

# List all constants
const.list()
# ['N_A', 'R', 'R_air', 'T_sl', 'a_sl', 'a_sl', 'atm', 'c', 'cp_air', 'g0',
#  'gamma_air', 'h', 'k_B', 'M_air', 'pi', 'rho_sl', 'sigma', 'T_sl']

# Search
const.search("gravity")
# [('g0', 9.8067 m/s^2)]

const.search("gas")
# [('R', 8.3145 J/mol/K), ('R_air', 287.06 J/kg/K)]
```

---

## Fluid Database (`anvil.fluids`)

Property tables for common engineering fluids. Uses curve-fit or tabulated data (no external packages needed).

### `fluids.get(name, T, P=101325)`

```python
from anvil.db import fluids

# Air at 500 K, 1 atm
air = fluids.get("air", T=500)
print(air["rho"])    # Q(0.7054, "kg/m^3")
print(air["mu"])     # Q(2.670e-5, "Pa*s")
print(air["cp"])     # Q(1005.0, "J/kg/K")
print(air["k"])      # Q(0.0404, "W/m/K")
print(air["gamma"])  # 1.4 (dimensionless float)
print(air["R_gas"])  # Q(287.058, "J/kg/K")
print(air["Pr"])     # 0.71

# Water at 350 K
water = fluids.get("water", T=350)
# rho, mu, cp, k properties

# Nitrogen at high temperature
n2 = fluids.get("nitrogen", T=1000)

# Helium
he = fluids.get("helium", T=300)

# Hydrogen
h2 = fluids.get("hydrogen", T=300)

# CO2
co2 = fluids.get("co2", T=300)
```

### Available fluids

| Name | Description | T range |
|------|-------------|---------|
| `"air"` | Dry air at 1 atm | 200–2000 K |
| `"nitrogen"` | N₂ | 200–2000 K |
| `"helium"` | He | 50–2000 K |
| `"hydrogen"` | H₂ | 200–3000 K |
| `"co2"` | CO₂ | 250–1500 K |
| `"water"` | Liquid/vapor | 280–600 K |
| `"methane"` | CH₄ | 200–2000 K |
| `"oxygen"` | O₂ | 200–2000 K |
| `"argon"` | Ar | 100–2000 K |

### Property models

Most gaseous fluids use:
- **Density:** Ideal gas law — `ρ = P/(R·T)`
- **Viscosity:** Sutherland's law — `μ = μ_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S)`
- **Conductivity:** Power law — `k = k_ref·(T/T_ref)^n`
- **cp, γ:** Constant (approximate)

These are suitable for temperature ranges away from critical point and liquid-vapor transitions. For high-accuracy near-critical or cryogenic properties, use the CoolProp adapter.

### `fluids.search(keyword)`

```python
fluids.search("nitrogen")
# Returns list of matching fluid entries
```

### Usage in System

```python
fluid = fluids.get("air", T=350, P=200e3)
sys.add("rho", float(fluid["rho"].si), "kg/m^3")
sys.add("mu",  float(fluid["mu"].si),  "Pa*s")
```

---

## Material Database (`anvil.materials`)

Structural material properties. Data from standard references (ASM, MIL-HDBK-5).

### `materials.get(name)`

```python
from anvil.db import materials

al = materials.get("Al-6061-T6")
print(al["E"])         # Q(68.9e9, "Pa")  — Young's modulus
print(al["sigma_y"])   # Q(276e6, "Pa")   — Yield strength
print(al["sigma_u"])   # Q(310e6, "Pa")   — Ultimate tensile strength
print(al["rho"])       # Q(2700, "kg/m^3") — Density
print(al["nu"])        # 0.33             — Poisson's ratio
print(al["alpha"])     # Q(23.6e-6, "1/K") — Thermal expansion
print(al["k"])         # Q(167, "W/m/K")  — Thermal conductivity
print(al["cp"])        # Q(896, "J/kg/K") — Specific heat
```

### Available materials

| Name | Category |
|------|---------|
| `"Al-6061-T6"` | Aluminum alloy |
| `"Al-7075-T6"` | Aluminum alloy (high strength) |
| `"steel-1020"` | Mild steel |
| `"steel-4340"` | Alloy steel (high strength) |
| `"Ti-6Al-4V"` | Titanium alloy |
| `"Inconel-718"` | Nickel superalloy |
| `"CFRP-unidirectional"` | Carbon fiber composite |
| `"Kevlar-49"` | Aramid fiber |

### `materials.search(keyword)`

```python
materials.search("steel")
materials.search("titanium")
```

### Usage with structures RSQs

```python
mat = materials.get("Al-6061-T6")
E = float(mat["E"].si)       # 68.9e9 Pa
I = 1e-6                      # m^4

r = anvil.R.beam_deflection_cantilever(F_tip=5000, L_beam=1.5, E=E, I_moment=I)
print(r["deflection"])       # m

r = anvil.R.buckling_euler(E=E, I_moment=I, L_eff=1.5)
print(r["P_critical"])       # N
```

---

## `anvil.lookup()` — In-REPL Help

A quick-reference search across the full registry plus constants and fluid/material databases:

```python
anvil.lookup("pressure")
# Returns and prints all RSQs tagged or named with "pressure",
# plus relevant constants and fluid properties
```

This is the same as `anvil.search()` but with a more complete output format.

---

## Database Accuracy Notes

**Fluid properties:** All models are polynomial/power-law fits valid over the stated temperature range. Accuracy:
- Density (ideal gas): exact for ideal gases; ±2% for real gases away from saturation
- Viscosity (Sutherland): ±2% for most gases in stated range
- Conductivity (power law): ±5% for moderate temperatures

**For high-accuracy fluid properties** (near critical point, saturation, mixtures): use the CoolProp adapter.

**Material properties:** Single-temperature values from standard references. Temperature-dependent properties are not available — for thermal analysis requiring T-dependent E or σ_y, use external data.
