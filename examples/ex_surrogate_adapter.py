"""
Example: Surrogate Model Adapters
===================================
Demonstrates make_gp_adapter, make_poly_adapter, make_rbf_adapter, gp_demo.
All adapters work without sklearn installed (numpy/scipy fallbacks).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.surrogate_models import (
    make_gp_adapter, make_poly_adapter, make_rbf_adapter, gp_demo, register
)

rng = np.random.default_rng(42)

# ── Demo adapter: noisy sine ──────────────────────────────────────────────────
print("=== Demo GP surrogate: noisy sin(x) ===")
for x in [0.5, 1.57, 3.14, 4.71]:
    r = gp_demo(x=x)
    print(f"  x={x:.2f}:  y_pred={r['y_pred']:.4f}  y_std={r['y_std']:.4f}"
          f"  exact={r['y_exact']:.4f}  source={r['source']}")

# ── GP surrogate from custom data ────────────────────────────────────────────
print("\n=== Custom GP surrogate: drag coefficient vs AoA ===")
# Synthetic drag polar training data
aoa_train  = np.linspace(-4, 16, 15)
cd_train   = 0.01 + 0.003 * aoa_train + 0.0015 * aoa_train**2 + 0.005 * rng.standard_normal(15)
cd_train   = np.maximum(cd_train, 0.005)

gp_cd = make_gp_adapter(
    X_train=aoa_train.reshape(-1, 1),
    y_train=cd_train,
    x_name="AoA_deg",
    y_name="CD_pred",
    x_unit="1",
    y_unit="1",
    name="drag_gp",
    desc="GP drag coefficient surrogate from wind tunnel data",
)
print("  AoA sweep prediction:")
for aoa in [-2, 0, 4, 8, 12, 15]:
    r = gp_cd(AoA_deg=float(aoa))
    cd = r["CD_pred"] if not hasattr(r["CD_pred"], "si") else float(r["CD_pred"].si)
    unc = r["CD_pred_std"] if not hasattr(r["CD_pred_std"], "si") else float(r["CD_pred_std"].si)
    print(f"  AoA={aoa:3d}°:  CD={cd:.5f} ± {unc:.5f}")
print(f"  source: {r['source']}")

# ── Polynomial surrogate ──────────────────────────────────────────────────────
print("\n=== Polynomial chaos surrogate (degree 4): C_d = f(Re) ===")
Re_train = np.logspace(4, 7, 20)
cd_sphere_train = (
    24.0 / Re_train
    + 6.0 / (1.0 + Re_train**0.5)
    + 0.4
    + 0.01 * rng.standard_normal(20)
)
# Work in log10(Re) space for numerical stability
log_Re_train = np.log10(Re_train)

poly_cd = make_poly_adapter(
    X_train=log_Re_train,
    y_train=cd_sphere_train,
    x_name="log_Re",
    y_name="CD_sphere",
    degree=4,
    name="sphere_drag_poly",
    desc="Sphere drag coefficient polynomial surrogate",
)
print(f"  {'Re':>10}  {'CD_pred':>9}  {'CD_exact':>10}")
for Re in [1e4, 1e5, 5e5, 1e6, 5e6]:
    r = poly_cd(log_Re=np.log10(Re))
    cd_pred  = r["CD_sphere"] if not hasattr(r["CD_sphere"], "si") else float(r["CD_sphere"].si)
    cd_exact = 24/Re + 6/(1+Re**0.5) + 0.4
    print(f"  {Re:10.2e}  {cd_pred:9.5f}  {cd_exact:10.5f}")

# ── RBF surrogate (2-input) ────────────────────────────────────────────────────
print("\n=== RBF surrogate (2 inputs): lift = f(AoA, Mach) ===")
n_pts  = 40
aoa_s  = rng.uniform(-4, 14, n_pts)
mach_s = rng.uniform(0.1, 0.8, n_pts)
cl_s   = (2 * np.pi * np.radians(aoa_s)
           / np.sqrt(1 - mach_s**2)
           + 0.02 * rng.standard_normal(n_pts))

X_2d = np.column_stack([aoa_s, mach_s])

try:
    rbf_cl = make_rbf_adapter(
        X_train=X_2d, y_train=cl_s,
        input_names=["AoA_deg", "Mach"],
        y_name="CL_pred",
        function="multiquadric",
        name="lift_rbf",
        desc="Lift coefficient RBF surrogate (AoA, Mach)",
    )
    print(f"  {'AoA':>5}  {'Mach':>5}  {'CL_RBF':>8}  {'CL_theory':>10}")
    for aoa, mach in [(2, 0.3), (5, 0.3), (5, 0.6), (8, 0.5)]:
        r = rbf_cl(AoA_deg=float(aoa), Mach=float(mach))
        cl_rbf = r["CL_pred"] if not hasattr(r["CL_pred"], "si") else float(r["CL_pred"].si)
        import math
        cl_th  = 2*math.pi*math.radians(aoa) / math.sqrt(1 - mach**2)
        print(f"  {aoa:5.1f}  {mach:5.2f}  {cl_rbf:8.4f}  {cl_th:10.4f}")
    print(f"  source: {r['source']}")
except Exception as e:
    print(f"  (RBF requires scipy ≥ 1.7: {e})")

# ── GP surrogate in Anvil System ──────────────────────────────────────────────
print("\n=== GP surrogate in System: drag polar study ===")
sys_ = anvil.system("surrogate_polar")
sys_.add("AoA_deg", 0.0)
sys_.use(gp_cd)

alphas = np.linspace(-2, 14, 9)
sweep  = sys_.sweep("AoA_deg", alphas)
print(f"  {'AoA':>5}  {'CD_pred':>9}  {'uncertainty':>12}")
for i in range(len(alphas)):
    row = sweep.table.iloc[i]
    cd  = row.get("CD_pred", row.get("CD_pred", None))
    if cd is None:
        continue
    cd  = float(cd.si) if hasattr(cd, "si") else float(cd)
    unc = row.get("CD_pred_std", 0.0)
    unc = float(unc.si) if hasattr(unc, "si") else float(unc)
    print(f"  {alphas[i]:5.1f}  {cd:9.5f}  ±{unc:.5f}")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register demo adapter ===")
register()
print("  Global: gp_demo_sine → domain surrogate.demo")
print("  Factories: make_gp_adapter, make_poly_adapter, make_rbf_adapter")
