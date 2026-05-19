"""
Example: 2D Euler CFD — Subsonic flow over a Gaussian bump
===========================================================

M = 0.5 air flow through a channel with a Gaussian bump on the lower wall.

Demonstrates:
    1. Loading mesh from .amesh coordinate file (written here, then re-read)
    2. Named boundary patches in the BCs dict
    3. Subsonic inlet / pressure outlet BCs (new BC types)
    4. PNG contour snapshots saved every N iterations (save_every)
    5. Mesh visualisation with patch labels
    6. Multi-field comparison plot at end
    7. Parallel Mach sweep via solver.as_relation()

Physics expected:
    • Flow accelerates and M increases over the bump crest
    • Pressure dip at crest, recovers downstream
    • No shock for M_inlet < 0.8 (purely subsonic)
"""

import sys, os

import numpy as np
import anvil
from anvil.cfd import CFDSolver, Mesh, MeshPatch, viz as cfd_viz
from anvil.cfd.bc import SubsonicInlet, SubsonicOutlet, SlipWall
from anvil.seed import seed; seed(force=True)
from anvil.registry import _rebuild_namespaces; _rebuild_namespaces()

# ─────────────────────────────────────────────────────────────────
# Parameters
# ─────────────────────────────────────────────────────────────────
M_inlet  = 0.5
gamma    = 1.4
R_gas    = 287.058
p0_inlet = 110_000.0   # Pa  (total pressure)
T0_inlet = 310.0       # K   (total temperature)

# Isentropic static conditions at inlet Mach 0.5
fac       = 1.0 + 0.5*(gamma-1)*M_inlet**2
p_inlet   = p0_inlet / fac**(gamma/(gamma-1))
T_inlet   = T0_inlet / fac
rho_inlet = p_inlet / (R_gas * T_inlet)
p_back    = p_inlet   # outlet back pressure = inlet static (isentropic channel, no net loss)

print("=" * 60)
print("  Subsonic Gaussian-bump channel  (M = 0.5)")
print("=" * 60)
print(f"\n  Inlet:  p0={p0_inlet:.0f} Pa  T0={T0_inlet:.1f} K  M={M_inlet}")
print(f"  Static: p={p_inlet:.1f} Pa  T={T_inlet:.2f} K  rho={rho_inlet:.4f} kg/m³")

# ─────────────────────────────────────────────────────────────────
# PART 1 — Build mesh and write .amesh file
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 1: Mesh generation and .amesh file I/O")
print("=" * 60)

out_dir = os.path.dirname(os.path.abspath(__file__))

mesh = Mesh.bump(
    length      = 2.0,
    height      = 0.5,
    nx          = 80,
    ny          = 30,
    bump_height = 0.10,
    bump_x0     = 1.0,
    bump_sigma  = 0.20,
    title       = "subsonic_bump",
    patches     = {
        "inlet":   MeshPatch("left",  0, 30),
        "outlet":  MeshPatch("right",  0, 30),
        "wall":    MeshPatch("bottom", 0, 80),
        "ceiling": MeshPatch("top", 0, 80),
    }
)

# Write then re-read the mesh (demonstrates file I/O)
amesh_path = os.path.join(out_dir, "bump.amesh")
mesh.to_file(amesh_path)
print(f"\n  Mesh written to: {amesh_path}")

mesh = Mesh.from_file(amesh_path)
mesh.info()

# Visualise mesh (saved to PNG, not shown interactively)
mesh_png = os.path.join(out_dir, "bump_mesh.png")
mesh.plot(show=False, save_path=mesh_png, show_patches=True, show_mesh=True)
print(f"  Mesh plot saved: {mesh_png}")

# ─────────────────────────────────────────────────────────────────
# PART 2 — Solver setup
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 2: Solver setup and run")
print("=" * 60)

bcs = {
    "inlet":   SubsonicInlet(M=M_inlet, p0=p0_inlet, T0=T0_inlet, gamma=gamma, R_gas=R_gas),
    "outlet":  SubsonicOutlet(p_back=p_back, gamma=gamma),
    "wall":    SlipWall(),
    "ceiling": SlipWall(),
}

solver = CFDSolver(
    mesh        = mesh,
    bcs         = bcs,
    gamma       = gamma,
    R_gas       = R_gas,
    flux_scheme = "roe",
    order       = 2,
    time_scheme = "rk4",
    cfl         = 0.3,
    transient   = False,
)
solver.initialize(M=M_inlet, p=p_inlet, T=T_inlet)

snap_dir = os.path.join(out_dir, "bump_snapshots")
print(f"\n  Running ({mesh.nx}×{mesh.ny} cells, M={M_inlet}, 2nd-order Roe)...")
print(f"  Saving Mach contour snapshots to: {snap_dir}/")

result = solver.run(
    max_iter    = 3000,
    tol         = 1e-3,    # subsonic fixed-ghost inlet converges slowly
    monitor     = True,
    verbose     = True,
    print_every = 300,
    save_every  = 600,      # save PNG every 600 iterations
    save_field  = "M",
    save_dir    = snap_dir,
    save_vmin   = 0.3,      # fixed scale -- all frames comparable
    save_vmax   = 1.0,
)

result.summary()

# ─────────────────────────────────────────────────────────────────
# PART 3 — Post-processing
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 3: Post-processing and comparison")
print("=" * 60)

# Centreline Mach number
j_mid   = mesh.ny // 2
M_up    = result.M[:mesh.nx // 2, j_mid].mean()
M_crest = result.M[mesh.nx // 2 - 5 : mesh.nx // 2 + 5, 0].mean()  # near wall at crest
p_crest = result.p[mesh.nx // 2 - 5 : mesh.nx // 2 + 5, 0].mean()
p_down  = result.p[mesh.nx // 2:, j_mid].mean()

print(f"\n  Upstream M (avg):     {M_up:.4f}  (inlet target: {M_inlet})")
print(f"  M near bump crest:    {M_crest:.4f}  (expected > inlet M)")
print(f"  p near bump crest:    {p_crest:.1f} Pa  (expected < {p_inlet:.1f} Pa)")
print(f"  p downstream (avg):   {p_down:.1f} Pa  (expected ~ {p_back:.1f} Pa)")
print(f"  p/p_back at outlet:   {p_down/p_back:.4f}  (ideal: 1.0000)")

# Multi-field contour panel
panel_png = os.path.join(out_dir, "bump_fields.png")
cfd_viz.multi_field(result, fields=["M", "p", "T", "rho"],
                    show=False, save_path=panel_png)
print(f"\n  Multi-field plot saved: {panel_png}")

# Residual convergence
conv_png = os.path.join(out_dir, "bump_convergence.png")
cfd_viz.convergence_png(result.history, conv_png, title="Bump: residual convergence")
print(f"  Convergence plot saved: {conv_png}")

# VTK for ParaView
vtk_path = os.path.join(out_dir, "bump_flow.vtk")
result.to_vtk(vtk_path)
print(f"  VTK output saved: {vtk_path}")

# ─────────────────────────────────────────────────────────────────
# PART 4 — Mach sweep via as_relation() + parallel
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 4: Mach sweep (parallel=2) using solver as Anvil Relation")
print("=" * 60)

sweep_mesh = Mesh.bump(
    length=2.0, height=0.5, nx=40, ny=15,
    bump_height=0.10, bump_x0=1.0, bump_sigma=0.20,
    patches={
        "inlet":   MeshPatch("left",  0, 15),
        "outlet":  MeshPatch("right",  0, 15),
        "wall":    MeshPatch("bottom", 0, 40),
        "ceiling": MeshPatch("top", 0, 40),
    }
)

def bump_bcs(M, p0, T0, alpha=0.0):
    g = gamma; R = R_gas
    fac = 1.0 + 0.5*(g-1)*M**2
    p_s = p0 / fac**(g/(g-1))   # isentropic static at inlet M
    return {
        "inlet":   SubsonicInlet(M=M, p0=p0, T0=T0, gamma=g, R_gas=R),
        "outlet":  SubsonicOutlet(p_back=p_s, gamma=g),  # matched back pressure
        "wall":    SlipWall(),
        "ceiling": SlipWall(),
    }

sweep_solver = CFDSolver(
    mesh=sweep_mesh, bcs=bump_bcs(0.5, p0_inlet, T0_inlet),
    gamma=gamma, R_gas=R_gas, flux_scheme="roe", order=2, cfl=0.3
)

cfd_rel = sweep_solver.as_relation(
    inputs     = ["M_inf", "p_inf", "T_inf"],
    outputs    = ["M_max", "p_wall"],
    name       = "bump_euler",
    bc_factory = bump_bcs,
    run_kwargs = {"max_iter": 1000, "tol": 1e-3, "verbose": False},
)

sweep_sys = anvil.system("bump_mach_sweep")
sweep_sys.add("M_inf", 0.5)
sweep_sys.add("p_inf",  p0_inlet)
sweep_sys.add("T_inf",  T0_inlet)
sweep_sys.use(cfd_rel)

mach_vals = np.array([0.3, 0.4, 0.5, 0.6])
print(f"\n  Sweeping M = {mach_vals}  (parallel=2)...")
sweep = sweep_sys.sweep("M_inf", mach_vals, parallel=2, skip_errors=True)
sweep.summary(outputs=["M_max", "p_wall"])

# ─────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────
for f in ["bump.amesh", "bump_flow.vtk"]:
    fp = os.path.join(out_dir, f)
    if os.path.exists(fp):
        os.remove(fp)

print("\n" + "=" * 60)
print("  Done. Output files:")
print(f"    {mesh_png}       — mesh + patch labels")
print(f"    {panel_png}      — M/p/T/rho contours")
print(f"    {conv_png}       — residual convergence")
print(f"    {snap_dir}/      — Mach snapshots every 500 iters")
print("=" * 60)
