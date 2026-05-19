"""
Example: 2D Euler CFD — Supersonic flow over a compression ramp
===============================================================

M = 2.5 flow over a compression ramp (lower wall turns up 12deg).
Creates an oblique shock from the ramp corner that reflects off the
upper wall (slip-wall reflection gives a second oblique shock).

Demonstrates:
    1. Compression-ramp mesh (smooth tanh wall transition)
    2. Named patches: inlet / outlet / ramp / ceiling
    3. Split lower-wall patches: "flat_wall" + "ramp" (different colours)
    4. Mesh file I/O: write and re-read .amesh
    5. Mesh visualisation
    6. save_every PNG snapshots
    7. Parallel Mach/angle sweep using solver.as_relation()

Physics expected:
    • Oblique shock from ramp foot → deflects flow by ramp_angle_deg
    • Reflected shock from upper wall
    • Mach number drops across each shock; pressure rises
    • Analytical check via anvil.R.oblique_shock
"""

import sys, os

import numpy as np
import anvil
from anvil.cfd import CFDSolver, Mesh, MeshPatch, viz as cfd_viz
from anvil.cfd.bc import SupersonicInlet, SupersonicOutlet, SlipWall
from anvil.seed import seed; seed(force=True)
from anvil.registry import _rebuild_namespaces; _rebuild_namespaces()

# ─────────────────────────────────────────────────────────────────
# Parameters
# ─────────────────────────────────────────────────────────────────
M_inf       = 2.5
theta_deg   = 12.0      # ramp angle
gamma       = 1.4
R_gas       = 287.058
p_inf       = 101_325.0
T_inf       = 300.0
length      = 2.0
height      = 0.6
ramp_x0     = 0.6       # ramp starts here

print("=" * 60)
print(f"  Supersonic compression ramp  (M={M_inf}, theta={theta_deg}deg)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# Analytical check (oblique shock at ramp foot)
# ─────────────────────────────────────────────────────────────────
r = anvil.R.oblique_shock(M1=M_inf, theta_deg=theta_deg, gamma=gamma)
print(f"\n  Analytical oblique shock (ramp foot):")
print(f"  Shock angle beta   = {r['beta_deg']:.3f} deg")
print(f"  Downstream M2   = {r['M2']:.4f}")
print(f"  p2/p1           = {r['p2_p1']:.4f}")
print(f"  Attached:         {r['attached']}")

if r['attached']:
    # Second shock: reflected off upper wall (same theta, M2 incoming)
    r2 = anvil.R.oblique_shock(M1=r['M2'], theta_deg=theta_deg, gamma=gamma)
    print(f"\n  Reflected shock (upper wall):")
    print(f"  M3 = {r2['M2']:.4f}   p3/p1 = {r['p2_p1']*r2['p2_p1']:.4f}")

# ─────────────────────────────────────────────────────────────────
# PART 1 — Mesh
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 1: Mesh with named patches (flat_wall + ramp)")
print("=" * 60)

# nx cells; ramp starts at cell i_ramp
nx, ny = 80, 30
i_ramp = int(nx * ramp_x0 / length)   # first ramp cell

patches = {
    "inlet":     MeshPatch("left",  0, ny),
    "outlet":    MeshPatch("right",  0, ny),
    "flat_wall": MeshPatch("bottom", 0, i_ramp),
    "ramp":      MeshPatch("bottom", i_ramp, nx),
    "ceiling":   MeshPatch("top", 0, nx),
}

mesh = Mesh.compression_ramp(
    length          = length,
    height          = height,
    ramp_x0         = ramp_x0,
    ramp_angle_deg  = theta_deg,
    nx              = nx,
    ny              = ny,
    title           = "supersonic_ramp",
    patches         = patches,
)

out_dir = os.path.dirname(os.path.abspath(__file__))
amesh_path = os.path.join(out_dir, "ramp.amesh")
mesh.to_file(amesh_path)
mesh = Mesh.from_file(amesh_path)   # round-trip test
mesh.info()

mesh_png = os.path.join(out_dir, "ramp_mesh.png")
mesh.plot(show=False, save_path=mesh_png)
print(f"  Mesh plot saved: {mesh_png}")

# ─────────────────────────────────────────────────────────────────
# PART 2 — Solve
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 2: Solver run")
print("=" * 60)

bcs = {
    "inlet":     SupersonicInlet(M=M_inf, p=p_inf, T=T_inf, gamma=gamma, R_gas=R_gas),
    "outlet":    SupersonicOutlet(),
    "flat_wall": SlipWall(),
    "ramp":      SlipWall(),
    "ceiling":   SlipWall(),
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
solver.initialize(M=M_inf, p=p_inf, T=T_inf)

snap_dir = os.path.join(out_dir, "ramp_snapshots")
print(f"\n  Running ({mesh.nx}×{mesh.ny} cells, Roe, 2nd order)...")
result = solver.run(
    max_iter    = 2000,
    tol         = 1e-4,
    monitor     = True,
    verbose     = True,
    print_every = 250,
    save_every  = 500,
    save_field  = "p",
    save_dir    = snap_dir,
    save_vmin   = 100_000,   # fixed scale for all frames
    save_vmax   = 430_000,
)

result.summary()

# ─────────────────────────────────────────────────────────────────
# PART 3 — Comparison
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 3: Analytical vs Numerical comparison")
print("=" * 60)

# Sample downstream region (right half, lower half — behind first shock)
ds_i = slice(nx // 2, nx)
ds_j = slice(0, ny // 4)

M_ds  = result.M[ds_i, ds_j].mean()
p_ds  = result.p[ds_i, ds_j].mean()

if r['attached']:
    print(f"\n  {'':25s}  {'Analytical':>12s}  {'Numerical':>12s}  {'Error':>8s}")
    M_an = r['M2']; p_an = p_inf * r['p2_p1']
    print(f"  {'p2 [Pa]':25s}  {p_an:>12.1f}  {p_ds:>12.1f}  "
          f"{abs(p_ds-p_an)/p_an*100:>7.2f}%")
    print(f"  {'M2':25s}  {M_an:>12.4f}  {M_ds:>12.4f}  "
          f"{abs(M_ds-M_an)/M_an*100:>7.2f}%")
    print("  (Numerical value is area-averaged; boundary-layer and mesh effects)")

# ─────────────────────────────────────────────────────────────────
# PART 4 — Save output files
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 4: Output files")
print("=" * 60)

panel_png = os.path.join(out_dir, "ramp_fields.png")
cfd_viz.multi_field(result, fields=["M", "p", "T", "rho"],
                    show=False, save_path=panel_png)
print(f"  Multi-field plot: {panel_png}")

conv_png = os.path.join(out_dir, "ramp_convergence.png")
cfd_viz.convergence_png(result.history, conv_png, "Ramp: residual convergence")
print(f"  Convergence plot: {conv_png}")

vtk_path = os.path.join(out_dir, "ramp_flow.vtk")
result.to_vtk(vtk_path)
print(f"  VTK for ParaView: {vtk_path}")

# ─────────────────────────────────────────────────────────────────
# PART 5 — Parallel ramp-angle sweep
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 5: Ramp-angle sweep (parallel=2)")
print("=" * 60)

def make_ramp_mesh(theta):
    i_r = int(40 * ramp_x0 / length)
    return Mesh.compression_ramp(
        length=length, height=height, ramp_x0=ramp_x0,
        ramp_angle_deg=theta, nx=40, ny=15,
        patches={
            "inlet":     MeshPatch("left",  0, 15),
            "outlet":    MeshPatch("right",  0, 15),
            "flat_wall": MeshPatch("bottom", 0, i_r),
            "ramp":      MeshPatch("bottom", i_r, 40),
            "ceiling":   MeshPatch("top", 0, 40),
        }
    )

# For the sweep we vary M_inf; theta is fixed at theta_deg
# (angle sweep would need a different relation wrapper)
_sweep_mesh = make_ramp_mesh(theta_deg)
_sweep_bcs  = {k: v for k, v in bcs.items()}   # reuse same BC types

def ramp_bcs(M, p, T, alpha=0.0):
    return {
        "inlet":     SupersonicInlet(M=M, p=p, T=T, gamma=gamma, R_gas=R_gas),
        "outlet":    SupersonicOutlet(),
        "flat_wall": SlipWall(),
        "ramp":      SlipWall(),
        "ceiling":   SlipWall(),
    }

sweep_solver = CFDSolver(
    mesh=_sweep_mesh, bcs=ramp_bcs(M_inf, p_inf, T_inf),
    gamma=gamma, R_gas=R_gas, flux_scheme="roe", order=2, cfl=0.3,
)
cfd_rel = sweep_solver.as_relation(
    inputs     = ["M_inf", "p_inf", "T_inf"],
    outputs    = ["M_max", "p_wall"],
    name       = "ramp_euler",
    bc_factory = ramp_bcs,
    run_kwargs = {"max_iter": 1000, "tol": 1e-3, "verbose": False},
)

sweep_sys = anvil.system("ramp_mach_sweep")
sweep_sys.add("M_inf", M_inf)
sweep_sys.add("p_inf", p_inf)
sweep_sys.add("T_inf", T_inf)
sweep_sys.use(cfd_rel)

mach_vals = np.array([2.0, 2.5, 3.0, 3.5])
print(f"\n  Sweeping M = {mach_vals}  (parallel=2) for theta = {theta_deg}deg...")
sweep = sweep_sys.sweep("M_inf", mach_vals, parallel=2, skip_errors=True)
sweep.summary(outputs=["M_max", "p_wall"])

# Analytical comparison
print("\n  Analytical comparison:")
print(f"  {'M_inf':>8s}  {'beta [deg]':>10s}  {'M2':>8s}  {'p2/p1':>8s}")
for M in mach_vals:
    ra = anvil.R.oblique_shock(M1=float(M), theta_deg=theta_deg, gamma=gamma)
    if ra["attached"]:
        print(f"  {M:>8.1f}  {ra['beta_deg']:>10.3f}  {ra['M2']:>8.4f}  {ra['p2_p1']:>8.4f}")
    else:
        print(f"  {M:>8.1f}  {'(detached)':>10s}  {'---':>8s}  {'---':>8s}")

# Cleanup
for f in ["ramp.amesh", "ramp_flow.vtk"]:
    fp = os.path.join(out_dir, f)
    if os.path.exists(fp): os.remove(fp)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
