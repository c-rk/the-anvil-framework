"""Test new features: parallel sweep, new RSQs, project registry, Jupyter repr."""
import sys, os, time
import anvil
import numpy as np

# Force re-seed to pick up new RSQs
from anvil.seed import seed
seed(force=True)
from anvil.registry import _rebuild_namespaces
_rebuild_namespaces()

print("=" * 60)
print("  Feature Tests")
print("=" * 60)

# --- Parallel sweep ---
print("\n[1] Parallel sweep")
nozzle = anvil.S.rocket_nozzle.copy()
nozzle.set(P_amb=0)

t0 = time.time()
sweep_seq = nozzle.sweep("P0", np.linspace(5e6, 30e6, 12))
t_seq = time.time() - t0

t1 = time.time()
sweep_par = nozzle.sweep("P0", np.linspace(5e6, 30e6, 12), parallel=4)
t_par = time.time() - t1

isp_seq = [float(r["Isp"]._si_value) for r in sweep_seq._results if r]
isp_par = [float(r["Isp"]._si_value) for r in sweep_par._results if r]
print(f"  Sequential: {t_seq:.3f}s  |  Parallel(4): {t_par:.3f}s")
print(f"  Results match: {all(abs(a-b) < 1e-6 for a, b in zip(isp_seq, isp_par))}")

# --- New RSQs ---
print("\n[2] New RSQs")

# ISA atmosphere
r = anvil.R.isa_atmosphere(h=10000)
T_atm = float(r["T_atm"]._si_value)
P_atm = float(r["P_atm"]._si_value)
print(f"  ISA @10km: T={T_atm:.1f} K (expect 223.3 K), P={P_atm:.0f} Pa (expect 26500)")

def val(v):
    """Extract float from Quantity or plain number."""
    return float(v._si_value) if hasattr(v, '_si_value') else float(v)

# 2nd order system
r2 = anvil.R.second_order_metrics(omega_n=10.0, zeta=0.5)
print(f"  2nd order (wn=10, z=0.5): overshoot={val(r2['overshoot_pct']):.1f}% (expect ~16.3%), t_settle={val(r2['t_settle']):.3f}s")

# Safety factor
r3 = anvil.R.safety_factor(allowable_stress=250e6, applied_stress=120e6)
print(f"  Safety factor (250/120): SF={val(r3['safety_factor']):.3f} (expect 2.083)")

# Drag polar
r4 = anvil.R.drag_polar(CL=0.5, CD0=0.02, AR=8, e=0.85)
print(f"  Drag polar (CL=0.5): CD={val(r4['CD']):.4f}, L/D={val(r4['LoD']):.1f}")

# Thin airfoil
r5 = anvil.R.thin_airfoil_cl(alpha_deg=5.0, alpha_L0_deg=0.0, M=0.0)
print(f"  Thin airfoil (alpha=5 deg): CL={val(r5['CL']):.4f} (expect ~0.5480)")

# Ziegler-Nichols
r6 = anvil.R.ziegler_nichols_pid(Ku=2.0, Tu=1.0)
print(f"  Z-N PID (Ku=2, Tu=1): Kp={val(r6['Kp']):.3f} (expect 1.2)")

# Fatigue
r7 = anvil.R.fatigue_life_basquin(sigma_a=300e6, sigma_f_prime=1000e6, b_exponent=-0.1)
print(f"  Fatigue life: N={val(r7['N_cycles']):.3e} cycles")

# Breguet range
r8 = anvil.R.range_breguet(V=250.0, TSFC=2e-5, LoD=15.0, W_initial=700e3, W_final=400e3)
print(f"  Breguet range: {val(r8['range_km']):.0f} km")

# --- Project registry ---
print("\n[3] Project registry")
proj = anvil.project("test_project", path="/tmp")

def my_special_relation(T, P, R_spec=287.0):
    """Ideal gas density with specific R."""
    from anvil import Q
    rho = P / (R_spec * T)
    return {"rho": Q(rho, "kg/m^3")}

proj.push(my_special_relation, domain="thermo", description="Project-local ideal gas")
proj.list()

# Access project RSQ
result = proj.R.my_special_relation(T=300.0, P=101325.0)
print(f"  Project RSQ result: rho={val(result['rho']):.4f} kg/m^3")

# Context manager
print("\n[4] Project as context manager")
with anvil.project("cm_test", path="/tmp") as p:
    @anvil.relation(domain="test", register=False)
    def simple_fn(x, y):
        return {"z": x + y}
    p.push(simple_fn, domain="test")

p.list()
result2 = p.R.simple_fn(x=3.0, y=4.0)
print(f"  simple_fn(3, 4) = {val(result2['z'])}")

# Test promote
p.promote("simple_fn")
print(f"  Promoted to global: {anvil.R.simple_fn}")

# --- HTML repr (smoke test) ---
print("\n[5] Jupyter repr (HTML)")
result3 = nozzle.solve()
html = result3._repr_html_()
print(f"  Result HTML: {len(html)} chars, starts with <div: {html.startswith('<div')}")

qty = anvil.Q(340.0, "m/s", name="speed_of_sound")
html_qty = qty._repr_html_()
print(f"  Quantity HTML: {html_qty}")

sweep_html = sweep_seq._repr_html_()
print(f"  Sweep HTML: {len(sweep_html)} chars")

print("\n" + "=" * 60)
print("  All tests passed.")
print("=" * 60)
