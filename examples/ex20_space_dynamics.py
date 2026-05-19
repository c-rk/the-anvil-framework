"""
Example 20: Space Dynamics, Attitude, and Mission Budgets
==========================================================

Demonstrates the space-focused RSQs added to the Anvil seed library.
All computed physical quantities carry units automatically -- no unit
strings are hard-coded in print statements.

Engineering context:
  A 200 kg Earth-observation smallsat in a 500 km Sun-Synchronous Orbit.
  Plan delta-V budget, size attitude hardware, compute link and power
  budgets, and analyse the attitude control system.
"""

import numpy as np

import anvil
from anvil import Q, System

W = 65
print("=" * W)
print("  Example 20: Space Dynamics, Attitude & Mission Budgets")
print("=" * W)

mu_E = 3.986004418e14
R_E = 6.371e6
J2 = 1.08263e-3
a_SSO = R_E + 500e3  # m
i_SSO = 97.4  # deg (SSO for 500 km)


# =============================================================================
# [1] Orbital state
# =============================================================================

print("\n[1] Orbital state: Keplerian <-> Cartesian")

eci = anvil.R.keplerian_to_cartesian(
    a=a_SSO,
    e=0.001,
    i_deg=i_SSO,
    RAAN_deg=45.0,
    omega_deg=90.0,
    nu_deg=0.0,
    mu=mu_E,
)
T_orbit = Q(2 * 3.141592653589793 * (a_SSO**3 / mu_E) ** 0.5, "s")
print(f"  r_mag  = {eci['r_mag']}")
print(f"  v_mag  = {eci['v_mag']}")
print(f"  period = {T_orbit}")

back = anvil.R.cartesian_to_keplerian(
    r_vec=eci["r_eci"],
    v_vec=eci["v_eci"],
    mu=mu_E,
)
print(f"  Round-trip:  a = {back['a']}  e = {back['e']:.5f}")
print(f"               i = {back['i_deg']:.3f} deg  RAAN = {back['RAAN_deg']:.3f} ")


# =============================================================================
# [2] J2 and eclipse
# =============================================================================

print("\n[2] J2 precession and eclipse at SSO")

j2 = anvil.R.j2_precession(a=a_SSO, e=0.001, i_deg=i_SSO)
print(f"  RAAN drift   : {j2['d_RAAN_dt']}  (SSO target ~+1.99e-7 rad/s)")
print(f"  omega drift  : {j2['d_omega_dt']}")

ecl_worst = anvil.R.eclipse_fraction(a=a_SSO, beta_deg=0.0)
ecl_best = anvil.R.eclipse_fraction(a=a_SSO, beta_deg=70.0)
print(f"  Eclipse worst (beta=0):   {ecl_worst['eclipse_frac']:.3f}")
print(f"  Eclipse best  (beta=70):  {ecl_best['eclipse_frac']:.3f}")
print(f"  Max-eclipse beta:         {ecl_worst['beta_max_deg']:.1f} deg")


# =============================================================================
# [3] Delta-V budget
# =============================================================================

print("\n[3] Delta-V budget")

dv = anvil.R.delta_v_budget(
    dv1=50,
    dv2=20,
    dv3=30,
    dv4=80,
    margin_pct=10.0,
)
print(f"  dv total (no margin)  : {dv['dv_total']}")
print(f"  dv with 10% margin    : {dv['dv_with_margin']}")

prop = anvil.R.propellant_mass(
    dv=dv["dv_with_margin"].si,
    Isp=220,
    m_dry=200,
)
print(f"  Propellant (Isp=220 s): {prop['m_propellant']}")
print(f"  Wet mass              : {prop['m_wet']}")
print(f"  Mass ratio            : {prop['mass_ratio']:.4f}")

print(f"\n  Propellant vs Isp (same dv):")
prop_sys = System("propulsion")
prop_sys.add("dv", dv["dv_with_margin"].si, "m/s")
prop_sys.add("Isp", 220, "s")
prop_sys.add("m_dry", 200, "kg")
prop_sys.use("propellant_mass")
prop_sys.sweep("Isp", [80, 150, 220, 300, 450, 3000]).summary(
    outputs=["Isp", "m_propellant", "mass_ratio"]
)


# =============================================================================
# [4] Gravity gradient torque and reaction wheel sizing
# =============================================================================

print("\n[4] Attitude disturbances and actuator sizing")

Ix, Iy, Iz = 8.0, 10.0, 12.0

gg = anvil.R.gravity_gradient_torque(
    mu=mu_E,
    r=a_SSO,
    Ix=Ix,
    Iy=Iy,
    Iz=Iz,
    theta_pitch_deg=1.0,
    phi_roll_deg=0.5,
)
print(f"  T_roll     : {gg['T_roll']}")
print(f"  T_pitch    : {gg['T_pitch']}")
print(f"  T_gg_max   : {gg['T_gg_max']}")

rw = anvil.R.reaction_wheel_sizing(
    I_sc=Iz,
    theta_slew_deg=5.0,
    t_slew=30.0,
    margin=1.5,
)
print(f"\n  5 deg slew in 30 s (1.5x margin):")
print(f"  H_rw       : {rw['H_rw']}")
print(f"  tau_rw     : {rw['tau_rw']}")
print(f"  omega_slew : {rw['omega_slew_max']}")
print(f"  P_peak     : {rw['P_peak']}")


# =============================================================================
# [5] Quaternion kinematics
# =============================================================================

print("\n[5] Quaternion kinematics -- 0.01 rad/s pitch for 10 steps")

dt = 1.0
q = [1.0, 0.0, 0.0, 0.0]
print(f"  {'t':>4}  {'q_w':>8}  {'q_x':>8}  {'q_y':>8}  {'q_z':>8}  {'|q|':>6}")
for step in range(11):
    if step % 2 == 0:
        print(
            f"  {step * dt:>4.0f}  {q[0]:>8.5f}  {q[1]:>8.5f}  {q[2]:>8.5f}  {q[3]:>8.5f}  "
            f"{sum(x**2 for x in q) ** 0.5:>6.4f}"
        )
    if step < 10:
        qd = anvil.R.quaternion_kinematics(
            q_w=q[0],
            q_x=q[1],
            q_y=q[2],
            q_z=q[3],
            omega_x=0.0,
            omega_y=0.01,
            omega_z=0.0,
        )
        q = [
            q[0] + qd["qw_dot"] * dt,
            q[1] + qd["qx_dot"] * dt,
            q[2] + qd["qy_dot"] * dt,
            q[3] + qd["qz_dot"] * dt,
        ]
        n = sum(x**2 for x in q) ** 0.5
        q = [x / n for x in q]


# =============================================================================
# [6] TRIAD attitude determination
# =============================================================================

print("\n[6] TRIAD attitude determination")

theta = np.radians(30)
C_true = np.array(
    [[np.cos(theta), -np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0, 0, 1]]
)
sun_ref = np.array([0.8, 0.6, 0.0])
mag_ref = np.array([0.3, 0.0, 0.95])
sun_body = C_true @ sun_ref
mag_body = C_true @ mag_ref

tr = anvil.R.triad_attitude(
    b1_x=sun_body[0],
    b1_y=sun_body[1],
    b1_z=sun_body[2],
    b2_x=mag_body[0],
    b2_y=mag_body[1],
    b2_z=mag_body[2],
    r1_x=sun_ref[0],
    r1_y=sun_ref[1],
    r1_z=sun_ref[2],
    r2_x=mag_ref[0],
    r2_y=mag_ref[1],
    r2_z=mag_ref[2],
)
print(
    f"  True rotation: 30 deg about Z  ->  q_z = sin(15 deg) = {np.sin(np.radians(15)):.5f}"
)
print(
    f"  TRIAD q: w={tr['q_w']:.5f}  x={tr['q_x']:.5f}  y={tr['q_y']:.5f}  z={tr['q_z']:.5f}"
)


# =============================================================================
# [7] Euler equations
# =============================================================================

print("\n[7] Euler equations -- spin stability check")

for label, (Ix_, Iy_, Iz_), (ox, oy, oz) in [
    ("Major axis (stable)", (100, 80, 60), (0.01, 0.01, 1.0)),
    ("Minor axis (stable)", (60, 80, 100), (0.01, 0.01, 1.0)),
    ("Intermediate (unstable)", (60, 100, 80), (0.01, 0.01, 1.0)),
]:
    r = anvil.R.euler_equations(
        omega_x=ox, omega_y=oy, omega_z=oz, Ix=Ix_, Iy=Iy_, Iz=Iz_
    )
    alpha_perp = (r["alpha_x"].si ** 2 + r["alpha_y"].si ** 2) ** 0.5
    print(f"  {label:32s}: perp accel = {Q(alpha_perp, 'rad/s^2')}")


# =============================================================================
# [8] Power budget
# =============================================================================

print("\n[8] Power budget -- 200 kg EO smallsat")

pwr = anvil.R.power_budget(
    P_load_W=80,
    T_orbit_min=94.6,
    eclipse_frac=ecl_worst["eclipse_frac"],
    eta_solar=0.30,
    flux_solar=1361.0,
    DOD=0.8,
    eta_battery=0.9,
)
print(f"  Solar array  : {pwr['A_panel_m2']}")
print(f"  Battery      : {pwr['E_bat_Wh']}  /  {pwr['m_bat_kg']}")
print(f"  Panel output : {pwr['P_from_panel_W']}")

print(f"\n  Sensitivity: panel area vs eclipse fraction:")
pwr_sys = System("power_sizing")
pwr_sys.add("P_load_W", 80)
pwr_sys.add("T_orbit_min", 94.6)
pwr_sys.add("eclipse_frac", 0.35)
pwr_sys.add("eta_solar", 0.30)
pwr_sys.add("flux_solar", 1361.0)
pwr_sys.add("DOD", 0.8)
pwr_sys.add("eta_battery", 0.9)
pwr_sys.use("power_budget")
pwr_sys.sweep("eclipse_frac", np.linspace(0.1, 0.5, 5)).summary(
    outputs=["eclipse_frac", "A_panel_m2", "E_bat_Wh", "m_bat_kg"]
)


# =============================================================================
# [9] Link budget
# =============================================================================

print("\n[9] Link budget -- X-band downlink at 500 km")

lnk = anvil.R.link_budget(
    P_tx_W=5,
    G_tx_dBi=3,
    G_rx_dBi=47,
    freq_Hz=8.4e9,
    distance_m=a_SSO,
    losses_dB=4.0,
)
print(f"  FSPL         : {lnk['FSPL_dB']:.1f} dB")
print(f"  EIRP         : {lnk['EIRP_dBW']:.1f} dBW")
print(f"  P_rx         : {lnk['P_rx_dBW']:.1f} dBW  =  {lnk['P_rx_W']}")

print(f"\n  Range sweep:")
print(f"  {'Range (km)':>12}  {'FSPL (dB)':>10}  {'P_rx (dBW)':>12}")
for d_km in [400, 600, 800, 1200, 2000]:
    r = anvil.R.link_budget(
        P_tx_W=5,
        G_tx_dBi=3,
        G_rx_dBi=47,
        freq_Hz=8.4e9,
        distance_m=d_km * 1e3,
        losses_dB=4.0,
    )
    print(f"  {d_km:>12}  {r['FSPL_dB']:>10.1f}  {r['P_rx_dBW']:>12.1f}")


# =============================================================================
# [10] Attitude controller analysis
# =============================================================================

print("\n[10] Attitude controller analysis (pitch PD)")

Kp, Kd = 0.15, 1.2
omega_n = (Kp / Iz) ** 0.5
zeta = Kd / (2 * (Kp * Iz) ** 0.5)

m = anvil.R.second_order_metrics(omega_n=omega_n, zeta=zeta)
print(f"  omega_n = {Q(omega_n, 'rad/s')}  zeta = {zeta:.4f}")
print(
    f"  Overshoot: {m['overshoot_pct']:.1f}%   t_settle: {m['t_settle']:.1f} s   t_rise: {m['t_rise']:.1f} s"
)

poles = anvil.R.state_space_poles(A_flat=[0, 1, -Kp / Iz, -Kd / Iz], n_states=2)
print(
    f"  Poles: {[complex(round(r, 4), round(i, 4)) for r, i in zip(poles['poles_real'], poles['poles_imag'])]}"
)
print(f"  Stable: {poles['stable']}  min damping: {poles['min_damping']:.4f}")

gm = anvil.R.gain_phase_margin(num_coeffs=[Kd, Kp], den_coeffs=[Iz, 0, 0])
print(
    f"  GM = {gm['GM_dB']:.1f} dB   PM = {gm['PM_deg']:.1f} deg   stable = {gm['stable']}"
)

q_lqr = anvil.R.lqr_bryson(
    state_bounds=[np.radians(5)] * 3,
    input_bounds=[0.5] * 3,
)
print(
    f"  LQR Q = {[round(x, 1) for x in q_lqr['Q_diag']]}  R = {[round(x, 2) for x in q_lqr['R_diag']]}"
)


# =============================================================================
# [11] Sphere of influence
# =============================================================================

print("\n[11] Sphere of influence")

soi_moon = anvil.R.sphere_of_influence(
    a_body=384400e3, m_body=7.342e22, m_parent=5.972e24
)
soi_mars = anvil.R.sphere_of_influence(
    a_body=1.524 * 1.496e11, m_body=6.390e23, m_parent=1.989e30
)
print(f"  Moon SOI : {soi_moon['r_SOI'].to('km')}  (expected 66100 km)")
print(f"  Mars SOI : {soi_mars['r_SOI'].to('km')}  (expected ~577000 km)")


# =============================================================================
# [12] Hohmann vs bi-elliptic
# =============================================================================

print("\n[12] Hohmann vs bi-elliptic  LEO -> GEO")

h = anvil.R.hohmann_transfer(mu=mu_E, r1=R_E + 400e3, r2=42164e3)
print(f"  Hohmann:   dv = {h['dv_total'].to('km/s')}   tof = {h['tof']}")

for r_b_km in [100_000, 200_000, 384_400]:
    be = anvil.R.bielliptic_transfer(
        mu=mu_E, r1=R_E + 400e3, r2=42164e3, rb=r_b_km * 1e3
    )
    print(
        f"  Bi-elliptic rb={r_b_km:7d} km:  dv = {be['dv_total'].to('km/s')}   tof = {be['tof']}"
    )


print("\n" + "=" * W)
print("  Done.")
print("=" * W)
