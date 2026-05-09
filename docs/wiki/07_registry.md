# Registry

The Anvil registry is a SQLite database at `~/.anvil/registry.db`. It stores RSQs (Relations, Systems, Quantities) with metadata, source code, and version info. It's auto-seeded with 57 built-in RSQs on first import.

---

## RSQ Types

| Type | Description | Accessed via |
|------|-------------|-------------|
| `"R"` | Relation — a computation function | `anvil.R.<name>` |
| `"S"` | System — a pre-built solvable problem | `anvil.S.<name>` |
| `"Q"` | Quantity — a named constant | `anvil.QDB.<name>` |

---

## Exploring the Registry

### `anvil.registry.list()` — list RSQs

```python
import anvil

anvil.registry.list()                      # all RSQs
anvil.registry.list(domain="aero")         # filter by domain
anvil.registry.list(type="R")             # only Relations
anvil.registry.list(tag="combustion")      # filter by tag
```

**Output (excerpt):**
```
[R] isentropic_ratios             [aero.compressible]  v0.1.0  (builtin)
    Isentropic flow relations: T0/T, P0/P, rho0/rho

[R] normal_shock                  [aero.compressible]  v0.1.0  (builtin)
    Normal shock relations
...
```

### `anvil.registry.search(keyword)` — fuzzy search

Searches name, description, domain, and tags:

```python
anvil.registry.search("shock")
anvil.registry.search("pid")
anvil.registry.search("rayleigh")
```

**Output:**
```
[R] normal_shock                   [compressible, shock]
       Normal shock relations
[R] oblique_shock                  [compressible, shock, oblique, wedge]
       2D oblique shock: shock angle, downstream M, pressure/temperature ratios

  2 result(s)
```

### `anvil.registry.info(name)` — detailed metadata

```python
anvil.registry.info("isentropic_ratios")
```

**Output:**
```
  isentropic_ratios
  --------------------------------------------------
  Domain:      aero.compressible
  Version:     0.1.0
  Origin:      builtin
  Author:      (none)
  Description: Isentropic flow relations: T0/T, P0/P, rho0/rho
  Tags:        compressible, isentropic, mach
  Inputs:
    M          (no default)
    gamma      default=1.4
```

### `anvil.registry.export(name)` — print source code

```python
anvil.registry.export("isentropic_ratios")
```

**Output:**
```python
# RSQ: isentropic_ratios (v0.1.0, R)
# Domain: aero.compressible
# Origin: builtin
# Tags: compressible, isentropic, mach

def isentropic_ratios(M, gamma=1.4):
    T_ratio = 1 + ((gamma - 1) / 2) * M**2
    P_ratio = T_ratio ** (gamma / (gamma - 1))
    rho_ratio = T_ratio ** (1 / (gamma - 1))
    return {"T0_T": T_ratio, "P0_P": P_ratio, "rho0_rho": rho_ratio}
export = isentropic_ratios
```

### `anvil.registry.remove(name)`

```python
anvil.registry.remove("my_rsq")
# Removed 'my_rsq'.
```

Permanently deletes from the SQLite database. Cannot be undone (re-push to restore).

---

## Registering RSQs

### `anvil.push()` — register

```python
anvil.push(
    obj,                    # function, Relation, System, or Quantity
    name=None,              # defaults to function.__name__
    domain="",              # hierarchical: "aero.compressible"
    version="0.0.1",
    description="",
    author="",
    tags=None,              # list of strings
    tests=None,             # dict of test cases (future feature)
    depends=None,           # list of dependency RSQ names
)
```

```python
def my_drag(CL, CD0, AR, e=0.85):
    CDi = CL**2 / (3.14159 * AR * e)
    return {"CD": CD0 + CDi, "CDi": CDi}

anvil.push(my_drag,
    domain="aero",
    description="Drag polar with induced drag",
    tags=["aerodynamics", "drag", "induced"],
    version="1.0.0",
)

# Now available globally
anvil.R.my_drag(CL=0.5, CD0=0.02, AR=8)
```

**Origin:** RSQs pushed via `anvil.push()` have `origin="local"`. Built-ins have `origin="builtin"`.

**Duplicate warning:** Pushing a name that already exists in the local registry raises `UserWarning`. Use `anvil.update()` to signal intentional overwrite — `update()` never shows this warning.

**Namespace rebuild:** `anvil.push()` and `anvil.update()` both rebuild `anvil.R.*` / `anvil.S.*` / `anvil.QDB.*` automatically. `anvil.R.<name>` is accessible immediately after the call — no session restart needed:

```python
anvil.push(my_func, name="my_rsq")
anvil.R.my_rsq(x=1.0)   # works immediately
```

### `anvil.update()` — update existing

```python
anvil.update(
    obj,
    name=None,
    domain=None,         # None = keep existing
    version=None,        # None = keep existing
    description=None,
    author=None,
    tags=None,
)
```

```python
# Fix a bug in my_drag
def my_drag_v2(CL, CD0, AR, e=0.85):
    CDi = CL**2 / (3.14159 * AR * e)
    CD = CD0 + CDi
    LoD = CL / CD
    return {"CD": CD, "CDi": CDi, "LoD": LoD}

anvil.update(my_drag_v2, name="my_drag", version="1.1.0")
# Updated 'my_drag'.
```

`update()` is semantically "intentional overwrite" — no duplicate warning. Merges only the fields you pass; omitted fields keep their current values. Rebuilds `anvil.R.*` automatically.

---

## Using Registry RSQs

### Dot-namespace access

```python
anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
# → {"T0_T": 1.8, "P0_P": 7.824, "rho0_rho": 4.347}

anvil.S.rocket_nozzle.copy()
# → deep copy of the pre-built System

anvil.QDB.g0
# → Q(9.80665, "m/s^2")  (standard gravity)
```

### String lookup in System

```python
sys.use("isentropic_ratios")
sys.use("normal_shock", map={"M1": "M_upstream"})
```

### `anvil.R.<name>` vs `anvil.registry.search()`

- `anvil.R.name` — attribute access, returns the live Relation/System/Quantity object
- `anvil.registry.search("name")` — returns metadata records (dicts from SQLite), not live objects

---

## `anvil.check()` — Health Check

```python
report = anvil.check("isentropic_ratios")
# or
report = anvil.check("rocket_nozzle")
# or
report = anvil.check(my_relation_object)
```

**Output for a Relation:**
```
============================================================
  anvil.check('isentropic_ratios')  [PASS]
============================================================
  Type:        Relation
  Domain:      aero.compressible
  Description: Isentropic flow relations: T0/T, P0/P, rho0/rho
  Version:     0.1.0
  Inputs:      M, gamma
  Outputs:     P0_P, T0_T, rho0_rho
  Defaults:    gamma=1.4

  --- Test Run ---
    T0_T: 1.2
    P0_P: 1.8929291587378542
    rho0_rho: 1.5774409656148785

  No issues found.
============================================================
```

**Return value:** dict with keys:

| Key | Type | Description |
|-----|------|-------------|
| `"ok"` | bool | Overall health |
| `"name"` | str | RSQ name |
| `"type"` | str | "R", "S", "Q" |
| `"inputs"` | list | Input names |
| `"outputs"` | list | Output names |
| `"defaults"` | dict | Default values |
| `"depends"` | list | Dependency names |
| `"tree"` | str | Printable dependency tree |
| `"issues"` | list | Problems found |
| `"test_result"` | dict | Test run outputs |

**`verbose=False`** — suppresses print, returns report dict only:

```python
report = anvil.check("isentropic_ratios", verbose=False)
report["ok"]       # True
report["inputs"]   # ['M', 'gamma']
report["outputs"]  # ['P0_P', 'T0_T', 'rho0_rho']
```

---

## `anvil.fetch()` — Load by Name/Domain/Tag

```python
anvil.fetch("pid_output")          # by name
anvil.fetch("aero.compressible")   # by domain — loads all in that domain
anvil.fetch("combustion")          # by tag
```

Primarily useful for refreshing the namespace after direct database manipulation. Not needed after `anvil.push()` or `anvil.update()` — those rebuild automatically.

---

## Store — SQLite Backend

The underlying store is `anvil.registry.store.Store`, backed by `~/.anvil/registry.db`.

### Schema (RSQ table)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | TEXT | RSQ name (unique per origin) |
| `type` | TEXT | "R", "S", "Q" |
| `domain` | TEXT | Hierarchical domain string |
| `version` | TEXT | Semantic version |
| `description` | TEXT | Human description |
| `author` | TEXT | Author name |
| `source` | TEXT | Python source code string |
| `metadata` | JSON | Input/output specs |
| `tests` | JSON | Test cases |
| `hash` | TEXT | SHA-256 of source |
| `origin` | TEXT | "builtin", "local", "project" |
| `created_at` | TEXT | ISO timestamp |
| `updated_at` | TEXT | ISO timestamp |

Plus `tags` and `dependencies` tables linked by foreign key.

### Upsert behavior

`store.put()` upserts on `(name, origin)`. Two RSQs with the same name but different origins coexist. When `store.get(name)` is called, local-origin RSQs take priority over builtin-origin RSQs with the same name.

---

## Seeding

The registry is seeded with 57 built-in RSQs via `anvil.seed.seed()` on first import:

```python
from anvil.seed import seed
seed()          # skips if all builtins already present
seed(force=True)  # always upserts all builtins
```

**Seed logic (post-fix):** Compares `{e["name"] for e in _SEED_ENTRIES}` against existing builtin-origin names in the DB. Seeds only if builtins are missing. This ensures new RSQs added to `seed.py` are picked up on next import without nuking user's local RSQs.

---

## Domain Conventions

Domains are hierarchical dotted strings. Convention used in built-ins:

| Domain | Contents |
|--------|---------|
| `const` | Physical constants |
| `aero` | General aerodynamics |
| `aero.atmosphere` | ISA atmosphere |
| `aero.compressible` | Isentropic, shock, Rayleigh |
| `aero.performance` | Lift, drag, range |
| `propulsion` | Nozzle, thrust, Isp |
| `thermo` | Ideal gas, viscosity |
| `heat_transfer` | Conduction, convection, radiation |
| `structures` | Stress, beam, buckling |
| `controls` | PID, step response, stability |
| `materials` | Fatigue, fracture, composites |
| `orbital` | Vis-viva, Hohmann, period |

User domains can be any string; recommended to follow the `category.subcategory` pattern.
