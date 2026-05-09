# Project Registry

A project registry is an isolated SQLite store for RSQs that are under development. It prevents polluting the global registry (`~/.anvil/registry.db`) while you iterate on new relations.

---

## Creating a Project

```python
proj = anvil.project("my_study", path="./work")
# Output: Project 'my_study' opened  (work/.anvil/project_my_study.db)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | required | Project name (used in DB filename) |
| `path` | `os.getcwd()` | Directory for `.anvil/` folder |

**Database location:** `{path}/.anvil/project_{name}.db`

Opening the same project twice (same name + path) reopens the existing database.

---

## Registering RSQs

```python
proj.push(
    obj,                 # function, Relation, System, or Quantity
    name=None,           # defaults to obj.__name__
    domain="",
    version="0.0.1",
    description="",
    author="",
    tags=None,
    tests=None,
    depends=None,
)
```

Accepts the same object types as `anvil.push()`.

```python
def rayleigh_ratios(M, gamma=1.4):
    g = float(gamma); M = float(M)
    gp1 = g + 1
    denom = 1 + g * M**2
    T_Tstar = (gp1 * M / denom)**2
    return {"T_Tstar": T_Tstar, "P_Pstar": gp1/denom}

proj.push(rayleigh_ratios,
          domain="aero.compressible",
          description="Rayleigh flow ratios",
          tags=["rayleigh", "compressible"])
# [my_study] Registered 'rayleigh_ratios' (R) in domain 'aero.compressible'.
```

**Origin:** Project RSQs have `origin="project"`.

---

## Using Project RSQs

### Direct call

```python
r = proj.R.rayleigh_ratios(M=0.5, gamma=1.4)
print(r["T_Tstar"])   # 0.790123
```

### In a System

```python
sys = anvil.system("duct")
sys.add("M", 0.5)
sys.add("gamma", 1.4)
sys.use(proj.R.rayleigh_ratios)    # pass the live Relation object
result = sys.solve_forward()
```

### Global RSQs still accessible

Project and global registries are fully independent. While a project is open, `anvil.R.*` still accesses global RSQs:

```python
# Global RSQs unaffected
anvil.R.isentropic_ratios(M=2.0)   # works fine
proj.R.rayleigh_ratios(M=0.5)      # project RSQ
```

---

## Listing and Searching

```python
proj.list()
# Project: my_study  (./work)
#
# Relations (2):
#   rayleigh_ratios              [aero.compressible]
#     Rayleigh flow ratios
#   rayleigh_heat                [aero.compressible]
#     Rayleigh flow with heat addition
#
# Total: 2 RSQs

proj.list(domain="aero.compressible")  # filter by domain
proj.list(rsq_type="R")                # filter by type

proj.search("rayleigh")
# [R] rayleigh_ratios              [rayleigh, compressible]
# [R] rayleigh_heat                [rayleigh, compressible, combustion]
```

---

## Removing RSQs

```python
proj.remove("old_draft")
# [my_study] Removed 'old_draft'.
```

---

## Promoting to Global Registry

When an RSQ is ready, promote it to the global registry:

```python
proj.promote("rayleigh_ratios")
# 'rayleigh_ratios' promoted from project 'my_study' to global registry.

# If the name already exists in global:
proj.promote("rayleigh_ratios", overwrite=True)   # replaces existing
proj.promote("rayleigh_ratios")                   # raises ValueError
```

```python
# Promote everything
proj.promote_all(overwrite=False)   # skips existing
proj.promote_all(overwrite=True)    # replaces existing
```

After promotion, the RSQ is accessible via `anvil.R.*`:

```python
anvil.R.rayleigh_ratios(M=0.5)   # now works globally
```

---

## Context Manager — Auto-route `anvil.push()`

The context manager routes `anvil.push()` calls to the project store automatically:

```python
with anvil.project("my_study", path="./work") as proj:
    # anvil.push() goes to project, not global
    @anvil.relation(domain="aero", register=False)
    def draft_relation(UA, C_min):
        return {"NTU": UA / C_min}

    proj.push(draft_relation)        # → project store
    anvil.R.isentropic_ratios(M=2)   # global still works

# Outside the with block — promote when satisfied
proj.promote("draft_relation")
```

**How it works internally:**
- `Project.__enter__()` calls `_set_active_project(self)` — sets a module-level `_active_project`
- `anvil.push()` checks `get_active_project()` — if set, routes to project store
- `Project.__exit__()` calls `_set_active_project(None)` — clears active project

**Warning:** `_active_project` is a module-level global. Nested `with anvil.project(...)` blocks are not safe — the inner one overrides the outer. Use explicit `proj.push()` for nested workflows.

---

## Full Workflow Example

From `examples/ex17_rayleigh_flow.py`:

```python
import anvil
from anvil import Q, solvers
import numpy as np

# 1. Define RSQs as plain Python functions
def rayleigh_ratios(M, gamma=1.4):
    g = float(gamma); M = float(M)
    gp1 = g + 1; denom = 1 + g * M**2
    T_Tstar = (gp1 * M / denom)**2
    T0_T0star = 2 * gp1 * M**2 * (1 + (g-1)/2*M**2) / denom**2
    return {"T0_T0star": T0_T0star, "T_Tstar": T_Tstar,
            "P_Pstar": gp1/denom}

def rayleigh_heat(M1, T01, P1, q_heat, cp, gamma=1.4):
    g = float(gamma); M1 = float(M1)
    T01 = float(getattr(T01, "si", T01))
    # ... (see ex17_rayleigh_flow.py for full implementation)
    return {"M2": M2, "T02": Q(T02, "K"), "P02_P01": P02/P01}

# 2. Push to project
proj = anvil.project("rayleigh_study", path="./rayleigh_work")
proj.push(rayleigh_ratios, domain="aero.compressible", tags=["rayleigh"])
proj.push(rayleigh_heat,   domain="aero.compressible", tags=["rayleigh"])

# 3. Use in System
duct = anvil.system("rayleigh_duct")
duct.add("M1", 0.3); duct.add("T01", 400.0, "K")
duct.add("P1", 200e3, "Pa"); duct.add("q_heat", 300e3, "J/kg")
duct.add("cp", 1005.0, "J/kg/K"); duct.add("gamma", 1.4)
duct.use(proj.R.rayleigh_heat)
result = duct.solve_forward()
# M2 = 0.445, T02 = 698.5 K, P02_P01 = 0.949

# 4. Sweep
q_choke = 757e3  # from rayleigh_ratios
sweep = duct.sweep("q_heat", np.linspace(0, 0.8*q_choke, 30), skip_errors=True)
sweep.summary(outputs=["M2", "T02", "P02_P01"])

# 5. Promote when ready
# proj.promote("rayleigh_ratios")
# proj.promote("rayleigh_heat")
```

---

## Project Object Attributes

```python
proj.name        # str — project name
proj._store      # Store — SQLite backend
proj._path       # Path — filesystem path
proj.R           # Namespace — project Relation access
proj.S           # Namespace — project System access
proj.Q           # Namespace — project Quantity access

repr(proj)       # <Project 'my_study': 2 RSQs at ./work>
```

---

## Comparison: Project vs Global Registry

| Feature | Global (`anvil.push`) | Project (`proj.push`) |
|---------|----------------------|----------------------|
| Database | `~/.anvil/registry.db` | `{path}/.anvil/project_{name}.db` |
| Scope | All sessions, all scripts | This project only |
| Access | `anvil.R.*` | `proj.R.*` |
| Origin | `"local"` | `"project"` |
| Shared | Yes (per user) | No |
| Lifetime | Until `anvil.registry.remove()` | Until `proj.remove()` or DB deleted |
| Promote to global | N/A | `proj.promote()` |
