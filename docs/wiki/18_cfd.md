# 2D Euler CFD Solver

`anvil.cfd` is a native finite-volume CFD solver for the 2D inviscid (Euler) equations on structured body-fitted meshes. It handles subsonic, transonic, and supersonic flows including normal and oblique shocks.

The key integration point: `solver.as_relation()` wraps the CFD result into an Anvil Relation — making it fully composable with Systems, sweepable over Mach number or geometry, and registerable like any other RSQ.

---

## Quick Start

```python
from anvil.cfd import CFDSolver, Mesh
from anvil.cfd.bc import SupersonicInlet, SupersonicOutlet, SlipWall, Farfield

# 1. Build mesh
mesh = Mesh.wedge(half_angle_deg=10, chord=1.0, height=0.8, nx=80, ny=40)

# 2. Boundary conditions
M_inf, p_inf, T_inf = 2.0, 101325.0, 300.0
bcs = {
    "west":  SupersonicInlet(M=M_inf, p=p_inf, T=T_inf),
    "east":  SupersonicOutlet(),
    "south": SlipWall(),
    "north": Farfield(M=M_inf, p=p_inf, T=T_inf),
}

# 3. Create and initialize solver
solver = CFDSolver(mesh, bcs, gamma=1.4, flux_scheme="roe", order=2, cfl=0.5)
solver.initialize(M=M_inf, p=p_inf, T=T_inf, alpha_deg=0.0)

# 4. Run
result = solver.run(max_iter=5000, tol=1e-6, monitor=True, print_every=200)
result.summary()

# 5. Export
result.to_vtk("wedge.vtk")         # open in ParaView
result.to_tecplot("wedge.dat")     # open in Tecplot
```

---

## Mesh

All mesh types are structured (i, j indexing). Factory methods return a `StructuredMesh2D` object.

### Factory Methods

```python
from anvil.cfd import Mesh

# Flat-plate / generic rectangular domain
mesh = Mesh.cartesian(x_span=(0, 2), y_span=(0, 1), nx=100, ny=50)

# Wedge (sharp leading edge, supersonic flows)
mesh = Mesh.wedge(half_angle_deg=10, chord=1.0, height=0.8, nx=80, ny=40)

# Gaussian bump (transonic channel flow, shock-induced separation)
mesh = Mesh.bump(length=3.0, height=1.0, nx=120, ny=60,
                 bump_height=0.1, bump_center=1.0, bump_width=0.3)

# Compression ramp
mesh = Mesh.compression_ramp(length=2.0, height=1.0,
                              ramp_angle_deg=15, nx=100, ny=50)

# From custom coordinate arrays (body-fitted grid generation)
mesh = Mesh.from_arrays(X, Y)   # X, Y: (nx+1, ny+1) node coordinates

# Load from file (previously saved mesh)
mesh = Mesh.from_file("mesh.msh")
```

### Mesh Info and Plotting

```python
mesh.info()       # prints: nx, ny, patch names, bounding box
mesh.plot()       # matplotlib visualization of grid lines
mesh.to_file("mesh.msh")
```

### Patch Names

Each mesh factory assigns patch names to the four boundaries:

| Factory | west | east | south | north |
|---------|------|------|-------|-------|
| `cartesian` | inlet | outlet | wall | top |
| `wedge` | west | east | south | north |
| `bump` | west | east | south | north |
| `compression_ramp` | west | east | south | north |

Override with `patches={"west": MeshPatch(...), ...}` argument.

---

## Boundary Conditions

```python
from anvil.cfd.bc import (
    SupersonicInlet, SupersonicOutlet,
    SubsonicInlet, SubsonicOutlet,
    SlipWall, Farfield, BackPressure, MassFlowInlet,
)
```

| BC Class | Use Case | Required args |
|----------|----------|---------------|
| `SupersonicInlet` | M > 1 inflow, all characteristics enter | `M, p, T` |
| `SupersonicOutlet` | M > 1 outflow, all characteristics leave | — |
| `SubsonicInlet` | M < 1 inflow (stagnation BCs) | `M, p0, T0` |
| `SubsonicOutlet` | M < 1 outflow, back-pressure specified | `p_back` |
| `SlipWall` | Inviscid wall (tangential flow enforced) | — |
| `Farfield` | Far-field / freestream condition | `M, p, T` |
| `BackPressure` | Pressure outlet (subsonic) | `p_back` |
| `MassFlowInlet` | Specified mass flow rate inlet | `mdot, T, area` |

**Example — subsonic channel with back-pressure:**

```python
bcs = {
    "west":  SubsonicInlet(M=0.3, p0=110000, T0=310),
    "east":  BackPressure(p_back=101325),
    "south": SlipWall(),
    "north": SlipWall(),
}
```

---

## CFDSolver

```python
solver = CFDSolver(
    mesh,
    bcs,
    gamma      = 1.4,       # ratio of specific heats
    R_gas      = 287.058,   # specific gas constant [J/kg/K]
    flux_scheme= "roe",     # "roe" or "hllc"
    order      = 2,         # 1 = first-order upwind, 2 = MUSCL (2nd order)
    cfl        = 0.5,       # CFL number (reduce to 0.3 for stability near shocks)
    time_scheme= "rk4",     # "rk4" or "euler" (RK4 more stable)
)

solver.initialize(M=2.0, p=101325, T=300, alpha_deg=0.0)
```

### Running

```python
result = solver.run(
    max_iter    = 5000,    # iteration limit
    tol         = 1e-6,   # L2 residual convergence threshold
    monitor     = True,   # print residual every print_every iterations
    print_every = 200,    # print interval
    restart     = None,   # path to .npz restart file (or None)
)
```

**Convergence output:**

```
iter     0   res = 2.4812e+00
iter   200   res = 4.3271e-01
iter   400   res = 6.1843e-02
...
iter  3200   res = 8.4312e-07
Converged in 3246 iterations (res = 9.98e-07)
```

### Restart

```python
# Save state mid-run
result.to_restart("checkpoint.npz")

# Resume from checkpoint
result2 = solver.run(max_iter=5000, restart="checkpoint.npz")
```

---

## CFDResult

Post-processing is done on the `CFDResult` object returned by `solver.run()`.

```python
result.summary()
# Prints: converged flag, iterations, final residual,
#         freestream conditions, min/max field values

# Wall pressure distribution (south boundary by default)
p_wall = result.wall_pressure(side="south")
# returns ndarray (nx,) of static pressure along wall

# Aerodynamic force coefficients
CL, CD = result.force_coefficients(
    p_ref=p_inf, rho_ref=rho_inf, V_ref=V_inf,
    S_ref=1.0,         # reference area [m²]
    side="south",      # which boundary to integrate
    alpha_deg=0.0,     # angle of attack (for CL/CD decomposition)
)

# Field arrays
fields = result._field_dict()
# {"rho": (nx,ny), "u": (nx,ny), "v": (nx,ny), "p": (nx,ny),
#  "T": (nx,ny), "M": (nx,ny), "p0": (nx,ny)}
```

### Export

```python
result.to_vtk("solution.vtk")         # ParaView — rho, u, v, p, T, M
result.to_tecplot("solution.dat")     # Tecplot ASCII
result.to_restart("solution.npz")     # numpy restart file
```

---

## Integration with Anvil System

`solver.as_relation()` converts the CFD solver into a standard Anvil Relation. Scalar Q inputs and scalar Q outputs are wired as normal workspace quantities.

```python
rel = solver.as_relation(
    inputs  = ["M_inf", "p_inf", "T_inf"],
    outputs = ["CL", "CD", "M_max", "p_wall_max"],
    name    = "wedge_cfd",
)

# Use in a System
sys = anvil.System("aero_study")
sys.add("M_inf",  2.0)
sys.add("p_inf",  101325.0, "Pa")
sys.add("T_inf",  300.0,    "K")
sys.use(rel)

result = sys.solve_forward()
print(result["CL"], result["CD"])

# Sweep Mach number — runs CFD at each point
import numpy as np
sweep = sys.sweep("M_inf", np.linspace(1.5, 3.5, 8), parallel=4)
sweep.summary(outputs=["M_inf", "CL", "CD"])
```

> **Note on `parallel`:** Each parallel worker gets an independent solver copy. Stateless — safe for parallel sweeps.

---

## Supported Mesh Configurations & Flows

| Configuration | Mesh factory | Typical use |
|---------------|-------------|-------------|
| 2D wedge | `Mesh.wedge()` | Oblique shock angle, wave drag |
| Channel bump | `Mesh.bump()` | Transonic shock / shock-boundary layer |
| Compression ramp | `Mesh.compression_ramp()` | Ramp-induced separation |
| Flat plate | `Mesh.cartesian()` | Subsonic flow, generic geometry |
| Custom body-fitted | `Mesh.from_arrays()` | Airfoils, nozzles, any structured grid |

**Supported flow regimes:**

| Regime | M range | Notes |
|--------|---------|-------|
| Subsonic | M < 0.8 | Smooth convergence |
| Transonic | 0.8 < M < 1.2 | May need CFL ≤ 0.3, order=1 near shock |
| Supersonic | M > 1.2 | Fastest convergence, clean shocks |
| Hypersonic | M > 5 | Needs reduced CFL (0.2–0.3), gamma correction |

---

## Visualization — anvil.cfd.viz

`anvil.cfd.viz` provides filled contour plots and multi-field panels for `CFDResult` objects. All plots use monospace fonts. Fixed colorbar limits (`vmin`/`vmax`) keep successive frames directly comparable — essential for animations or batch sweeps.

```python
from anvil.cfd import viz as cfd_viz

# Single-field contour (opens matplotlib window)
cfd_viz.contour(result, "M")                           # Mach number, auto scale
cfd_viz.contour(result, "p", vmin=90000, vmax=180000)  # fixed colorbar

# Save to PNG without opening a window
cfd_viz.save_png(result, "M", "mach.png", vmin=0, vmax=2.5)

# 2×2 multi-field panel with per-field colorbar limits
fig, axes = cfd_viz.multi_field(
    result, ["M", "p", "T", "rho"],
    vmin_map={"p": (90e3, 200e3), "M": (0, 3)},
    save_path="overview.png",
)

# Mesh + named boundary patch labels
cfd_viz.mesh_plot(mesh)

# Normalised residual history PNG (res / res0)
cfd_viz.convergence_png(result.history, "convergence.png")
```

**Available fields:** `p` (pressure), `T` (temperature), `M` (Mach), `rho` (density), `u`, `v` (velocity components), `cp` (pressure coefficient), `pt` (total pressure).

**Function reference:**

| Function | Description |
|----------|-------------|
| `contour(result, field, vmin, vmax, show_patches, save_path)` | Filled contour of one field; overlays boundary patch labels |
| `save_png(result, field, path, vmin, vmax)` | Non-interactive contour save — no window |
| `multi_field(result, fields, vmin_map, save_path)` | 2×2 (or 1×N) panel, optional per-field limits |
| `mesh_plot(mesh)` | Grid lines + named boundary patch labels |
| `convergence_png(history, path)` | Normalised residual (res/res0) saved to PNG |

**Tip — animations:** Run `save_png` inside a loop over `save_every` restart frames. Pass the same `vmin`/`vmax` each call so all frames share a colorbar scale.

```python
for i, r in enumerate(solver.snapshots):
    cfd_viz.save_png(r, "M", f"frame_{i:04d}.png", vmin=0, vmax=2.5)
```

---

## Limitations

- **2D only** — no 3D support
- **Structured meshes only** — no unstructured, no AMR
- **Euler only** — no viscous (Navier-Stokes), no turbulence
- **Ideal gas only** — no real gas EOS, no equilibrium chemistry
- **Dirichlet / ghost-cell BCs only** — no adjoint-compatible, no PML far-field
- For viscous flow, combustion, or production-quality results: use OpenFOAM via a CLI adapter

**Extensibility notes (from module docstring):**
- Viscous: add `viscous_flux_2d()` in `flux.py`; call after inviscid in `solver._residual()`
- 3D: add k-index in mesh, w-velocity, and third face sweep in solver
- Real gas: replace ideal-gas EOS calls with custom EOS object
