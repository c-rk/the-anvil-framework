"""
Example 8: Research Workflow -- Thermal-Structural Coupled Analysis
===================================================================

Demonstrates the full Anvil research workflow:
    1. Look up material properties from the built-in database
    2. Look up fluid properties for convective cooling
    3. Build a coupled thermal-structural system
    4. Sweep over operating conditions
    5. Sensitivity analysis to identify design drivers
    6. Export results to CSV for post-processing
    7. Compare materials for optimal selection

Engineering context:
    A rocket combustion chamber wall is cooled by fuel flowing
    through channels. The wall must survive thermal stresses
    without exceeding yield. Which material? Which coolant flow rate?
"""

import sys, os
import numpy as np

import anvil
from anvil import Q, System
from anvil.db import fluids, materials

print("=" * 60)
print("  Example 8: Combustion Chamber Wall Design")
print("=" * 60)

# =====================================================
# Step 1: Material selection database lookup
# =====================================================
print("\n[1] Material candidates:")
materials.compare("Copper-C101", "Inconel-718", "Steel-304")

# Select copper for thermal conductivity
mat = materials.get("Copper-C101")
print(f"  Selected: Copper-C101")
print(f"    k = {mat['k']} (high conductivity)")
print(f"    sigma_y = {mat['sigma_y'].to('MPa')}")
print(f"    T_max = {mat['T_max']}")

# =====================================================
# Step 2: Coolant properties
# =====================================================
print(f"\n[2] Coolant: RP-1 (modeled as air-like for demo)")
coolant = fluids.get("air", T=400)  # RP-1 approximation
print(f"  rho = {coolant['rho']}")
print(f"  cp  = {coolant['cp']}")
print(f"  mu  = {coolant['mu']}")

# =====================================================
# Step 3: Build thermal-structural wall system
# =====================================================
print(f"\n[3] Building coupled wall analysis system...")

wall = System("chamber_wall")

# Operating conditions
wall.add("T_gas",      3500,     "K",      desc="Hot gas temperature")
wall.add("h_gas",      5000,     "W",      desc="Gas-side heat transfer coeff")
wall.add("T_coolant",  400,      "K",      desc="Coolant bulk temperature")
wall.add("h_coolant",  15000,    "W",      desc="Coolant-side heat transfer coeff")

# Wall geometry
wall.add("t_wall",     0.003,    "m",      desc="Wall thickness")
wall.add("r_inner",    0.15,     "m",      desc="Chamber inner radius")

# Material (from database)
wall.add("k_wall",     mat["k"].si,           desc="Wall thermal conductivity")
wall.add("E",          mat["E"].si,  "Pa",    desc="Young's modulus")
wall.add("alpha_th",   mat["alpha"].si,        desc="Thermal expansion coeff")
wall.add("nu_poisson", mat["nu_poisson"],      desc="Poisson's ratio")
wall.add("sigma_y",    mat["sigma_y"].si, "Pa", desc="Yield strength")

# Thermal analysis: T_hot -> T_cold through wall
def wall_temperatures(T_gas, h_gas, T_coolant, h_coolant, k_wall, t_wall):
    """Steady-state 1D heat transfer through wall with convection on both sides."""
    # Total thermal resistance per unit area
    R_total = 1/h_gas + t_wall/k_wall + 1/h_coolant
    # Heat flux
    q_flux = (T_gas - T_coolant) / R_total
    # Surface temperatures
    T_hot_wall = T_gas - q_flux / h_gas
    T_cold_wall = T_coolant + q_flux / h_coolant
    T_avg_wall = (T_hot_wall + T_cold_wall) / 2
    return {
        "q_flux": Q(q_flux, "W"),
        "T_hot_wall": Q(T_hot_wall, "K"),
        "T_cold_wall": Q(T_cold_wall, "K"),
        "T_avg_wall": Q(T_avg_wall, "K"),
    }

# Thermal stress
def thermal_stress(T_hot_wall, T_cold_wall, E, alpha_th, nu_poisson):
    """Thermal stress from temperature gradient through wall."""
    dT = T_hot_wall - T_cold_wall
    # Biaxial thermal stress in a constrained plate
    sigma_th = E * alpha_th * dT / (2 * (1 - nu_poisson))
    return {"sigma_thermal": Q(sigma_th, "Pa"), "delta_T_wall": Q(dT, "K")}

# Pressure stress (hoop)
def pressure_stress(P_chamber, r_inner, t_wall):
    sigma_h = P_chamber * r_inner / t_wall
    return {"sigma_hoop": Q(sigma_h, "Pa")}

# Safety factor
def safety_factor(sigma_thermal, sigma_hoop, sigma_y):
    sigma_total = sigma_thermal + sigma_hoop
    SF = sigma_y / sigma_total if sigma_total > 0 else 999
    return {"sigma_total": Q(sigma_total, "Pa"), "safety_factor": SF}

wall.add("P_chamber", 10e6, "Pa", desc="Chamber pressure")
wall.use(wall_temperatures)
wall.use(thermal_stress)
wall.use(pressure_stress)
wall.use(safety_factor)

result = wall.solve_forward()
result.summary(keys=["T_gas", "T_coolant", "t_wall", "P_chamber",
                       "q_flux", "T_hot_wall", "T_cold_wall", "delta_T_wall",
                       "sigma_thermal", "sigma_hoop", "sigma_total", "safety_factor"])

# =====================================================
# Step 4: Sweep over wall thickness
# =====================================================
print(f"\n[4] Sweep: safety factor vs wall thickness...")
sweep = wall.sweep("t_wall", np.linspace(0.001, 0.008, 6))
sweep.summary(outputs=["T_hot_wall", "sigma_thermal", "sigma_hoop",
                          "sigma_total", "safety_factor"])

# =====================================================
# Step 5: Sensitivity analysis
# =====================================================
print(f"\n[5] Sensitivity: what drives safety factor?")
sens = wall.sensitivity(outputs=["safety_factor", "T_hot_wall"])
sens.summary()

print(f"\n  Top 3 drivers of safety factor:")
for inp, val in sens.top("safety_factor", n=3):
    print(f"    {inp}: {val:+.4f}")

# =====================================================
# Step 6: Material comparison
# =====================================================
print(f"\n[6] Material comparison for this wall:")
candidates = ["Copper-C101", "Inconel-718", "Steel-304"]
print(f"  {'Material':20s} {'T_hot(K)':>10s} {'sigma(MPa)':>12s} {'SF':>8s}")
print(f"  {'-'*52}")

for mat_name in candidates:
    m = materials.get(mat_name)
    wall.set(
        k_wall=m["k"].si,
        E=m["E"].si,
        alpha_th=m["alpha"].si,
        nu_poisson=m["nu_poisson"],
        sigma_y=m["sigma_y"].si,
    )
    r = wall.solve_forward()
    sf = r["safety_factor"].si
    thot = r["T_hot_wall"].si
    sig = r["sigma_total"].si / 1e6
    ok = "OK" if sf > 1.5 else "FAIL"
    print(f"  {mat_name:20s} {thot:10.0f} {sig:12.0f} {sf:8.2f}  [{ok}]")

# =====================================================
# Step 7: Export
# =====================================================
print(f"\n[7] Exporting sweep data...")
sweep.to_csv("wall_sweep.csv", outputs=["T_hot_wall", "sigma_total", "safety_factor"])
print(f"  Saved: wall_sweep.csv")
os.remove("wall_sweep.csv")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
