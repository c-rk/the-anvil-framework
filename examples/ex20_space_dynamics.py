"""
Example 20: Space Dynamics, Attitude, and Mission Budgets
==========================================================

Demonstrates the new space-focused RSQs added to the Anvil seed library:

  Orbital mechanics:
    keplerian_to_cartesian, cartesian_to_keplerian
    plane_change_dv, bielliptic_transfer
    j2_precession, eclipse_fraction, sphere_of_influence
    propellant_mass, delta_v_budget

  Attitude / ADCS:
    euler_equations, quaternion_kinematics
    triad_attitude, gravity_gradient_torque, reaction_wheel_sizing

  Mission budgets:
    link_budget, power_budget

  Controls (extended):
    state_space_poles, lqr_bryson, gain_phase_margin

Engineering context:
  A 200 kg Earth-observation smallsat in a 500 km Sun-Synchronous Orbit (SSO).
  Mission: plan delta-V budget, size attitude hardware, compute link and power
  budgets, and analyse the attitude control system.
"""

import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil import Q, System

print("=" * 65)
print("  Example 20: Space Dynamics, Attitude & Mission Budgets")
print("=" * 65)

mu_E   = 3.986004418e14   # m³/s²
R_E    = 6.371e6          # m
J2     = 1.08263e-3       # Earth J2
h_SSO  = 500e3            # m altitude
a_SSO  = R_E + h_SSO      # m semi-major axis
i_SSO  = 97.4             # deg (SSO inclination for 500 km)


# =============================================================================
# [1] Orbital state representation
# =============================================================================

print("\n[1] Orbital state: Keplerian <-> Cartesian")

elems = dict(a=a_SSO, e=0.001, i_deg=i_SSO,
             RAAN_deg=45.0, omega_deg=90.0, nu_deg=0.0, mu=mu_E)

eci = anvil.R.keplerian_to_cartesian(**elems)
print(f"  Elements -> ECI:")
print(f"    r = [{eci['r_eci'][0]/1e3:+.1f}, {eci['r_eci'][1]/1e3:+.1f}, {eci['r_eci'][2]/1e3:+.1f}] km")
print(f"    v = [{eci['v_eci'][0]/1e3:+.4f}, {eci['v_eci'][1]/1e3:+.4f}, {eci['v_eci'][2]/1e3:+.4f}] km/s")
print(f"    |r| = {eci['r_mag'].to('km').value:.2f} km  |v| = {eci['v_mag'].to('km/s').value:.4f} km/s")

# Round-trip check
back = anvil.R.cartesian_to_keplerian(r_vec=eci['r_eci'], v_vec=eci['v_eci'], mu=mu_E)
print(f"  ECI -> Elements (round-trip):")
print(f"    a={back['a'].to('km').value:.2f} km  e={back['e']:.5f}  i={back['i_deg']:.3f} deg")
print(f"    RAAN={back['RAAN_deg']:.3f}  omega={back['omega_deg']:.3f}  nu={back['nu_deg']:.3f} deg")


# =============================================================================
# [2] J2 perturbation and eclipse
# =============================================================================

print("\n[2] J2 precession and eclipse fraction at SSO")

j2 = anvil.R.j2_precession(a=a_SSO, e=0.001, i_deg=i_SSO)
print(f"  RAAN drift   : {j2['d_RAAN_deg_per_day']:+.4f} deg/day  (SSO target: ~+0.9856 deg/day)")
print(f"  omega drift  : {j2['d_omega_deg_per_day']:+.4f} deg/day")

ecl_worst = anvil.R.eclipse_fraction(a=a_SSO, beta_deg=0.0)
ecl_best  = anvil.R.eclipse_fraction(a=a_SSO, beta_deg=70.0)
print(f"\n  Eclipse fraction:")
print(f"    Worst case (beta=0):  {ecl_worst['eclipse_frac']:.3f}  ({ecl_worst['eclipse_frac']*100:.1f}%)")
print(f"    Best case  (beta=70): {ecl_best['eclipse_frac']:.3f}  ({ecl_best['eclipse_frac']*100:.1f}%)")
print(f"    Max eclipse beta: {ecl_worst['beta_max_deg']:.1f} deg")


# =============================================================================
# [3] Delta-V budget and propellant sizing
# =============================================================================

print("\n[3] Mission delta-V budget  (LEO injection + station-keeping + deorbit)")

dv = anvil.R.delta_v_budget(
    dv1 = 50,    # launch dispersion correction
    dv2 = 20,    # RAAN correction
    dv3 = 30,    # drag makeup (5 years)
    dv4 = 80,    # deorbit burn
    margin_pct = 10.0,
)
print(f"  Phase totals (no margin): {dv['dv_total'].value:.0f} m/s")
print(f"  With 10% margin:          {dv['dv_with_margin'].value:.0f} m/s")

prop = anvil.R.propellant_mass(
    dv  = dv['dv_with_margin'].si,
    Isp = 220,          # cold-gas thruster Isp
    m_dry = 200,        # kg dry mass
)
print(f"\n  Propellant mass (Isp=220 s): {prop['m_propellant'].value:.1f} kg")
print(f"  Wet mass:                     {prop['m_wet'].value:.1f} kg")
print(f"  Mass ratio:                   {prop['mass_ratio']:.4f}")

# Sweep Isp to compare propulsion options
prop_sys = System("propulsion")
prop_sys.add("dv",    dv['dv_with_margin'].si, "m/s")
prop_sys.add("Isp",   220,                     "s")
prop_sys.add("m_dry", 200,                     "kg")
prop_sys.use("propellant_mass")

print(f"\n  Propellant vs Isp (same dv = {dv['dv_with_margin'].value:.0f} m/s):")
sweep = prop_sys.sweep("Isp", [80, 150, 220, 300, 450, 3000])
sweep.summary(outputs=["Isp", "m_propellant", "mass_ratio"])


# =============================================================================
# [4] Gravity gradient torque and reaction wheel sizing
# =============================================================================

print("\n[4] Attitude disturbances and actuator sizing")

# Spacecraft inertia (box ~0.5 m, 200 kg)
Ix, Iy, Iz = 8.0, 10.0, 12.0   # kg*m²

gg = anvil.R.gravity_gradient_torque(
    mu=mu_E, r=a_SSO, Ix=Ix, Iy=Iy, Iz=Iz,
    theta_pitch_deg=1.0, phi_roll_deg=0.5
)
print(f"  Gravity gradient torques (at 1 deg pitch, 0.5 deg roll):")
print(f"    T_roll  = {gg['T_roll'].value:.2e} N*m")
print(f"    T_pitch = {gg['T_pitch'].value:.2e} N*m")
print(f"    T_max   = {gg['T_gg_max'].value:.2e} N*m  (45-deg worst case)")
print(f"    orbital rate = {gg['omega_orbital'].value*180/np.pi*60:.4f} deg/min")

# Reaction wheel sizing for 5-deg slew in 30 seconds (imaging maneuver)
rw = anvil.R.reaction_wheel_sizing(
    I_sc=Iz, theta_slew_deg=5.0, t_slew=30.0, margin=1.5
)
print(f"\n  Reaction wheel sizing (5 deg slew in 30 s, 50% margin):")
print(f"    Angular momentum : {rw['H_rw'].value:.4f} N*m*s")
print(f"    Peak torque      : {rw['tau_rw'].value:.5f} N*m")
print(f"    Max slew rate    : {rw['omega_slew_max'].value*180/np.pi:.3f} deg/s")
print(f"    Peak power       : {rw['P_peak'].value:.4f} W")


# =============================================================================
# [5] Attitude kinematics: quaternion propagation
# =============================================================================

print("\n[5] Quaternion kinematics — propagate attitude under constant spin")

dt = 1.0   # s
omega_body = (0.0, 0.01, 0.0)   # rad/s pitch rate
q = [1.0, 0.0, 0.0, 0.0]        # initial identity

print("  Propagating attitude at 0.01 rad/s pitch for 10 steps:")
print(f"  {'t':>4}  {'q_w':>8}  {'q_x':>8}  {'q_y':>8}  {'q_z':>8}  {'|q|':>6}")
for step in range(11):
    t = step * dt
    if step % 2 == 0:
        print(f"  {t:>4.0f}  {q[0]:>8.5f}  {q[1]:>8.5f}  {q[2]:>8.5f}  {q[3]:>8.5f}  "
              f"{sum(x**2 for x in q)**0.5:>6.4f}")
    if step < 10:
        qd = anvil.R.quaternion_kinematics(
            q_w=q[0], q_x=q[1], q_y=q[2], q_z=q[3],
            omega_x=omega_body[0], omega_y=omega_body[1], omega_z=omega_body[2]
        )
        # Euler integration
        q = [q[0]+qd['qw_dot']*dt, q[1]+qd['qx_dot']*dt,
             q[2]+qd['qy_dot']*dt, q[3]+qd['qz_dot']*dt]
        # Re-normalise
        n = sum(x**2 for x in q)**0.5
        q = [x/n for x in q]


# =============================================================================
# [6] TRIAD attitude determination
# =============================================================================

print("\n[6] TRIAD attitude determination (sun + magnetic field vectors)")

# Simulate: spacecraft rotated 30 deg about Z from reference
theta = np.radians(30)
C_true = np.array([[np.cos(theta), -np.sin(theta), 0],
                   [np.sin(theta),  np.cos(theta), 0],
                   [0,              0,             1]])

# Reference vectors in inertial frame
sun_ref  = np.array([0.8, 0.6, 0.0])
mag_ref  = np.array([0.3, 0.0, 0.95])

# Measurements in body frame (ideal, no noise)
sun_body = C_true @ sun_ref
mag_body = C_true @ mag_ref

result = anvil.R.triad_attitude(
    b1_x=sun_body[0], b1_y=sun_body[1], b1_z=sun_body[2],
    b2_x=mag_body[0], b2_y=mag_body[1], b2_z=mag_body[2],
    r1_x=sun_ref[0],  r1_y=sun_ref[1],  r1_z=sun_ref[2],
    r2_x=mag_ref[0],  r2_y=mag_ref[1],  r2_z=mag_ref[2],
)
print(f"  True rotation: 30 deg about Z")
print(f"  TRIAD result quaternion: w={result['q_w']:.5f}  x={result['q_x']:.5f}  "
      f"y={result['q_y']:.5f}  z={result['q_z']:.5f}")
print(f"  Expected q_z = sin(15 deg) = {np.sin(np.radians(15)):.5f}")


# =============================================================================
# [7] Euler equations — spin axis stability
# =============================================================================

print("\n[7] Euler equations — prolate vs oblate spin stability check")

# Spin about minor axis (prolate, Iz < Iy < Ix): UNSTABLE for intermediate axis
# Spin about major or minor axis: stable

cases = [
    ("Major axis (Iz>Iy>Ix, spin Z)",  (100, 80, 60), (0.01, 0.01, 1.0)),
    ("Minor axis (Iz<Iy<Ix, spin Z)",  (60, 80, 100), (0.01, 0.01, 1.0)),
    ("Intermediate (perturbed)",        (60, 100, 80), (0.01, 0.01, 1.0)),
]
for label, (Ix_,Iy_,Iz_), (ox,oy,oz) in cases:
    r = anvil.R.euler_equations(
        omega_x=ox, omega_y=oy, omega_z=oz, Ix=Ix_, Iy=Iy_, Iz=Iz_)
    alpha_perp = (r['alpha_x'].si**2 + r['alpha_y'].si**2)**0.5
    print(f"  {label:40s}: alpha_perp = {alpha_perp:.6f} rad/s²")


# =============================================================================
# [8] Power budget
# =============================================================================

print("\n[8] Power budget — 200 kg EO smallsat")

pwr = anvil.R.power_budget(
    P_load_W    = 80,
    T_orbit_min = 94.6,    # 500 km period
    eclipse_frac= ecl_worst['eclipse_frac'],
    eta_solar   = 0.30,    # 30% triple-junction GaAs
    flux_solar  = 1361.0,
    DOD         = 0.8,
    eta_battery = 0.9,
)
print(f"  Load power:     80 W  |  orbit period: 94.6 min  |  eclipse: {ecl_worst['eclipse_frac']*100:.1f}%")
print(f"  Solar array:    {pwr['A_panel_m2'].value:.2f} m²  (GaAs 30%)")
print(f"  Battery:        {pwr['E_bat_Wh']:.0f} Wh  →  {pwr['m_bat_kg'].value:.1f} kg Li-ion")
print(f"  Panel output:   {pwr['P_from_panel_W'].value:.0f} W")

# Sweep over eclipse fraction
pwr_sys = System("power_sizing")
pwr_sys.add("P_load_W",    80)
pwr_sys.add("T_orbit_min", 94.6)
pwr_sys.add("eclipse_frac", 0.35)
pwr_sys.add("eta_solar",    0.30)
pwr_sys.add("flux_solar",   1361.0)
pwr_sys.add("DOD",          0.8)
pwr_sys.add("eta_battery",  0.9)
pwr_sys.use("power_budget")

print("\n  Sensitivity: panel area vs eclipse fraction:")
sw = pwr_sys.sweep("eclipse_frac", np.linspace(0.1, 0.5, 5))
sw.summary(outputs=["eclipse_frac", "A_panel_m2", "E_bat_Wh", "m_bat_kg"])


# =============================================================================
# [9] Link budget — X-band downlink
# =============================================================================

print("\n[9] Link budget — X-band downlink at 500 km")

lnk = anvil.R.link_budget(
    P_tx_W    = 5,
    G_tx_dBi  = 3,       # patch antenna on spacecraft
    G_rx_dBi  = 47,      # 5 m parabolic dish ground station
    freq_Hz   = 8.4e9,
    distance_m= a_SSO,
    losses_dB = 4.0,
)
print(f"  Transmit power: 5 W  |  freq: 8.4 GHz  |  range: {a_SSO/1e3:.0f} km")
print(f"  FSPL:           {lnk['FSPL_dB']:.1f} dB")
print(f"  EIRP:           {lnk['EIRP_dBW']:.1f} dBW")
print(f"  Received power: {lnk['P_rx_dBW']:.1f} dBW  =  {lnk['P_rx_W'].value:.2e} W")

# Sweep range (elevation angle effect)
ranges_km = [400, 600, 800, 1200, 2000]
print(f"\n  {'Range (km)':>12}  {'FSPL (dB)':>10}  {'P_rx (dBW)':>12}")
for d in ranges_km:
    r = anvil.R.link_budget(P_tx_W=5, G_tx_dBi=3, G_rx_dBi=47, freq_Hz=8.4e9,
                             distance_m=d*1e3, losses_dB=4.0)
    print(f"  {d:>12}  {r['FSPL_dB']:>10.1f}  {r['P_rx_dBW']:>12.1f}")


# =============================================================================
# [10] Controls: attitude controller analysis
# =============================================================================

print("\n[10] Attitude controller analysis")

# Second-order response for pitch axis PD controller
# Plant: 1/(Iz*s²), Controller: Kp+Kd*s
# Open-loop: G(s) = (Kp+Kd*s)/(Iz*s²)  = (Kd*s+Kp)/(Iz*s²)
# Characteristic: Iz*s² + Kd*s + Kp = 0  -> omega_n=sqrt(Kp/Iz), zeta=Kd/(2*sqrt(Kp*Iz))

Kp, Kd = 0.15, 1.2
omega_n_pitch = (Kp/Iz)**0.5
zeta_pitch    = Kd / (2*(Kp*Iz)**0.5)

metrics = anvil.R.second_order_metrics(omega_n=omega_n_pitch, zeta=zeta_pitch)
print(f"  Pitch PD controller (Kp={Kp}, Kd={Kd}, Iz={Iz} kg*m²):")
print(f"    omega_n = {omega_n_pitch:.4f} rad/s  zeta = {zeta_pitch:.4f}")
print(f"    Overshoot: {metrics['overshoot_pct']:.1f}%")
print(f"    t_settle:  {metrics['t_settle']:.1f} s")
print(f"    t_rise:    {metrics['t_rise']:.1f} s")

# State-space stability check (pitch axis: x=[theta, theta_dot])
# x_dot = [theta_dot, (Kp*theta_err + Kd*theta_dot_err)/Iz ... simplified as]
# A = [[0, 1], [-Kp/Iz, -Kd/Iz]]
A_pitch = [0, 1, -Kp/Iz, -Kd/Iz]
poles = anvil.R.state_space_poles(A_flat=A_pitch, n_states=2)
print(f"\n  State-space poles: {[complex(round(r,4),round(i,4)) for r,i in zip(poles['poles_real'],poles['poles_imag'])]}")
print(f"  Stable: {poles['stable']}  min damping: {poles['min_damping']:.4f}")

# Gain/phase margin of open-loop G(s) = (Kd*s+Kp)/(Iz*s²)
gm = anvil.R.gain_phase_margin(
    num_coeffs=[Kd, Kp],
    den_coeffs=[Iz, 0, 0],
)
print(f"\n  Open-loop Bode margins:")
print(f"    GM = {gm['GM_dB']:.1f} dB  PM = {gm['PM_deg']:.1f} deg  stable = {gm['stable']}")

# LQR weights for a 3-state attitude controller
# States: [theta, phi, psi] (pitch, roll, yaw) max 5 deg each
# Inputs: [tau_pitch, tau_roll, tau_yaw] max 0.5 N*m each
q_lqr = anvil.R.lqr_bryson(
    state_bounds=[np.radians(5), np.radians(5), np.radians(5)],
    input_bounds=[0.5, 0.5, 0.5],
)
print(f"\n  LQR Bryson weights (max 5 deg, max 0.5 N*m):")
print(f"    Q_diag = {[round(x,1) for x in q_lqr['Q_diag']]}  (rad⁻²)")
print(f"    R_diag = {[round(x,2) for x in q_lqr['R_diag']]}  (N*m)⁻²")


# =============================================================================
# [11] Sphere of influence for Moon gravity assist planning
# =============================================================================

print("\n[11] Sphere of influence — Moon and Mars")

soi_moon = anvil.R.sphere_of_influence(
    a_body  = 384400e3,    # Moon orbital radius
    m_body  = 7.342e22,    # Moon mass
    m_parent= 5.972e24,    # Earth mass
)
soi_mars = anvil.R.sphere_of_influence(
    a_body  = 1.524 * 1.496e11,   # Mars orbital radius
    m_body  = 6.390e23,
    m_parent= 1.989e30,           # Sun mass
)
print(f"  Moon SOI: {soi_moon['r_SOI'].to('km').value:.0f} km  (expected 66100 km)")
print(f"  Mars SOI: {soi_mars['r_SOI'].to('km').value/1e3:.0f} thousand km  (expected ~577000 km)")


# =============================================================================
# [12] Bi-elliptic transfer study
# =============================================================================

print("\n[12] Hohmann vs bi-elliptic for LEO -> GEO")

r_LEO = R_E + 400e3
r_GEO = 42164e3

h = anvil.R.hohmann_transfer(mu=mu_E, r1=r_LEO, r2=r_GEO)
print(f"  Hohmann:      dv = {h['dv_total'].to('km/s').value:.3f} km/s  tof = {h['tof'].value/3600:.2f} h")

for r_b_km in [100000, 200000, 384400]:
    be = anvil.R.bielliptic_transfer(mu=mu_E, r1=r_LEO, r2=r_GEO, rb=r_b_km*1e3)
    print(f"  Bi-elliptic (rb={r_b_km:6d} km):  dv = {be['dv_total'].to('km/s').value:.3f} km/s"
          f"  tof = {be['tof'].value/3600:.1f} h")


print("\n" + "=" * 65)
print("  Done.")
print("=" * 65)
