# Built-in RSQs

57 RSQs across 10 domains, auto-seeded into `~/.anvil/registry.db` on first import. Access via `anvil.R.*`, `anvil.S.*`, `anvil.QDB.*`, or `sys.use("name")`.

All inputs are dimensionless scalars or SI floats unless noted. All outputs are SI units unless returned as `Q(value, "unit")`.

---

## Constants (`const`) — Type: Q

Accessed via `anvil.QDB.*`:

| Name | Value | Unit | Description |
|------|-------|------|-------------|
| `g0` | 9.80665 | m/s² | Standard gravitational acceleration |
| `R_universal` | 8.314462 | J/mol/K | Universal gas constant |
| `atm_pressure` | 101325 | Pa | Standard atmosphere |
| `sigma_sb` | 5.670374×10⁻⁸ | W/m²K⁴ | Stefan-Boltzmann constant |

```python
g0 = anvil.QDB.g0
print(g0)           # 9.8067 m/s^2
print(g0.to("ft/s^2"))  # 32.1740 ft/s^2
```

---

## Aerodynamics — Atmosphere (`aero.atmosphere`)

### `isa_atmosphere`

International Standard Atmosphere up to 86 km altitude.

```
Inputs:  h [m]  — geometric altitude
Outputs: T_atm [K], P_atm [Pa], rho_atm [kg/m³], a_atm [m/s],
         mu_atm [Pa*s], sigma (density ratio ρ/ρ₀)
```

```python
r = anvil.R.isa_atmosphere(h=10000)
# T_atm = 223.15 K  (-50°C)
# P_atm = 26436.9 Pa
# rho_atm = 0.4127 kg/m³
# a_atm = 299.5 m/s

r = anvil.R.isa_atmosphere(h=0)
# T_atm = 288.15 K  P_atm = 101325 Pa  rho_atm = 1.2250 kg/m³

r = anvil.R.isa_atmosphere(h=85000)  # near model limit
# T_atm = 270.6 K  P_atm = 110.9 Pa
```

**Layers implemented:**
- 0–11 km: Troposphere (T decreases at −6.5 K/km)
- 11–20 km: Lower Stratosphere (T = 216.65 K, isothermal)
- 20–32 km: Upper Stratosphere (T increases at +1 K/km)
- Above 32 km: Extended with pressure extrapolation

**Limit:** Model extends to ~86 km. Outputs above this are extrapolated and should be treated as approximate.

---

## Aerodynamics — Compressible (`aero.compressible`)

### `isentropic_ratios`

```
Inputs:  M, gamma=1.4
Outputs: T0_T (T₀/T), P0_P (P₀/P), rho0_rho (ρ₀/ρ)
```

```python
r = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
# T0_T = 1.8000    P0_P = 7.8244    rho0_rho = 4.3469

r = anvil.R.isentropic_ratios(M=0.0)
# T0_T = 1.0  P0_P = 1.0  rho0_rho = 1.0

r = anvil.R.isentropic_ratios(M=1.0)
# T0_T = 1.2000  P0_P = 1.8929  rho0_rho = 1.5774

r = anvil.R.isentropic_ratios(M=5.0)
# T0_T = 6.0  P0_P = 529.09  rho0_rho = 88.18
```

### `area_mach_supersonic`

Find supersonic Mach from area ratio (A/A*). Uses Brent's method.

```
Inputs:  area_ratio, gamma=1.4
Outputs: M_exit
```

```python
anvil.R.area_mach_supersonic(area_ratio=8.0, gamma=1.25)
# M_exit = 3.64  (approximate — depends on gamma)

anvil.R.area_mach_supersonic(area_ratio=1.0)
# M_exit = 1.001 (barely supersonic — root is very close to 1)
```

### `area_mach_subsonic`

Find subsonic Mach from area ratio (A/A*). Uses Brent's method.

```
Inputs:  area_ratio, gamma=1.4
Outputs: M_sub
```

```python
anvil.R.area_mach_subsonic(area_ratio=2.0)
# M_sub = 0.3059

anvil.R.area_mach_subsonic(area_ratio=1.0)
# M_sub = 0.999 (subsonic near-sonic)
```

### `normal_shock`

```
Inputs:  M1, gamma=1.4
Outputs: M2, P2_P1, T2_T1, rho2_rho1, P02_P01
```

```python
r = anvil.R.normal_shock(M1=2.0, gamma=1.4)
# M2 = 0.5774    P2_P1 = 4.5000    T2_T1 = 1.6875
# rho2_rho1 = 2.6667    P02_P01 = 0.7209

r = anvil.R.normal_shock(M1=1.0)
# M2 = 1.0  P2_P1 = 1.0  T2_T1 = 1.0  (no shock at M=1)

r = anvil.R.normal_shock(M1=5.0)
# M2 = 0.4152  P2_P1 = 29.0  T2_T1 = 5.800
```

**Limit:** `M1` must be ≥ 1 for a physical shock. No input guard — passing M1<1 returns mathematical results that are not physically meaningful.

### `prandtl_meyer`

```
Inputs:  M, gamma=1.4
Outputs: nu [rad], nu_deg [degrees]
```

```python
r = anvil.R.prandtl_meyer(M=2.0)
# nu = 0.4602 rad  nu_deg = 26.38°

r = anvil.R.prandtl_meyer(M=1.0)
# nu = 0.0 rad  nu_deg = 0.0° (no expansion at M=1)

r = anvil.R.prandtl_meyer(M=10.0)
# nu_deg = 100.7°
```

### `oblique_shock`

2D oblique shock for wedge half-angle `theta_deg`. Returns weak (attached) solution if it exists.

```
Inputs:  M1, theta_deg, gamma=1.4
Outputs: beta_deg, M2, p2_p1, T2_T1, rho2_rho1, attached [bool]
```

```python
r = anvil.R.oblique_shock(M1=3.0, theta_deg=20.0)
# beta_deg = 37.76  M2 = 1.994  p2_p1 = 3.31  attached=True

r = anvil.R.oblique_shock(M1=2.0, theta_deg=35.0)
# attached = False  (detached shock — theta exceeds max deflection)
# p2_p1 = nan  T2_T1 = nan  (NaN outputs when detached)
```

**Algorithm:** Solves the theta-beta-M equation numerically using Brent's method on the weak shock branch. Checks if any real solution exists (sign change in residual). Returns `attached=False` with NaN outputs if no attached solution exists.

---

## Aerodynamics — Performance (`aero.performance`)

### `dynamic_pressure`

```
Inputs:  rho [kg/m³], V [m/s]
Outputs: q_inf [Pa]
```

```python
anvil.R.dynamic_pressure(rho=1.225, V=100)
# q_inf = 6125.00 Pa
```

### `lift_force`

```
Inputs:  rho, V, S_ref [m²], CL
Outputs: lift [N]
```

### `drag_force`

```
Inputs:  rho, V, S_ref, CD
Outputs: drag [N]
```

### `thin_airfoil_cl`

Thin airfoil theory, with Prandtl-Glauert compressibility correction.

```
Inputs:  alpha_deg, alpha_L0_deg=0, M=0
Outputs: CL, CL_alpha [per rad]
```

```python
anvil.R.thin_airfoil_cl(alpha_deg=5.0)
# CL = 0.5483  CL_alpha = 6.2832 (2π)

anvil.R.thin_airfoil_cl(alpha_deg=5.0, M=0.6)
# CL = 0.6854  (Prandtl-Glauert compressibility correction)
```

**Limit:** `M < 1` only. At M=1 the Prandtl-Glauert formula has a singularity (1/√(1-M²) → ∞).

### `induced_drag`

```
Inputs:  CL, AR, e=0.85
Outputs: CDi
```

```python
anvil.R.induced_drag(CL=0.5, AR=8, e=0.85)
# CDi = 0.01179
```

### `drag_polar`

```
Inputs:  CL, CD0, AR, e=0.85
Outputs: CD, CDi, LoD
```

```python
r = anvil.R.drag_polar(CL=0.5, CD0=0.02, AR=8)
# CD = 0.0318  CDi = 0.0118  LoD = 15.77
```

### `oswald_efficiency`

Estimate Oswald span efficiency for straight wings.

```
Inputs:  AR, sweep_deg=0, taper=1
Outputs: e_oswald
```

```python
anvil.R.oswald_efficiency(AR=8, sweep_deg=0, taper=0.5)
# e_oswald ≈ 0.87 (approximate empirical formula)
```

### `stall_speed`

```
Inputs:  W [N], rho, S_ref [m²], CLmax
Outputs: V_stall [m/s]
```

```python
anvil.R.stall_speed(W=50000, rho=1.225, S_ref=20, CLmax=1.5)
# V_stall = 58.5 m/s
```

### `range_breguet`

Breguet range equation for jet aircraft.

```
Inputs:  V [m/s], TSFC [1/s], LoD, W_initial [N], W_final [N]
Outputs: range [m], range_km [km]
```

```python
r = anvil.R.range_breguet(V=250, TSFC=1.5e-5, LoD=15, W_initial=70000, W_final=55000)
# range = 6.029e7 m   range_km = 60290.5 km
```

**Note:** TSFC in 1/s (= thrust-specific fuel consumption per second). Convert from kg/N/hr: `TSFC_1s = TSFC_kgNhr / 3600`.

---

## Propulsion (`propulsion`)

### `nozzle_area_ratio`

```
Inputs:  A_exit [m²], A_throat [m²]
Outputs: area_ratio
```

### `exit_conditions`

Static conditions at nozzle exit from isentropic ratios.

```
Inputs:  T0, P0, T0_T, P0_P, gamma, R_gas
Outputs: T_exit [K], P_exit [Pa], a_exit [m/s]
```

### `exit_velocity`

```
Inputs:  M_exit, a_exit [m/s]
Outputs: V_exit [m/s]
```

### `choked_mass_flow`

Mass flow through a choked throat.

```
Inputs:  P0 [Pa], A_throat [m²], gamma, R_gas, T0 [K]
Outputs: mdot [kg/s]
```

### `rocket_thrust`

```
Inputs:  mdot [kg/s], V_exit [m/s], P_exit [Pa], P_amb [Pa], A_exit [m²]
Outputs: thrust [N]
```

### `specific_impulse`

```
Inputs:  thrust [N], mdot [kg/s]
Outputs: Isp [s]
```

### `tsiolkovsky`

```
Inputs:  Isp [s], mass_ratio (m_wet/m_dry)
Outputs: delta_v [m/s]
```

```python
anvil.R.tsiolkovsky(Isp=450, mass_ratio=3.0)
# delta_v = 4848.2 m/s

anvil.R.tsiolkovsky(Isp=315, mass_ratio=8.0)  # Falcon 9 approximate
# delta_v = 6429.9 m/s
```

### `rocket_nozzle` ★ — Pre-built System

The only built-in System (type "S"). A complete quasi-1D isentropic rocket nozzle.

**Default inputs:**
| Name | Value | Unit | Desc |
|------|-------|------|------|
| `P0` | 6.9e6 | Pa | Chamber pressure |
| `T0` | 3500 | K | Chamber temperature |
| `gamma` | 1.25 | — | Specific heat ratio |
| `R_gas` | 320 | J/kg/K | Gas constant |
| `A_throat` | 0.01 | m² | Throat area |
| `A_exit` | 0.08 | m² | Exit area |
| `P_amb` | 101325 | Pa | Ambient pressure |

**Computed outputs:** `area_ratio`, `M_exit`, `T0_T`, `P0_P`, `rho0_rho`, `T_exit`, `P_exit`, `a_exit`, `V_exit`, `mdot`, `thrust`, `Isp`

**Usage:**
```python
nozzle = anvil.S.rocket_nozzle.copy()  # always copy before modifying
nozzle.set(P0=10e6, T0=3500, A_exit=0.1, P_amb=0)
result = nozzle.solve_forward()

# Key outputs:
result["thrust"].to("kN")  # ~171 kN (vacuum)
result["Isp"]              # ~281 s
result["M_exit"]           # ~3.64
result["mdot"]             # ~12 kg/s
```

**Dependency chain (8 relations):**
```
nozzle_area_ratio → area_mach_supersonic → isentropic_ratios →
exit_conditions → exit_velocity + choked_mass_flow → rocket_thrust → specific_impulse
```

---

## Thermodynamics (`thermo`)

### `ideal_gas_density`

```
Inputs:  P [Pa], R_gas [J/kg/K], T [K]
Outputs: rho [kg/m³]
```

```python
anvil.R.ideal_gas_density(P=101325, R_gas=287.058, T=288.15)
# rho = 1.2250 kg/m³
```

### `speed_of_sound`

```
Inputs:  gamma, R_gas, T [K]
Outputs: a [m/s]
```

```python
anvil.R.speed_of_sound(gamma=1.4, R_gas=287.058, T=288.15)
# a = 340.29 m/s
```

### `sutherland_viscosity`

Sutherland's law for dynamic viscosity of gases.

```
Inputs:  T [K], T_ref=288.15, mu_ref=1.789e-5 [Pa*s], S=110.4 [K]
Outputs: mu [Pa*s]
```

```python
anvil.R.sutherland_viscosity(T=500)
# mu = 2.670e-5 Pa*s

anvil.R.sutherland_viscosity(T=1000)
# mu = 4.153e-5 Pa*s
```

### `reynolds_number`

```
Inputs:  rho, V, L_char [m], mu [Pa*s]
Outputs: Re (dimensionless)
```

```python
anvil.R.reynolds_number(rho=1.225, V=100, L_char=1.0, mu=1.789e-5)
# Re = 6,847,401
```

---

## Heat Transfer (`heat_transfer`)

### `conduction_1d`

Fourier's law: `Q = k·A·ΔT/L`

```
Inputs:  k [W/m/K], A_cross [m²], dT [K], L_thickness [m]
Outputs: Q_cond [W]
```

```python
anvil.R.conduction_1d(k=200, A_cross=0.01, dT=100, L_thickness=0.01)
# Q_cond = 20000 W
```

### `convection`

Newton's law of cooling: `Q = h·A·(T_surf - T_inf)`

```
Inputs:  h_conv [W/m²/K], A_surf [m²], T_surf [K], T_inf [K]
Outputs: Q_conv [W]
```

### `radiation`

Stefan-Boltzmann law: `Q = ε·σ·A·(T_hot⁴ - T_cold⁴)`

```
Inputs:  emissivity, A_surf [m²], T_hot [K], T_cold [K]
Outputs: Q_rad [W]
```

### `thermal_resistance_wall`

```
Inputs:  L_thickness [m], k [W/m/K], A_cross [m²]
Outputs: R_thermal [K/W]
```

### `fin_efficiency_rect`

Rectangular fin efficiency using the exact hyperbolic tangent formula.

```
Inputs:  h_conv [W/m²/K], k_fin [W/m/K], t_fin [m], L_fin [m]
Outputs: eta_fin, mL (fin parameter)
```

```python
r = anvil.R.fin_efficiency_rect(h_conv=50, k_fin=200, t_fin=0.003, L_fin=0.05)
# eta_fin = 0.8806  mL = 0.4082
```

---

## Structures (`structures`)

### `hooke_stress`

```
Inputs:  E [Pa], strain
Outputs: stress [Pa]
```

### `axial_stress`

```
Inputs:  F_axial [N], A_cross [m²]
Outputs: sigma_axial [Pa]
```

### `beam_deflection_cantilever`

Point load at tip of cantilever beam.

```
Inputs:  F_tip [N], L_beam [m], E [Pa], I_moment [m⁴]
Outputs: deflection [m], max_moment [N·m]
```

```python
r = anvil.R.beam_deflection_cantilever(F_tip=1000, L_beam=2, E=200e9, I_moment=1e-6)
# deflection = 0.013333 m    max_moment = 2000 N·m
```

Formula: `δ = F·L³/(3·E·I)`

### `beam_deflection_simply_supported`

Uniformly distributed load.

```
Inputs:  w_load [N/m], L_beam [m], E [Pa], I_moment [m⁴]
Outputs: deflection [m], max_moment [N·m]
```

Formula: `δ = 5·w·L⁴/(384·E·I)`

### `buckling_euler`

```
Inputs:  E [Pa], I_moment [m⁴], L_eff [m]
Outputs: P_critical [N]
```

```python
anvil.R.buckling_euler(E=200e9, I_moment=1e-6, L_eff=2.0)
# P_critical = 493,480 N
```

Formula: `P_cr = π²·E·I/(L_eff²)`

### `thin_wall_hoop_stress`

```
Inputs:  P_internal [Pa], r_inner [m], t_wall [m]
Outputs: sigma_hoop [Pa], sigma_axial [Pa]
```

```python
r = anvil.R.thin_wall_hoop_stress(P_internal=1e6, r_inner=0.1, t_wall=0.005)
# sigma_hoop = 20,000,000 Pa  sigma_axial = 10,000,000 Pa
```

---

## Controls (`controls`)

### `pid_output`

PID control law: `u = Kp·e + Ki·∫e + Kd·de/dt`

```
Inputs:  error, integral_error, derivative_error, Kp, Ki, Kd
Outputs: u_pid
```

```python
anvil.R.pid_output(error=1.0, integral_error=0.5, derivative_error=0.1,
                   Kp=2.0, Ki=0.5, Kd=0.1)
# u_pid = 2.0*1.0 + 0.5*0.5 + 0.1*0.1 = 2.26
```

**Note:** You must pre-compute `integral_error` and `derivative_error` externally. This RSQ is the control law only, not a full PID controller with state.

### `ziegler_nichols_pid`

```
Inputs:  Ku (ultimate gain), Tu (ultimate period), method="classic"
Outputs: Kp, Ki, Kd, Ti, Td
```

```python
r = anvil.R.ziegler_nichols_pid(Ku=10.0, Tu=2.0)
# Kp=6.00  Ki=6.00  Kd=1.50  Ti=1.0  Td=0.25
```

Methods: `"classic"` (Ziegler-Nichols), `"no_overshoot"`, `"some_overshoot"`, `"pessen_integral"`

### `first_order_step`

Step response metrics for a first-order system `G(s) = K/(τs+1)`.

```
Inputs:  K (gain), tau [s] (time constant), t_settle_criterion=0.02 (±2%)
Outputs: t_settle [s], t_rise [s], bandwidth_Hz [Hz]
```

### `second_order_metrics`

```
Inputs:  omega_n [rad/s], zeta
Outputs: overshoot_pct, t_peak [s], t_settle [s], t_rise [s], omega_d [rad/s]
```

```python
r = anvil.R.second_order_metrics(omega_n=10.0, zeta=0.5)
# overshoot_pct = 16.3%    t_settle = 0.800 s    t_rise = 0.181 s
# omega_d = 8.660 rad/s

r = anvil.R.second_order_metrics(omega_n=10.0, zeta=1.0)  # critically damped
# overshoot_pct = 0.0%
```

### `routh_hurwitz_2nd`

Routh-Hurwitz stability for 2nd order characteristic polynomial: `s² + a1·s + a0 = 0`

```
Inputs:  a1, a0
Outputs: stable [bool]
```

```python
anvil.R.routh_hurwitz_2nd(a1=2.0, a0=5.0)
# stable = True  (both coefficients positive)

anvil.R.routh_hurwitz_2nd(a1=-1.0, a0=5.0)
# stable = False  (negative a1)
```

**Stability condition:** Both `a1 > 0` and `a0 > 0`.

---

## Materials (`materials`)

### `safety_factor`

```
Inputs:  allowable_stress [Pa], applied_stress [Pa]
Outputs: safety_factor, margin_of_safety, pass [bool]
```

```python
r = anvil.R.safety_factor(allowable_stress=250e6, applied_stress=100e6)
# safety_factor = 2.50   margin_of_safety = 1.50   pass = True
```

`margin_of_safety = safety_factor - 1`

### `thermal_expansion_stress`

Thermal stress in constrained member: `σ = E·α·ΔT`

```
Inputs:  E [Pa], alpha_thermal [1/K], dT [K]
Outputs: sigma_thermal [Pa]
```

### `fatigue_life_basquin`

Basquin's power law: `σₐ = σ'f · (2N)^b`

```
Inputs:  sigma_a [Pa], sigma_f_prime [Pa], b_exponent
Outputs: N_cycles
```

```python
anvil.R.fatigue_life_basquin(sigma_a=300e6, sigma_f_prime=1000e6, b_exponent=-0.1)
# N_cycles = 84,700
```

### `miners_rule`

```
Inputs:  cycle_counts [list], cycle_limits [list]
Outputs: damage_index, failed [bool], remaining_life_fraction
```

### `fracture_toughness_check`

```
Inputs:  sigma [Pa], a_crack [m], KIc [Pa·m^0.5], F_geometry=1.12
Outputs: KI [Pa·m^0.5], safety_factor, failed [bool]
```

```python
r = anvil.R.fracture_toughness_check(sigma=200e6, a_crack=0.01, KIc=50e6)
# KI = 39,703,000  safety_factor = 1.26  failed = False
```

`KI = F·σ·√(π·a)`

### `composite_laminate_stiffness`

Rule of mixtures for unidirectional composite laminate.

```
Inputs:  Ef [Pa], Em [Pa], Gf [Pa], Gm [Pa], nu_f, nu_m, Vf
Outputs: E1 [Pa], E2 [Pa], G12 [Pa], nu12
```

---

## Orbital Mechanics (`orbital`)

### `vis_viva`

```
Inputs:  mu [m³/s²], r [m], a [m]
Outputs: V_orbital [m/s]
```

```python
# LEO circular orbit
anvil.R.vis_viva(mu=3.986e14, r=6.571e6, a=6.571e6)
# V_orbital = 7784.3 m/s

# GTO apogee
anvil.R.vis_viva(mu=3.986e14, r=42164e3, a=(6.571e6+42164e3)/2)
# V_orbital = 1596.5 m/s
```

### `hohmann_transfer`

```
Inputs:  mu [m³/s²], r1 [m], r2 [m]
Outputs: dv1 [m/s], dv2 [m/s], dv_total [m/s], tof [s]
```

```python
r = anvil.R.hohmann_transfer(mu=3.986e14, r1=6.571e6, r2=42164e3)
# dv1 = 2427 m/s  dv2 = 1508 m/s  dv_total = 3934.7 m/s
# tof = 19116 s = 5.31 hours
```

### `orbital_period`

```
Inputs:  mu [m³/s²], a [m]
Outputs: T_orbital [s]
```

```python
anvil.R.orbital_period(mu=3.986e14, a=6.571e6)
# T_orbital = 5303 s = 88.4 minutes  (LEO)
```

---

## Quick Reference — All 57 RSQs

| Name | Domain | Type | Key inputs | Key outputs |
|------|--------|------|-----------|------------|
| `g0` | const | Q | — | 9.80665 m/s² |
| `R_universal` | const | Q | — | 8.314 J/mol/K |
| `atm_pressure` | const | Q | — | 101325 Pa |
| `sigma_sb` | const | Q | — | 5.67e-8 W/m²K⁴ |
| `isa_atmosphere` | aero.atmosphere | R | h | T_atm, P_atm, rho_atm, a_atm, mu_atm |
| `isentropic_ratios` | aero.compressible | R | M, gamma | T0_T, P0_P, rho0_rho |
| `area_mach_supersonic` | aero.compressible | R | area_ratio, gamma | M_exit |
| `area_mach_subsonic` | aero.compressible | R | area_ratio, gamma | M_sub |
| `normal_shock` | aero.compressible | R | M1, gamma | M2, P2_P1, T2_T1, rho2_rho1, P02_P01 |
| `prandtl_meyer` | aero.compressible | R | M, gamma | nu, nu_deg |
| `oblique_shock` | aero.compressible | R | M1, theta_deg, gamma | beta_deg, M2, p2_p1, T2_T1, attached |
| `dynamic_pressure` | aero | R | rho, V | q_inf |
| `lift_force` | aero | R | rho, V, S_ref, CL | lift |
| `drag_force` | aero | R | rho, V, S_ref, CD | drag |
| `thin_airfoil_cl` | aero.performance | R | alpha_deg, alpha_L0_deg, M | CL, CL_alpha |
| `induced_drag` | aero.performance | R | CL, AR, e | CDi |
| `drag_polar` | aero.performance | R | CL, CD0, AR, e | CD, CDi, LoD |
| `oswald_efficiency` | aero.performance | R | AR, sweep_deg, taper | e_oswald |
| `stall_speed` | aero.performance | R | W, rho, S_ref, CLmax | V_stall |
| `range_breguet` | aero.performance | R | V, TSFC, LoD, W_initial, W_final | range, range_km |
| `nozzle_area_ratio` | propulsion | R | A_exit, A_throat | area_ratio |
| `exit_conditions` | propulsion | R | T0, P0, T0_T, P0_P, gamma, R_gas | T_exit, P_exit, a_exit |
| `exit_velocity` | propulsion | R | M_exit, a_exit | V_exit |
| `choked_mass_flow` | propulsion | R | P0, A_throat, gamma, R_gas, T0 | mdot |
| `rocket_thrust` | propulsion | R | mdot, V_exit, P_exit, P_amb, A_exit | thrust |
| `specific_impulse` | propulsion | R | thrust, mdot | Isp |
| `tsiolkovsky` | propulsion | R | Isp, mass_ratio | delta_v |
| `rocket_nozzle` | propulsion | **S** | P0, T0, gamma, R_gas, A_throat, A_exit, P_amb | M_exit, thrust, Isp, mdot, … |
| `ideal_gas_density` | thermo | R | P, R_gas, T | rho |
| `speed_of_sound` | thermo | R | gamma, R_gas, T | a |
| `sutherland_viscosity` | thermo | R | T, T_ref, mu_ref, S | mu |
| `reynolds_number` | thermo | R | rho, V, L_char, mu | Re |
| `conduction_1d` | heat_transfer | R | k, A_cross, dT, L_thickness | Q_cond |
| `convection` | heat_transfer | R | h_conv, A_surf, T_surf, T_inf | Q_conv |
| `radiation` | heat_transfer | R | emissivity, A_surf, T_hot, T_cold | Q_rad |
| `thermal_resistance_wall` | heat_transfer | R | L_thickness, k, A_cross | R_thermal |
| `fin_efficiency_rect` | heat_transfer | R | h_conv, k_fin, t_fin, L_fin | eta_fin, mL |
| `hooke_stress` | structures | R | E, strain | stress |
| `axial_stress` | structures | R | F_axial, A_cross | sigma_axial |
| `beam_deflection_cantilever` | structures | R | F_tip, L_beam, E, I_moment | deflection, max_moment |
| `beam_deflection_simply_supported` | structures | R | w_load, L_beam, E, I_moment | deflection, max_moment |
| `buckling_euler` | structures | R | E, I_moment, L_eff | P_critical |
| `thin_wall_hoop_stress` | structures | R | P_internal, r_inner, t_wall | sigma_hoop, sigma_axial |
| `pid_output` | controls | R | error, integral_error, derivative_error, Kp, Ki, Kd | u_pid |
| `ziegler_nichols_pid` | controls | R | Ku, Tu, method | Kp, Ki, Kd, Ti, Td |
| `first_order_step` | controls | R | K, tau, t_settle_criterion | t_settle, t_rise, bandwidth_Hz |
| `second_order_metrics` | controls | R | omega_n, zeta | overshoot_pct, t_peak, t_settle, t_rise, omega_d |
| `routh_hurwitz_2nd` | controls | R | a1, a0 | stable |
| `safety_factor` | materials | R | allowable_stress, applied_stress | safety_factor, margin, pass |
| `thermal_expansion_stress` | materials | R | E, alpha_thermal, dT | sigma_thermal |
| `fatigue_life_basquin` | materials | R | sigma_a, sigma_f_prime, b_exponent | N_cycles |
| `miners_rule` | materials | R | cycle_counts, cycle_limits | damage_index, failed, remaining_life_fraction |
| `fracture_toughness_check` | materials | R | sigma, a_crack, KIc, F_geometry | KI, safety_factor, failed |
| `composite_laminate_stiffness` | materials | R | Ef, Em, Gf, Gm, nu_f, nu_m, Vf | E1, E2, G12, nu12 |
| `vis_viva` | orbital | R | mu, r, a | V_orbital |
| `hohmann_transfer` | orbital | R | mu, r1, r2 | dv1, dv2, dv_total, tof |
| `orbital_period` | orbital | R | mu, a | T_orbital |
