"""
Example: OpenMDAO MDO Adapter
==============================
Demonstrates openmdo_sellar, openmdo_beam, and the make_openmdo_adapter factory.
Mock mode (analytical Sellar equations, Euler-Bernoulli beam) runs without OpenMDAO.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil
from anvil.adapters.openmdo_wrap import (
    openmdo_sellar, openmdo_beam, make_openmdo_adapter, register
)

# ── Sellar benchmark ──────────────────────────────────────────────────────────
print("=== Sellar coupled MDO benchmark ===")
r = openmdo_sellar(x1=1.0, z1=5.0, z2=2.0)
print(f"  f  = {r['f']:.4f}  (objective, minimize)")
print(f"  g1 = {r['g1']:.4f}  (constraint ≤ 0 → feasible if ≤ 0)")
print(f"  g2 = {r['g2']:.4f}  (constraint ≤ 0)")
print(f"  y1 = {r['y1']:.4f}  (coupling variable, discipline 1)")
print(f"  y2 = {r['y2']:.4f}  (coupling variable, discipline 2)")
print(f"  source: {r['source']}")

# ── Sweep: Sellar objective vs z1 ─────────────────────────────────────────────
print("\n=== Sellar objective vs z1 (x1=1, z2=2) ===")
sys_ = anvil.system("sellar_z1_sweep")
sys_.add("x1", 1.0)
sys_.add("z1", 5.0)
sys_.add("z2", 2.0)
sys_.use(openmdo_sellar)

z1_vals = np.linspace(1.0, 8.0, 8)
sweep   = sys_.sweep("z1", z1_vals)

print(f"  {'z1':>5}  {'f':>8}  {'g1':>7}  {'g2':>7}  feasible?")
for i in range(len(z1_vals)):
    row  = sweep.table.iloc[i]
    feas = "YES" if row["g1"] <= 0 and row["g2"] <= 0 else " no"
    print(f"  {row['z1']:5.2f}  {row['f']:8.4f}  {row['g1']:7.4f}  {row['g2']:7.4f}  {feas}")
print("  (g2 = y2 - 24; tends infeasible at high z1 due to y2 growth)")

# ── Cantilever beam ───────────────────────────────────────────────────────────
print("\n=== OpenMDAO cantilever beam ===")
r2 = openmdo_beam(
    F_tip=5000.0,    # N
    L_beam=2.0,      # m
    E=70e9,          # Pa (aluminium)
    b=0.05,          # m
    h=0.10,          # m
)
print(f"  Deflection = {r2['deflection']}")
print(f"  Max stress = {r2['max_stress']}")
print(f"  I_moment   = {r2['I_moment']}")
print(f"  source: {r2['source']}")

# ── Beam sensitivity: deflection vs cross-section height ─────────────────────
print("\n=== Beam deflection vs height h (F=5kN, L=2m, E=70GPa, b=0.05) ===")
sys2 = anvil.system("beam_height_sweep")
sys2.add("F_tip",  5000.0)
sys2.add("L_beam", 2.0)
sys2.add("E",      70e9)
sys2.add("b",      0.05)
sys2.add("h",      0.1)
sys2.use(openmdo_beam)

h_vals = np.linspace(0.04, 0.20, 8)
sweep2 = sys2.sweep("h", h_vals)
print(f"  {'h [m]':>7}  {'δ [mm]':>8}  {'σ_max [MPa]':>12}")
for i in range(len(h_vals)):
    row = sweep2.table.iloc[i]
    defl_mm  = float(row["deflection"]) * 1000 if hasattr(row["deflection"], "__float__") else row["deflection"].to("mm").value if hasattr(row["deflection"], "to") else 0
    # Handle Q objects
    defl_mm = float(row.get("deflection", 0))
    defl_mm = sweep2.table.iloc[i]["deflection"]
    if hasattr(defl_mm, "si"):
        defl_mm = float(defl_mm.si) * 1000
    else:
        defl_mm = float(defl_mm) * 1000
    stress = sweep2.table.iloc[i]["max_stress"]
    if hasattr(stress, "si"):
        stress_mpa = float(stress.si) / 1e6
    else:
        stress_mpa = float(stress) / 1e6
    print(f"  {h_vals[i]:7.3f}  {defl_mm:8.2f}  {stress_mpa:12.1f}")
print("  (δ ∝ 1/h³: doubling height cuts deflection 8×)")

# ── Custom OpenMDAO problem via factory ───────────────────────────────────────
print("\n=== Custom OpenMDAO problem via make_openmdo_adapter ===")
# This example only works with OpenMDAO installed — shows the pattern
try:
    import openmdao.api as om

    def build_paraboloid():
        class Paraboloid(om.ExplicitComponent):
            def setup(self):
                self.add_input("x", val=0.0)
                self.add_input("y", val=0.0)
                self.add_output("f_xy", val=0.0)
                self.declare_partials("*", "*", method="fd")
            def compute(self, inputs, outputs):
                x = inputs["x"]; y = inputs["y"]
                outputs["f_xy"] = (x - 3.0)**2 + x*y + (y + 4.0)**2 - 3.0
        p = om.Problem()
        p.model.add_subsystem("comp", Paraboloid(), promotes=["*"])
        p.setup()
        return p

    paraboloid = make_openmdo_adapter(
        prob_factory=build_paraboloid,
        input_vars={"x": {"unit": "1", "desc": "x variable", "default": 0.0},
                    "y": {"unit": "1", "desc": "y variable", "default": 0.0}},
        output_vars={"f_xy": {"unit": "1", "desc": "Paraboloid value"}},
        name="paraboloid_mdo",
        desc="Paraboloid function via OpenMDAO",
    )
    r3 = paraboloid(x=6.6, y=-7.3)
    print(f"  f_xy at (6.6, -7.3) = {r3['f_xy']:.4f}  (expected ≈ -15.94)")
    print(f"  source: {r3['source']}")
except ImportError:
    print("  (OpenMDAO not installed — install with: pip install openmdao)")
    print("  Pattern: make_openmdo_adapter(prob_factory, input_vars, output_vars, ...)")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: openmdo_sellar, openmdo_beam → domain mdo.openmdao")
