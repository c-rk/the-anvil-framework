"""
Anvil seed library -- fundamental Relations that ship with the framework.

Call seed() to populate the local registry with these built-in RSQs.
This runs automatically on first import if the registry is empty.
Namespace loading is deferred (lazy) to avoid circular imports.
"""

from anvil.registry import _get_store


def seed(force=False):
    """Populate the registry database with built-in RSQs."""
    store = _get_store()
    builtin_names = {e["name"] for e in _SEED_ENTRIES}
    existing_builtins = {r["name"] for r in store.get_all(origin="builtin")}
    if not force and builtin_names <= existing_builtins:
        return
    for entry in _SEED_ENTRIES:
        store.put(
            name=entry["name"], rsq_type=entry["type"], source=entry["source"],
            domain=entry.get("domain", ""), version=entry.get("version", "0.1.0"),
            description=entry.get("desc", ""), tags=entry.get("tags", []),
            depends=entry.get("depends", []), origin="builtin",
        )


_SEED_ENTRIES = [
    # ==================== CONSTANTS ====================
    {"name": "g0", "type": "Q", "domain": "const",
     "desc": "Standard gravitational acceleration", "tags": ["constant", "gravity"],
     "source": 'from anvil import Q\nexport = Q(9.80665, "m/s^2", name="g0")'},
    {"name": "R_universal", "type": "Q", "domain": "const",
     "desc": "Universal gas constant", "tags": ["constant", "gas"],
     "source": 'from anvil import Q\nexport = Q(8.314462618, "J/mol/K", name="R_universal")'},
    {"name": "atm_pressure", "type": "Q", "domain": "const",
     "desc": "Standard atmospheric pressure", "tags": ["constant", "atmosphere"],
     "source": 'from anvil import Q\nexport = Q(101325.0, "Pa", name="atm_pressure")'},
    {"name": "sigma_sb", "type": "Q", "domain": "const",
     "desc": "Stefan-Boltzmann constant", "tags": ["constant", "radiation", "thermal"],
     "source": 'from anvil import Q\nexport = Q(5.670374419e-8, "W", name="sigma_sb")'},

    # ==================== AERO: COMPRESSIBLE ====================
    {"name": "isentropic_ratios", "type": "R", "domain": "aero.compressible",
     "desc": "Isentropic stagnation-to-static ratios from Mach number",
     "tags": ["compressible", "isentropic", "mach"],
     "source": 'def isentropic_ratios(M, gamma=1.4):\n    T_ratio = 1 + ((gamma - 1) / 2) * M**2\n    P_ratio = T_ratio ** (gamma / (gamma - 1))\n    rho_ratio = T_ratio ** (1 / (gamma - 1))\n    return {"T0_T": T_ratio, "P0_P": P_ratio, "rho0_rho": rho_ratio}\nexport = isentropic_ratios'},
    {"name": "area_mach_supersonic", "type": "R", "domain": "aero.compressible",
     "desc": "Supersonic Mach from area ratio (A/A*)", "tags": ["compressible", "nozzle", "mach"],
     "source": 'from anvil import solvers\ndef area_mach_supersonic(area_ratio, gamma=1.4):\n    def residual(M):\n        t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)\n        return (1/M)*t**((gamma+1)/(2*(gamma-1))) - area_ratio\n    M = solvers.find_root(residual, bracket=(1.001, 30.0))\n    return {"M_exit": M}\nexport = area_mach_supersonic'},
    {"name": "area_mach_subsonic", "type": "R", "domain": "aero.compressible",
     "desc": "Subsonic Mach from area ratio (A/A*)", "tags": ["compressible", "mach"],
     "source": 'from anvil import solvers\ndef area_mach_subsonic(area_ratio, gamma=1.4):\n    def residual(M):\n        t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)\n        return (1/M)*t**((gamma+1)/(2*(gamma-1))) - area_ratio\n    M = solvers.find_root(residual, bracket=(0.001, 0.999))\n    return {"M_sub": M}\nexport = area_mach_subsonic'},
    {"name": "normal_shock", "type": "R", "domain": "aero.compressible",
     "desc": "Normal shock relations", "tags": ["compressible", "shock"],
     "source": 'def normal_shock(M1, gamma=1.4):\n    M1sq = M1**2\n    M2sq = (1+(gamma-1)/2*M1sq)/(gamma*M1sq-(gamma-1)/2)\n    M2 = M2sq**0.5\n    P2_P1 = 1+2*gamma/(gamma+1)*(M1sq-1)\n    T2_T1 = P2_P1*(2+(gamma-1)*M1sq)/((gamma+1)*M1sq)\n    rho2_rho1 = (gamma+1)*M1sq/(2+(gamma-1)*M1sq)\n    P02_P01 = ((((gamma+1)*M1sq)/(2+(gamma-1)*M1sq))**(gamma/(gamma-1)))*((2*gamma*M1sq-(gamma-1))/(gamma+1))**(-1/(gamma-1))\n    return {"M2":M2,"P2_P1":P2_P1,"T2_T1":T2_T1,"rho2_rho1":rho2_rho1,"P02_P01":P02_P01}\nexport = normal_shock'},
    {"name": "prandtl_meyer", "type": "R", "domain": "aero.compressible",
     "desc": "Prandtl-Meyer expansion angle", "tags": ["compressible", "expansion"],
     "source": 'import numpy as np\ndef prandtl_meyer(M, gamma=1.4):\n    g = gamma\n    term = ((g+1)/(g-1))**0.5\n    nu = term*np.arctan(((M**2-1)/((g+1)/(g-1)))**0.5) - np.arctan((M**2-1)**0.5)\n    return {"nu": nu, "nu_deg": np.degrees(nu)}\nexport = prandtl_meyer'},
    {"name": "dynamic_pressure", "type": "R", "domain": "aero",
     "desc": "Dynamic pressure: q = 0.5 * rho * V^2", "tags": ["aerodynamics", "pressure"],
     "source": 'from anvil import Q\ndef dynamic_pressure(rho, V):\n    return {"q_inf": Q(0.5*rho*V**2, "Pa")}\nexport = dynamic_pressure'},
    {"name": "lift_force", "type": "R", "domain": "aero",
     "desc": "Lift force: L = 0.5 * rho * V^2 * S * CL", "tags": ["aerodynamics", "lift"],
     "source": 'from anvil import Q\ndef lift_force(rho, V, S_ref, CL):\n    return {"lift": Q(0.5*rho*V**2*S_ref*CL, "N")}\nexport = lift_force'},
    {"name": "drag_force", "type": "R", "domain": "aero",
     "desc": "Drag force: D = 0.5 * rho * V^2 * S * CD", "tags": ["aerodynamics", "drag"],
     "source": 'from anvil import Q\ndef drag_force(rho, V, S_ref, CD):\n    return {"drag": Q(0.5*rho*V**2*S_ref*CD, "N")}\nexport = drag_force'},

    # ==================== PROPULSION ====================
    {"name": "nozzle_area_ratio", "type": "R", "domain": "propulsion",
     "desc": "Exit-to-throat area ratio", "tags": ["nozzle", "geometry"],
     "source": 'def nozzle_area_ratio(A_exit, A_throat):\n    return {"area_ratio": A_exit / A_throat}\nexport = nozzle_area_ratio'},
    {"name": "exit_conditions", "type": "R", "domain": "propulsion",
     "desc": "Nozzle exit static conditions", "tags": ["nozzle", "propulsion"],
     "source": 'from anvil import Q\ndef exit_conditions(T0, P0, T0_T, P0_P, gamma, R_gas):\n    T_exit = T0/T0_T\n    P_exit = P0/P0_P\n    a_exit = (gamma*R_gas*T_exit)**0.5\n    return {"T_exit": Q(T_exit,"K"), "P_exit": Q(P_exit,"Pa"), "a_exit": Q(a_exit,"m/s")}\nexport = exit_conditions'},
    {"name": "exit_velocity", "type": "R", "domain": "propulsion",
     "desc": "Exit velocity", "tags": ["nozzle", "velocity"],
     "source": 'from anvil import Q\ndef exit_velocity(M_exit, a_exit):\n    return {"V_exit": Q(M_exit*a_exit, "m/s")}\nexport = exit_velocity'},
    {"name": "choked_mass_flow", "type": "R", "domain": "propulsion",
     "desc": "Mass flow through choked throat", "tags": ["nozzle", "mass_flow"],
     "source": 'from anvil import Q\ndef choked_mass_flow(P0, A_throat, gamma, R_gas, T0):\n    t = (2/(gamma+1))**((gamma+1)/(2*(gamma-1)))\n    mdot = P0*A_throat*(gamma/(R_gas*T0))**0.5*t\n    return {"mdot": Q(mdot, "kg/s")}\nexport = choked_mass_flow'},
    {"name": "rocket_thrust", "type": "R", "domain": "propulsion",
     "desc": "Rocket thrust", "tags": ["propulsion", "thrust"],
     "source": 'from anvil import Q\ndef rocket_thrust(mdot, V_exit, P_exit, P_amb, A_exit):\n    F = mdot*V_exit + (P_exit-P_amb)*A_exit\n    return {"thrust": Q(F, "N")}\nexport = rocket_thrust'},
    {"name": "specific_impulse", "type": "R", "domain": "propulsion",
     "desc": "Specific impulse", "tags": ["propulsion", "isp"],
     "source": 'from anvil import Q\ndef specific_impulse(thrust, mdot):\n    return {"Isp": Q(thrust/(mdot*9.80665), "s")}\nexport = specific_impulse'},
    {"name": "tsiolkovsky", "type": "R", "domain": "propulsion",
     "desc": "Tsiolkovsky rocket equation: dV = Isp * g0 * ln(m0/mf)",
     "tags": ["propulsion", "rocket", "delta_v"],
     "source": 'import numpy as np\nfrom anvil import Q\ndef tsiolkovsky(Isp, mass_ratio):\n    dv = Isp * 9.80665 * np.log(mass_ratio)\n    return {"delta_v": Q(dv, "m/s")}\nexport = tsiolkovsky'},

    # ==================== PROPULSION: NOZZLE SYSTEM ====================
    {"name": "rocket_nozzle", "type": "S", "domain": "propulsion",
     "desc": "Quasi-1D isentropic rocket nozzle with thrust and Isp",
     "tags": ["nozzle", "propulsion", "rocket", "system"],
     "depends": ["nozzle_area_ratio", "area_mach_supersonic", "isentropic_ratios",
                  "exit_conditions", "exit_velocity", "choked_mass_flow",
                  "rocket_thrust", "specific_impulse"],
     "source": 'from anvil import Q, System\ndef build():\n    s = System("rocket_nozzle")\n    s.add("P0", 6.9e6, "Pa", desc="Chamber pressure")\n    s.add("T0", 3500, "K", desc="Chamber temperature")\n    s.add("gamma", 1.25, desc="Ratio of specific heats")\n    s.add("R_gas", 320, "J/kg/K", desc="Specific gas constant")\n    s.add("A_throat", 0.01, "m^2", desc="Throat area")\n    s.add("A_exit", 0.08, "m^2", desc="Exit area")\n    s.add("P_amb", 101325, "Pa", desc="Ambient pressure")\n    s.use("nozzle_area_ratio")\n    s.use("area_mach_supersonic")\n    s.use("isentropic_ratios", map={"M": "M_exit"})\n    s.use("exit_conditions")\n    s.use("exit_velocity")\n    s.use("choked_mass_flow")\n    s.use("rocket_thrust")\n    s.use("specific_impulse")\n    return s\nexport = build'},

    # ==================== THERMODYNAMICS ====================
    {"name": "ideal_gas_density", "type": "R", "domain": "thermo",
     "desc": "Ideal gas density: rho = P / (R * T)", "tags": ["thermodynamics", "density"],
     "source": 'from anvil import Q\ndef ideal_gas_density(P, R_gas, T):\n    return {"rho": Q(P/(R_gas*T), "kg/m^3")}\nexport = ideal_gas_density'},
    {"name": "speed_of_sound", "type": "R", "domain": "thermo",
     "desc": "Speed of sound in ideal gas", "tags": ["thermodynamics", "acoustics"],
     "source": 'from anvil import Q\ndef speed_of_sound(gamma, R_gas, T):\n    return {"a": Q((gamma*R_gas*T)**0.5, "m/s")}\nexport = speed_of_sound'},
    {"name": "sutherland_viscosity", "type": "R", "domain": "thermo",
     "desc": "Sutherland's law for dynamic viscosity of a gas",
     "tags": ["thermodynamics", "viscosity", "transport"],
     "source": 'from anvil import Q\ndef sutherland_viscosity(T, T_ref=288.15, mu_ref=1.789e-5, S=110.4):\n    mu = mu_ref * (T/T_ref)**1.5 * (T_ref + S) / (T + S)\n    return {"mu": Q(mu, "Pa*s")}\nexport = sutherland_viscosity'},
    {"name": "reynolds_number", "type": "R", "domain": "thermo",
     "desc": "Reynolds number: Re = rho * V * L / mu",
     "tags": ["fluid", "dimensionless", "reynolds"],
     "source": 'def reynolds_number(rho, V, L_char, mu):\n    return {"Re": rho * V * L_char / mu}\nexport = reynolds_number'},

    # ==================== HEAT TRANSFER ====================
    {"name": "conduction_1d", "type": "R", "domain": "heat_transfer",
     "desc": "1D steady conduction: Q = k * A * dT / L",
     "tags": ["heat_transfer", "conduction", "fourier"],
     "source": 'from anvil import Q\ndef conduction_1d(k, A_cross, dT, L_thickness):\n    Q_dot = k * A_cross * dT / L_thickness\n    return {"Q_cond": Q(Q_dot, "W")}\nexport = conduction_1d'},
    {"name": "convection", "type": "R", "domain": "heat_transfer",
     "desc": "Newton's law of cooling: Q = h * A * (T_s - T_inf)",
     "tags": ["heat_transfer", "convection", "newton"],
     "source": 'from anvil import Q\ndef convection(h_conv, A_surf, T_surf, T_inf):\n    Q_dot = h_conv * A_surf * (T_surf - T_inf)\n    return {"Q_conv": Q(Q_dot, "W")}\nexport = convection'},
    {"name": "radiation", "type": "R", "domain": "heat_transfer",
     "desc": "Radiation heat transfer: Q = eps * sigma * A * (T1^4 - T2^4)",
     "tags": ["heat_transfer", "radiation", "stefan_boltzmann"],
     "source": 'from anvil import Q\ndef radiation(emissivity, A_surf, T_hot, T_cold):\n    sigma = 5.670374419e-8\n    Q_dot = emissivity * sigma * A_surf * (T_hot**4 - T_cold**4)\n    return {"Q_rad": Q(Q_dot, "W")}\nexport = radiation'},
    {"name": "thermal_resistance_wall", "type": "R", "domain": "heat_transfer",
     "desc": "Thermal resistance of a plane wall: R = L / (k * A)",
     "tags": ["heat_transfer", "resistance", "conduction"],
     "source": 'def thermal_resistance_wall(L_thickness, k, A_cross):\n    return {"R_thermal": L_thickness / (k * A_cross)}\nexport = thermal_resistance_wall'},
    {"name": "fin_efficiency_rect", "type": "R", "domain": "heat_transfer",
     "desc": "Rectangular fin efficiency: eta = tanh(mL) / (mL)",
     "tags": ["heat_transfer", "fin", "extended_surface"],
     "source": 'import numpy as np\ndef fin_efficiency_rect(h_conv, k_fin, t_fin, L_fin):\n    P = 2 * (1 + t_fin)  # perimeter per unit depth (approx for wide fin)\n    Ac = t_fin * 1  # cross section per unit depth\n    m = (h_conv * P / (k_fin * Ac))**0.5\n    mL = m * L_fin\n    eta = np.tanh(mL) / mL if mL > 0.01 else 1.0\n    return {"eta_fin": eta, "mL": mL}\nexport = fin_efficiency_rect'},

    # ==================== STRUCTURES ====================
    {"name": "hooke_stress", "type": "R", "domain": "structures",
     "desc": "Hooke's law: stress = E * strain", "tags": ["structures", "stress", "elastic"],
     "source": 'from anvil import Q\ndef hooke_stress(E, strain):\n    return {"stress": Q(E * strain, "Pa")}\nexport = hooke_stress'},
    {"name": "axial_stress", "type": "R", "domain": "structures",
     "desc": "Axial stress: sigma = F / A", "tags": ["structures", "stress", "axial"],
     "source": 'from anvil import Q\ndef axial_stress(F_axial, A_cross):\n    return {"sigma_axial": Q(F_axial / A_cross, "Pa")}\nexport = axial_stress'},
    {"name": "beam_deflection_cantilever", "type": "R", "domain": "structures",
     "desc": "Cantilever beam tip deflection under point load: delta = F*L^3 / (3*E*I)",
     "tags": ["structures", "beam", "deflection", "cantilever"],
     "source": 'from anvil import Q\ndef beam_deflection_cantilever(F_tip, L_beam, E, I_moment):\n    delta = F_tip * L_beam**3 / (3 * E * I_moment)\n    return {"deflection": Q(delta, "m"), "max_moment": Q(F_tip * L_beam, "N")}\nexport = beam_deflection_cantilever'},
    {"name": "beam_deflection_simply_supported", "type": "R", "domain": "structures",
     "desc": "Simply supported beam center deflection under uniform load: delta = 5*w*L^4 / (384*E*I)",
     "tags": ["structures", "beam", "deflection"],
     "source": 'from anvil import Q\ndef beam_deflection_simply_supported(w_load, L_beam, E, I_moment):\n    delta = 5 * w_load * L_beam**4 / (384 * E * I_moment)\n    max_M = w_load * L_beam**2 / 8\n    return {"deflection": Q(delta, "m"), "max_moment": Q(max_M, "N")}\nexport = beam_deflection_simply_supported'},
    {"name": "buckling_euler", "type": "R", "domain": "structures",
     "desc": "Euler buckling critical load: Pcr = pi^2 * E * I / L_eff^2",
     "tags": ["structures", "buckling", "stability"],
     "source": 'import numpy as np\nfrom anvil import Q\ndef buckling_euler(E, I_moment, L_eff):\n    Pcr = np.pi**2 * E * I_moment / L_eff**2\n    return {"P_critical": Q(Pcr, "N")}\nexport = buckling_euler'},
    {"name": "thin_wall_hoop_stress", "type": "R", "domain": "structures",
     "desc": "Hoop stress in thin-walled pressure vessel: sigma = P*r/t",
     "tags": ["structures", "pressure_vessel", "hoop"],
     "source": 'from anvil import Q\ndef thin_wall_hoop_stress(P_internal, r_inner, t_wall):\n    sigma_h = P_internal * r_inner / t_wall\n    sigma_a = P_internal * r_inner / (2 * t_wall)\n    return {"sigma_hoop": Q(sigma_h, "Pa"), "sigma_axial": Q(sigma_a, "Pa")}\nexport = thin_wall_hoop_stress'},

    # ==================== AERO: OBLIQUE SHOCK ====================
    {"name": "oblique_shock", "type": "R", "domain": "aero.compressible",
     "desc": "2D oblique shock: shock angle, downstream M, pressure/temperature ratios",
     "tags": ["compressible", "shock", "oblique", "wedge"],
     "source": (
         'import numpy as np\nfrom anvil import solvers\n'
         'def oblique_shock(M1, theta_deg, gamma=1.4):\n'
         '    """Oblique shock: weak (attached) solution for wedge half-angle theta_deg.\n'
         '    The theta-beta-M function starts at 0 (at Mach angle mu), rises to a\n'
         '    maximum deflection, then falls back to 0 at beta=90. Both endpoints are\n'
         '    below theta for attached shocks, so we sample to find the sign-change\n'
         '    bracket near the weak-shock crossing.\n'
         '    """\n'
         '    theta = np.radians(theta_deg)\n'
         '    mu = np.arcsin(1.0 / M1)\n'
         '    def tbm(beta):\n'
         '        sb2 = np.sin(beta)**2\n'
         '        num = M1**2 * sb2 - 1.0\n'
         '        den = M1**2 * (gamma + np.cos(2.0*beta)) + 2.0\n'
         '        tb  = abs(np.tan(beta))\n'
         '        if tb < 1e-14: return 0.0\n'
         '        return np.arctan(2.0 / tb * num / den)\n'
         '    betas = np.linspace(mu + 0.001, np.pi/2 - 0.001, 500)\n'
         '    vals  = np.array([tbm(b) for b in betas])\n'
         '    if vals.max() <= theta:\n'
         '        return {"beta_deg": float("nan"), "M2": float("nan"),\n'
         '                "p2_p1": float("nan"), "T2_T1": float("nan"),\n'
         '                "rho2_rho1": float("nan"), "attached": False}\n'
         '    resid = vals - theta\n'
         '    # Weak shock: first upward crossing (vals rising through theta)\n'
         '    cross = np.where((resid[:-1] < 0) & (resid[1:] >= 0))[0]\n'
         '    if len(cross) == 0:\n'
         '        cross = np.where((resid[:-1] >= 0) & (resid[1:] < 0))[0]\n'
         '    if len(cross) == 0:\n'
         '        return {"beta_deg": float("nan"), "M2": float("nan"),\n'
         '                "p2_p1": float("nan"), "T2_T1": float("nan"),\n'
         '                "rho2_rho1": float("nan"), "attached": False}\n'
         '    idx = int(cross[0])\n'
         '    beta = solvers.find_root(lambda b: tbm(b) - theta,\n'
         '                            bracket=(float(betas[idx]), float(betas[idx+1])),\n'
         '                            method="brent", tol=1e-12)\n'
         '    M1n       = M1 * np.sin(beta)\n'
         '    M2n2      = (1+(gamma-1)/2*M1n**2) / (gamma*M1n**2-(gamma-1)/2)\n'
         '    M2        = np.sqrt(max(M2n2, 0.0)) / np.sin(beta - theta)\n'
         '    p2_p1     = 1 + 2*gamma/(gamma+1)*(M1n**2 - 1)\n'
         '    T2_T1     = p2_p1*(2+(gamma-1)*M1n**2) / ((gamma+1)*M1n**2)\n'
         '    rho2_rho1 = (gamma+1)*M1n**2 / (2+(gamma-1)*M1n**2)\n'
         '    return {"beta_deg": float(np.degrees(beta)), "M2": float(M2),\n'
         '            "p2_p1": float(p2_p1), "T2_T1": float(T2_T1),\n'
         '            "rho2_rho1": float(rho2_rho1), "attached": True}\n'
         'export = oblique_shock'
     )},

    # ==================== ORBITAL MECHANICS ====================
    {"name": "vis_viva", "type": "R", "domain": "orbital",
     "desc": "Vis-viva equation: V = sqrt(mu * (2/r - 1/a))",
     "tags": ["orbital", "velocity", "kepler"],
     "source": 'from anvil import Q\ndef vis_viva(mu, r, a):\n    V = (mu*(2/r - 1/a))**0.5\n    return {"V_orbital": Q(V, "m/s")}\nexport = vis_viva'},
    {"name": "hohmann_transfer", "type": "R", "domain": "orbital",
     "desc": "Hohmann transfer delta-V between two circular orbits",
     "tags": ["orbital", "transfer", "hohmann", "delta_v"],
     "source": 'import numpy as np\nfrom anvil import Q\ndef hohmann_transfer(mu, r1, r2):\n    a_t = (r1 + r2) / 2\n    v1 = (mu / r1)**0.5\n    v2 = (mu / r2)**0.5\n    v_t1 = (mu * (2/r1 - 1/a_t))**0.5\n    v_t2 = (mu * (2/r2 - 1/a_t))**0.5\n    dv1 = abs(v_t1 - v1)\n    dv2 = abs(v2 - v_t2)\n    return {"dv1": Q(dv1, "m/s"), "dv2": Q(dv2, "m/s"), "dv_total": Q(dv1+dv2, "m/s"), "tof": Q(np.pi*(a_t**3/mu)**0.5, "s")}\nexport = hohmann_transfer'},
    {"name": "orbital_period", "type": "R", "domain": "orbital",
     "desc": "Orbital period: T = 2*pi*sqrt(a^3/mu)",
     "tags": ["orbital", "period", "kepler"],
     "source": 'import numpy as np\nfrom anvil import Q\ndef orbital_period(mu, a):\n    T = 2*np.pi*(a**3/mu)**0.5\n    return {"T_orbital": Q(T, "s")}\nexport = orbital_period'},

    # ==================== AERODYNAMICS: ATMOSPHERE ====================
    {"name": "isa_atmosphere", "type": "R", "domain": "aero.atmosphere",
     "desc": "International Standard Atmosphere (ISA) up to 86 km",
     "tags": ["atmosphere", "ISA", "altitude", "aerodynamics"],
     "source": (
         'import numpy as np\nfrom anvil import Q\n'
         'def isa_atmosphere(h):\n'
         '    """ISA atmosphere. h in meters. Troposphere 0-11km, Stratosphere 11-20km."""\n'
         '    T0, P0, rho0 = 288.15, 101325.0, 1.225\n'
         '    g0, R_air = 9.80665, 287.058\n'
         '    if h <= 11000:\n'
         '        T = T0 - 0.0065 * h\n'
         '        P = P0 * (T / T0) ** (g0 / (0.0065 * R_air))\n'
         '    elif h <= 20000:\n'
         '        T11 = 216.65\n'
         '        P11 = 101325.0 * (216.65 / 288.15) ** (g0 / (0.0065 * R_air))\n'
         '        T = T11\n'
         '        P = P11 * np.exp(-g0 * (h - 11000) / (R_air * T11))\n'
         '    elif h <= 32000:\n'
         '        T20 = 216.65\n'
         '        P20 = 5474.89\n'
         '        T = T20 + 0.001 * (h - 20000)\n'
         '        P = P20 * (T / T20) ** (-g0 / (0.001 * R_air))\n'
         '    else:\n'
         '        T = 228.65 + 0.0028 * (h - 32000) if h <= 47000 else 270.65\n'
         '        P = 868.019 * np.exp(-g0 * (h - 32000) / (R_air * 228.65)) if h <= 47000 else 110.906\n'
         '    rho = P / (R_air * T)\n'
         '    a = (1.4 * R_air * T) ** 0.5\n'
         '    mu = 1.458e-6 * T**1.5 / (T + 110.4)\n'
         '    return {"T_atm": Q(T, "K"), "P_atm": Q(P, "Pa"), "rho_atm": Q(rho, "kg/m^3"),\n'
         '            "a_atm": Q(a, "m/s"), "mu_atm": Q(mu, "Pa*s"),\n'
         '            "sigma": rho / 1.225}\n'
         'export = isa_atmosphere'
     )},

    # ==================== AERODYNAMICS: LIFT & DRAG ====================
    {"name": "thin_airfoil_cl", "type": "R", "domain": "aero",
     "desc": "Thin airfoil theory: CL = 2*pi*(alpha + alpha_L0); M correction via Prandtl-Glauert",
     "tags": ["aerodynamics", "lift", "thin_airfoil", "subsonic"],
     "source": (
         'import numpy as np\n'
         'def thin_airfoil_cl(alpha_deg, alpha_L0_deg=0.0, M=0.0):\n'
         '    """Thin airfoil CL with optional Prandtl-Glauert compressibility correction."""\n'
         '    alpha = np.radians(alpha_deg)\n'
         '    alpha_L0 = np.radians(alpha_L0_deg)\n'
         '    CL_inc = 2 * np.pi * (alpha - alpha_L0)\n'
         '    beta = max((1 - min(M, 0.7)**2)**0.5, 0.1)\n'
         '    CL = CL_inc / beta\n'
         '    return {"CL": CL, "CL_alpha": 2 * np.pi / beta}\n'
         'export = thin_airfoil_cl'
     )},
    {"name": "induced_drag", "type": "R", "domain": "aero",
     "desc": "Induced drag: CDi = CL^2 / (pi * e * AR)",
     "tags": ["aerodynamics", "drag", "induced", "lifting_line"],
     "source": (
         'import numpy as np\n'
         'def induced_drag(CL, AR, e=0.85):\n'
         '    """Lifting-line induced drag. e = Oswald efficiency (0.7-0.9 typical)."""\n'
         '    CDi = CL**2 / (np.pi * e * AR)\n'
         '    return {"CDi": CDi}\n'
         'export = induced_drag'
     )},
    {"name": "drag_polar", "type": "R", "domain": "aero",
     "desc": "Parabolic drag polar: CD = CD0 + CL^2/(pi*e*AR)",
     "tags": ["aerodynamics", "drag", "polar"],
     "source": (
         'import numpy as np\n'
         'def drag_polar(CL, CD0, AR, e=0.85):\n'
         '    CDi = CL**2 / (np.pi * e * AR)\n'
         '    CD = CD0 + CDi\n'
         '    LoD = CL / CD if CD > 0 else 0\n'
         '    return {"CD": CD, "CDi": CDi, "LoD": LoD}\n'
         'export = drag_polar'
     )},
    {"name": "oswald_efficiency", "type": "R", "domain": "aero",
     "desc": "Oswald span efficiency estimate from aspect ratio (empirical)",
     "tags": ["aerodynamics", "oswald", "efficiency", "wing"],
     "source": (
         'import numpy as np\n'
         'def oswald_efficiency(AR, sweep_deg=0.0, taper=1.0):\n'
         '    """Raymer/Hoak empirical fit for Oswald efficiency factor."""\n'
         '    sweep_rad = np.radians(sweep_deg)\n'
         '    e = 1.78 * (1 - 0.045 * AR**0.68) - 0.64\n'
         '    e = max(0.5, min(e, 1.0))\n'
         '    return {"e_oswald": e}\n'
         'export = oswald_efficiency'
     )},
    {"name": "stall_speed", "type": "R", "domain": "aero",
     "desc": "Aircraft stall speed: Vs = sqrt(2*W/(rho*S*CLmax))",
     "tags": ["aerodynamics", "stall", "speed", "performance"],
     "source": (
         'from anvil import Q\n'
         'def stall_speed(W, rho, S_ref, CLmax):\n'
         '    """W: weight [N], rho: air density [kg/m^3], S_ref: wing area [m^2]."""\n'
         '    Vs = (2 * W / (rho * S_ref * CLmax)) ** 0.5\n'
         '    return {"V_stall": Q(Vs, "m/s")}\n'
         'export = stall_speed'
     )},
    {"name": "range_breguet", "type": "R", "domain": "aero.performance",
     "desc": "Breguet range equation for jet aircraft",
     "tags": ["aerodynamics", "range", "breguet", "performance"],
     "source": (
         'import numpy as np\nfrom anvil import Q\n'
         'def range_breguet(V, TSFC, LoD, W_initial, W_final):\n'
         '    """V [m/s], TSFC [1/s = kg/N/s], LoD = L/D, weights in N."""\n'
         '    R = (V / TSFC) * LoD * np.log(W_initial / W_final)\n'
         '    return {"range": Q(R, "m"), "range_km": Q(R / 1000, "km")}\n'
         'export = range_breguet'
     )},

    # ==================== CONTROLS ====================
    {"name": "pid_output", "type": "R", "domain": "controls",
     "desc": "PID controller output: u = Kp*e + Ki*integral(e) + Kd*de/dt",
     "tags": ["controls", "PID", "controller"],
     "source": (
         'def pid_output(error, integral_error, derivative_error, Kp, Ki, Kd):\n'
         '    """PID control law. Provide pre-computed integral and derivative of error."""\n'
         '    u = Kp * error + Ki * integral_error + Kd * derivative_error\n'
         '    return {"u_pid": u}\n'
         'export = pid_output'
     )},
    {"name": "ziegler_nichols_pid", "type": "R", "domain": "controls",
     "desc": "Ziegler-Nichols PID tuning from ultimate gain and period",
     "tags": ["controls", "PID", "tuning", "ziegler_nichols"],
     "source": (
         'def ziegler_nichols_pid(Ku, Tu, method="classic"):\n'
         '    """Compute Kp, Ki, Kd from ultimate gain Ku and period Tu."""\n'
         '    if method == "classic":\n'
         '        Kp = 0.6 * Ku\n'
         '        Ti = 0.5 * Tu\n'
         '        Td = 0.125 * Tu\n'
         '    elif method == "PI":\n'
         '        Kp = 0.45 * Ku; Ti = 0.833 * Tu; Td = 0.0\n'
         '    elif method == "PD":\n'
         '        Kp = 0.8 * Ku; Ti = 1e12; Td = 0.1 * Tu\n'
         '    else:\n'
         '        Kp = 0.6 * Ku; Ti = 0.5 * Tu; Td = 0.125 * Tu\n'
         '    Ki = Kp / Ti if Ti > 0 else 0\n'
         '    Kd = Kp * Td\n'
         '    return {"Kp": Kp, "Ki": Ki, "Kd": Kd, "Ti": Ti, "Td": Td}\n'
         'export = ziegler_nichols_pid'
     )},
    {"name": "first_order_step", "type": "R", "domain": "controls",
     "desc": "First-order system step response: y(t) = K*(1-exp(-t/tau))",
     "tags": ["controls", "first_order", "step_response", "dynamics"],
     "source": (
         'import numpy as np\n'
         'def first_order_step(K, tau, t_settle_criterion=0.02):\n'
         '    """K: DC gain, tau: time constant. Returns settling time for 2% criterion."""\n'
         '    t_settle = -tau * np.log(t_settle_criterion)\n'
         '    rise_time = 2.2 * tau\n'
         '    return {"t_settle": t_settle, "t_rise": rise_time,\n'
         '            "bandwidth_Hz": 1 / (2 * np.pi * tau)}\n'
         'export = first_order_step'
     )},
    {"name": "second_order_metrics", "type": "R", "domain": "controls",
     "desc": "Second-order system metrics from natural frequency and damping ratio",
     "tags": ["controls", "second_order", "damping", "natural_frequency"],
     "source": (
         'import numpy as np\n'
         'def second_order_metrics(omega_n, zeta):\n'
         '    """omega_n [rad/s], zeta = damping ratio. Returns step response metrics."""\n'
         '    if zeta >= 1.0:\n'
         '        t_settle = 4.0 / (zeta * omega_n)\n'
         '        overshoot = 0.0\n'
         '        t_peak = float("inf")\n'
         '    else:\n'
         '        omega_d = omega_n * (1 - zeta**2)**0.5\n'
         '        overshoot = np.exp(-np.pi * zeta / (1 - zeta**2)**0.5) * 100\n'
         '        t_peak = np.pi / omega_d\n'
         '        t_settle = 4.0 / (zeta * omega_n)\n'
         '    t_rise = (1 - 0.4167 * zeta + 2.917 * zeta**2) / omega_n\n'
         '    return {"overshoot_pct": overshoot, "t_peak": t_peak,\n'
         '            "t_settle": t_settle, "t_rise": t_rise,\n'
         '            "omega_d": omega_n * max((1 - zeta**2)**0.5, 0)}\n'
         'export = second_order_metrics'
     )},
    {"name": "routh_hurwitz_2nd", "type": "R", "domain": "controls",
     "desc": "Stability check for 2nd-order characteristic polynomial: s^2 + a1*s + a0",
     "tags": ["controls", "stability", "routh_hurwitz"],
     "source": (
         'def routh_hurwitz_2nd(a1, a0):\n'
         '    """All coefficients must be positive for stability."""\n'
         '    stable = (a1 > 0) and (a0 > 0)\n'
         '    return {"stable": stable, "a1": a1, "a0": a0}\n'
         'export = routh_hurwitz_2nd'
     )},

    # ==================== MATERIALS ====================
    {"name": "safety_factor", "type": "R", "domain": "materials",
     "desc": "Safety factor and margin of safety",
     "tags": ["materials", "safety", "stress", "design"],
     "source": (
         'def safety_factor(allowable_stress, applied_stress):\n'
         '    SF = allowable_stress / applied_stress if applied_stress != 0 else float("inf")\n'
         '    MS = SF - 1\n'
         '    return {"safety_factor": SF, "margin_of_safety": MS, "pass": SF >= 1.0}\n'
         'export = safety_factor'
     )},
    {"name": "thermal_expansion_stress", "type": "R", "domain": "materials",
     "desc": "Thermal stress in fully constrained member: sigma = E * alpha * dT",
     "tags": ["materials", "thermal", "stress", "expansion"],
     "source": (
         'from anvil import Q\n'
         'def thermal_expansion_stress(E, alpha_thermal, dT):\n'
         '    """E [Pa], alpha_thermal [1/K], dT [K]. Fully constrained."""\n'
         '    sigma = E * alpha_thermal * dT\n'
         '    return {"sigma_thermal": Q(sigma, "Pa")}\n'
         'export = thermal_expansion_stress'
     )},
    {"name": "fatigue_life_basquin", "type": "R", "domain": "materials",
     "desc": "Basquin S-N fatigue life: N = (sigma_f / sigma_a)^(1/b)",
     "tags": ["materials", "fatigue", "SN_curve", "basquin"],
     "source": (
         'def fatigue_life_basquin(sigma_a, sigma_f_prime, b_exponent):\n'
         '    """sigma_a: stress amplitude, sigma_f\': fatigue strength coefficient,\n'
         '    b: fatigue strength exponent (typically -0.05 to -0.12).\n'
         '    Returns number of cycles to failure."""\n'
         '    N = 0.5 * (sigma_a / sigma_f_prime) ** (1 / b_exponent)\n'
         '    return {"N_cycles": N}\n'
         'export = fatigue_life_basquin'
     )},
    {"name": "miners_rule", "type": "R", "domain": "materials",
     "desc": "Miner's rule cumulative damage: D = sum(ni/Ni). Failure when D >= 1.",
     "tags": ["materials", "fatigue", "damage", "miners_rule"],
     "source": (
         'def miners_rule(cycle_counts, cycle_limits):\n'
         '    """cycle_counts: list of ni, cycle_limits: list of Ni."""\n'
         '    D = sum(n / N for n, N in zip(cycle_counts, cycle_limits) if N > 0)\n'
         '    return {"damage_index": D, "failed": D >= 1.0,\n'
         '            "remaining_life_fraction": max(0, 1 - D)}\n'
         'export = miners_rule'
     )},
    {"name": "fracture_toughness_check", "type": "R", "domain": "materials",
     "desc": "Linear elastic fracture mechanics: K = sigma * sqrt(pi * a) * F",
     "tags": ["materials", "fracture", "LEFM", "toughness"],
     "source": (
         'import numpy as np\n'
         'def fracture_toughness_check(sigma, a_crack, KIc, F_geometry=1.12):\n'
         '    """sigma: stress [Pa], a_crack: crack half-length [m],\n'
         '    KIc: plane strain fracture toughness [Pa*sqrt(m)], F: geometry factor."""\n'
         '    KI = sigma * np.sqrt(np.pi * a_crack) * F_geometry\n'
         '    SF = KIc / KI if KI > 0 else float("inf")\n'
         '    return {"KI": KI, "KIc": KIc, "safety_factor": SF, "failed": KI >= KIc}\n'
         'export = fracture_toughness_check'
     )},
    {"name": "composite_laminate_stiffness", "type": "R", "domain": "materials",
     "desc": "Rule-of-mixtures for unidirectional composite: E1, E2, G12, nu12",
     "tags": ["materials", "composite", "laminate", "rule_of_mixtures"],
     "source": (
         'def composite_laminate_stiffness(Ef, Em, Gf, Gm, nu_f, nu_m, Vf):\n'
         '    """Vf: fiber volume fraction (0-1). Returns UD ply properties."""\n'
         '    Vm = 1 - Vf\n'
         '    E1 = Ef * Vf + Em * Vm\n'
         '    E2 = Ef * Em / (Ef * Vm + Em * Vf)\n'
         '    G12 = Gf * Gm / (Gf * Vm + Gm * Vf)\n'
         '    nu12 = nu_f * Vf + nu_m * Vm\n'
         '    return {"E1": E1, "E2": E2, "G12": G12, "nu12": nu12}\n'
         'export = composite_laminate_stiffness'
     )},

    # ==================== ORBITAL MECHANICS (EXTENDED) ====================
    {"name": "keplerian_to_cartesian", "type": "R", "domain": "orbital",
     "desc": "Convert Keplerian elements to ECI Cartesian state (r, v vectors)",
     "tags": ["orbital", "keplerian", "cartesian", "state_vector"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def keplerian_to_cartesian(a, e, i_deg, RAAN_deg, omega_deg, nu_deg, mu):\n'
         '    """Convert classical orbital elements to ECI position and velocity.\n'
         '    a: semi-major axis [m], e: eccentricity, angles in degrees, mu [m³/s²].\n'
         '    Returns r_eci [m] and v_eci [m/s] as 3-element lists.\n'
         '    """\n'
         '    a=float(a); e=float(e); mu=float(mu)\n'
         '    i=np.radians(float(i_deg)); W=np.radians(float(RAAN_deg))\n'
         '    w=np.radians(float(omega_deg)); nu=np.radians(float(nu_deg))\n'
         '    p = a*(1-e**2)\n'
         '    r = p/(1+e*np.cos(nu))\n'
         '    r_pf = r*np.array([np.cos(nu), np.sin(nu), 0.0])\n'
         '    v_pf = np.sqrt(mu/p)*np.array([-np.sin(nu), e+np.cos(nu), 0.0])\n'
         '    cW,sW=np.cos(W),np.sin(W); ci,si=np.cos(i),np.sin(i)\n'
         '    cw,sw=np.cos(w),np.sin(w)\n'
         '    Q_mat = np.array([\n'
         '        [cW*cw-sW*sw*ci, -cW*sw-sW*cw*ci,  sW*si],\n'
         '        [sW*cw+cW*sw*ci, -sW*sw+cW*cw*ci, -cW*si],\n'
         '        [sw*si,           cw*si,             ci  ]])\n'
         '    r_eci = Q_mat @ r_pf\n'
         '    v_eci = Q_mat @ v_pf\n'
         '    return {"r_eci": r_eci.tolist(), "v_eci": v_eci.tolist(),\n'
         '            "r_mag": Q(float(r), "m"), "v_mag": Q(float(np.linalg.norm(v_eci)), "m/s")}\n'
         'export = keplerian_to_cartesian'
     )},
    {"name": "cartesian_to_keplerian", "type": "R", "domain": "orbital",
     "desc": "Convert ECI Cartesian state vector to Keplerian orbital elements",
     "tags": ["orbital", "keplerian", "cartesian", "orbit_determination"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def cartesian_to_keplerian(r_vec, v_vec, mu):\n'
         '    """Convert ECI position+velocity to classical orbital elements.\n'
         '    r_vec, v_vec: 3-element lists [m] and [m/s]. mu in m³/s².\n'
         '    """\n'
         '    r=np.array(r_vec,dtype=float); v=np.array(v_vec,dtype=float)\n'
         '    mu=float(mu)\n'
         '    r_m=np.linalg.norm(r); v_m=np.linalg.norm(v)\n'
         '    eps = v_m**2/2 - mu/r_m\n'
         '    a = -mu/(2*eps)\n'
         '    h = np.cross(r,v); h_m=np.linalg.norm(h)\n'
         '    e_vec = np.cross(v,h)/mu - r/r_m\n'
         '    e = np.linalg.norm(e_vec)\n'
         '    i_deg = float(np.degrees(np.arccos(np.clip(h[2]/h_m,-1,1))))\n'
         '    N = np.cross(np.array([0,0,1.0]),h); N_m=np.linalg.norm(N)\n'
         '    RAAN_deg = 0.0\n'
         '    if N_m > 1e-10:\n'
         '        RAAN_deg = float(np.degrees(np.arccos(np.clip(N[0]/N_m,-1,1))))\n'
         '        if N[1] < 0: RAAN_deg = 360-RAAN_deg\n'
         '    omega_deg = 0.0\n'
         '    if N_m > 1e-10 and e > 1e-10:\n'
         '        omega_deg = float(np.degrees(np.arccos(np.clip(np.dot(N,e_vec)/(N_m*e),-1,1))))\n'
         '        if e_vec[2] < 0: omega_deg = 360-omega_deg\n'
         '    nu_deg = 0.0\n'
         '    if e > 1e-10:\n'
         '        nu_deg = float(np.degrees(np.arccos(np.clip(np.dot(e_vec,r)/(e*r_m),-1,1))))\n'
         '        if np.dot(r,v) < 0: nu_deg = 360-nu_deg\n'
         '    return {"a": Q(float(a),"m"), "e": float(e), "i_deg": i_deg,\n'
         '            "RAAN_deg": RAAN_deg, "omega_deg": omega_deg, "nu_deg": nu_deg,\n'
         '            "h_mag": Q(float(h_m),"m^2/s")}\n'
         'export = cartesian_to_keplerian'
     )},
    {"name": "plane_change_dv", "type": "R", "domain": "orbital",
     "desc": "Delta-V for a pure orbital plane change (inclination change)",
     "tags": ["orbital", "plane_change", "inclination", "delta_v"],
     "source": (
         'import math\n'
         'from anvil import Q\n'
         'def plane_change_dv(v, delta_i_deg):\n'
         '    """Delta-V for a pure inclination change.\n'
         '    v: orbital speed [m/s], delta_i_deg: inclination change [deg].\n'
         '    Most efficient at apoapsis (lowest v).\n'
         '    """\n'
         '    dv = 2*float(v)*math.sin(math.radians(float(delta_i_deg))/2)\n'
         '    return {"dv_plane_change": Q(dv,"m/s")}\n'
         'export = plane_change_dv'
     )},
    {"name": "bielliptic_transfer", "type": "R", "domain": "orbital",
     "desc": "Bi-elliptic transfer delta-V between two circular orbits via intermediate radius",
     "tags": ["orbital", "bielliptic", "transfer", "delta_v"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def bielliptic_transfer(mu, r1, r2, rb):\n'
         '    """Bi-elliptic transfer r1 -> rb -> r2. More efficient than Hohmann when r2/r1 > 11.94.\n'
         '    rb: intermediate apoapsis radius [m]. Must be >= max(r1,r2).\n'
         '    """\n'
         '    mu=float(mu); r1=float(r1); r2=float(r2); rb=float(rb)\n'
         '    a1=(r1+rb)/2; a2=(rb+r2)/2\n'
         '    v1=np.sqrt(mu/r1)\n'
         '    vt1a=np.sqrt(mu*(2/r1-1/a1)); dv1=abs(vt1a-v1)\n'
         '    vt1b=np.sqrt(mu*(2/rb-1/a1)); vt2b=np.sqrt(mu*(2/rb-1/a2)); dv2=abs(vt2b-vt1b)\n'
         '    vt2a=np.sqrt(mu*(2/r2-1/a2)); v2=np.sqrt(mu/r2); dv3=abs(v2-vt2a)\n'
         '    tof=np.pi*((a1**3/mu)**0.5+(a2**3/mu)**0.5)\n'
         '    return {"dv1":Q(dv1,"m/s"),"dv2":Q(dv2,"m/s"),"dv3":Q(dv3,"m/s"),\n'
         '            "dv_total":Q(dv1+dv2+dv3,"m/s"),"tof":Q(tof,"s")}\n'
         'export = bielliptic_transfer'
     )},
    {"name": "j2_precession", "type": "R", "domain": "orbital",
     "desc": "J2 oblateness nodal (RAAN) and apsidal (perigee) precession rates",
     "tags": ["orbital", "J2", "precession", "perturbation"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def j2_precession(a, e, i_deg, mu=3.986004418e14, R_body=6.371e6, J2=1.08263e-3):\n'
         '    """J2 secular precession rates for Earth orbit.\n'
         '    Returns RAAN and argument-of-perigee drift in rad/s and deg/day.\n'
         '    """\n'
         '    a=float(a); e=float(e); i=np.radians(float(i_deg))\n'
         '    n=np.sqrt(float(mu)/a**3); p=a*(1-e**2)\n'
         '    fac=-1.5*n*float(J2)*(float(R_body)/p)**2\n'
         '    d_RAAN = fac*np.cos(i)\n'
         '    d_omega = -0.5*fac*(5*np.cos(i)**2-1)\n'
         '    return {"d_RAAN_dt":Q(float(d_RAAN),"rad/s"),\n'
         '            "d_omega_dt":Q(float(d_omega),"rad/s"),\n'
         '            "d_RAAN_deg_per_day":float(np.degrees(d_RAAN)*86400),\n'
         '            "d_omega_deg_per_day":float(np.degrees(d_omega)*86400)}\n'
         'export = j2_precession'
     )},
    {"name": "eclipse_fraction", "type": "R", "domain": "orbital",
     "desc": "Fraction of circular orbit spent in planet shadow (cylindrical model)",
     "tags": ["orbital", "eclipse", "shadow", "power"],
     "source": (
         'import numpy as np\n'
         'def eclipse_fraction(a, R_body=6.371e6, beta_deg=0.0):\n'
         '    """Cylindrical shadow model. beta_deg: sun-orbit plane angle.\n'
         '    Returns eclipse_frac=0 when |beta|>beta_max (no eclipse season).\n'
         '    """\n'
         '    a=float(a); R_body=float(R_body); beta=np.radians(float(beta_deg))\n'
         '    rho=np.arcsin(min(R_body/a,1.0))\n'
         '    beta_max_deg=float(np.degrees(rho))\n'
         '    if abs(beta)>=rho:\n'
         '        return {"eclipse_frac":0.0,"beta_max_deg":beta_max_deg,"in_eclipse_season":False}\n'
         '    eclipse_frac=float(np.arccos(np.cos(rho)/np.cos(beta))/np.pi)\n'
         '    return {"eclipse_frac":eclipse_frac,"beta_max_deg":beta_max_deg,"in_eclipse_season":True}\n'
         'export = eclipse_fraction'
     )},
    {"name": "sphere_of_influence", "type": "R", "domain": "orbital",
     "desc": "Laplace sphere of influence radius: r_SOI = a*(m_body/m_parent)^(2/5)",
     "tags": ["orbital", "SOI", "patched_conic", "gravity_assist"],
     "source": (
         'from anvil import Q\n'
         'def sphere_of_influence(a_body, m_body, m_parent):\n'
         '    """Sphere of influence for patched-conic trajectory design.\n'
         '    a_body: semi-major axis of body around parent [m],\n'
         '    m_body, m_parent: masses [kg].\n'
         '    """\n'
         '    r_SOI=float(a_body)*(float(m_body)/float(m_parent))**0.4\n'
         '    return {"r_SOI":Q(r_SOI,"m")}\n'
         'export = sphere_of_influence'
     )},
    {"name": "propellant_mass", "type": "R", "domain": "orbital",
     "desc": "Propellant mass from delta-V requirement via Tsiolkovsky equation (inverse)",
     "tags": ["orbital", "propulsion", "propellant", "tsiolkovsky", "delta_v"],
     "source": (
         'import math\n'
         'from anvil import Q\n'
         'def propellant_mass(dv, Isp, m_dry):\n'
         '    """Compute propellant mass from delta-V, Isp, and dry mass.\n'
         '    dv [m/s], Isp [s], m_dry [kg].\n'
         '    """\n'
         '    mass_ratio=math.exp(float(dv)/(float(Isp)*9.80665))\n'
         '    m_wet=float(m_dry)*mass_ratio\n'
         '    return {"m_propellant":Q(m_wet-float(m_dry),"kg"),"m_wet":Q(m_wet,"kg"),"mass_ratio":mass_ratio}\n'
         'export = propellant_mass'
     )},
    {"name": "delta_v_budget", "type": "R", "domain": "orbital",
     "desc": "Aggregate mission delta-V budget across up to 6 phases with margin",
     "tags": ["orbital", "delta_v", "budget", "mission"],
     "source": (
         'from anvil import Q\n'
         'def delta_v_budget(dv1, dv2=0, dv3=0, dv4=0, dv5=0, dv6=0, margin_pct=5.0):\n'
         '    """Sum delta-V phases and apply a percentage margin.\n'
         '    dv1..dv6 [m/s]: mission phase delta-Vs. margin_pct: design margin [%].\n'
         '    """\n'
         '    tot=float(dv1)+float(dv2)+float(dv3)+float(dv4)+float(dv5)+float(dv6)\n'
         '    margin=tot*float(margin_pct)/100\n'
         '    return {"dv_total":Q(tot,"m/s"),"dv_with_margin":Q(tot+margin,"m/s"),\n'
         '            "dv_margin":Q(margin,"m/s")}\n'
         'export = delta_v_budget'
     )},

    # ==================== ATTITUDE & ADCS ====================
    {"name": "euler_equations", "type": "R", "domain": "attitude",
     "desc": "Euler's equations of motion for rigid body rotation in principal axes",
     "tags": ["attitude", "rigid_body", "euler", "rotation", "dynamics"],
     "source": (
         'from anvil import Q\n'
         'def euler_equations(omega_x, omega_y, omega_z, Ix, Iy, Iz,\n'
         '                    tau_x=0.0, tau_y=0.0, tau_z=0.0):\n'
         '    """Instantaneous angular acceleration from Euler equations.\n'
         '    omega_* [rad/s]: body rates. I* [kg*m²]: principal moments.\n'
         '    tau_* [N*m]: external torques.\n'
         '    """\n'
         '    ox,oy,oz=float(omega_x),float(omega_y),float(omega_z)\n'
         '    Ix,Iy,Iz=float(Ix),float(Iy),float(Iz)\n'
         '    ax=(float(tau_x)-(Iz-Iy)*oy*oz)/Ix\n'
         '    ay=(float(tau_y)-(Ix-Iz)*oz*ox)/Iy\n'
         '    az=(float(tau_z)-(Iy-Ix)*ox*oy)/Iz\n'
         '    return {"alpha_x":Q(ax,"rad/s^2"),"alpha_y":Q(ay,"rad/s^2"),"alpha_z":Q(az,"rad/s^2")}\n'
         'export = euler_equations'
     )},
    {"name": "quaternion_kinematics", "type": "R", "domain": "attitude",
     "desc": "Quaternion kinematic equation: q_dot = 0.5 * Ξ(q) * omega",
     "tags": ["attitude", "quaternion", "kinematics", "ADCS"],
     "source": (
         'import math\n'
         'def quaternion_kinematics(q_w, q_x, q_y, q_z, omega_x, omega_y, omega_z):\n'
         '    """Quaternion time derivative given attitude q=[w,x,y,z] and body rate omega.\n'
         '    Hamilton convention. omega [rad/s] in body frame.\n'
         '    """\n'
         '    qw,qx,qy,qz=float(q_w),float(q_x),float(q_y),float(q_z)\n'
         '    ox,oy,oz=float(omega_x),float(omega_y),float(omega_z)\n'
         '    qw_dot=0.5*(-qx*ox-qy*oy-qz*oz)\n'
         '    qx_dot=0.5*( qw*ox-qz*oy+qy*oz)\n'
         '    qy_dot=0.5*( qz*ox+qw*oy-qx*oz)\n'
         '    qz_dot=0.5*(-qy*ox+qx*oy+qw*oz)\n'
         '    q_norm=math.sqrt(qw**2+qx**2+qy**2+qz**2)\n'
         '    return {"qw_dot":qw_dot,"qx_dot":qx_dot,"qy_dot":qy_dot,"qz_dot":qz_dot,\n'
         '            "q_norm":q_norm}\n'
         'export = quaternion_kinematics'
     )},
    {"name": "triad_attitude", "type": "R", "domain": "attitude",
     "desc": "TRIAD two-vector attitude determination: body-to-reference DCM and quaternion",
     "tags": ["attitude", "TRIAD", "attitude_determination", "ADCS"],
     "source": (
         'import numpy as np\n'
         'def triad_attitude(b1_x,b1_y,b1_z, b2_x,b2_y,b2_z,\n'
         '                   r1_x,r1_y,r1_z, r2_x,r2_y,r2_z):\n'
         '    """TRIAD attitude determination.\n'
         '    b1,b2: reference vectors measured in body frame.\n'
         '    r1,r2: same vectors in reference (inertial) frame.\n'
         '    Returns body-to-reference DCM C (3x3) and quaternion [w,x,y,z].\n'
         '    """\n'
         '    def u(v): return v/np.linalg.norm(v)\n'
         '    b1=u(np.array([float(b1_x),float(b1_y),float(b1_z)]))\n'
         '    b2=u(np.array([float(b2_x),float(b2_y),float(b2_z)]))\n'
         '    r1=u(np.array([float(r1_x),float(r1_y),float(r1_z)]))\n'
         '    r2=u(np.array([float(r2_x),float(r2_y),float(r2_z)]))\n'
         '    t1b=b1; t2b=u(np.cross(b1,b2)); t3b=np.cross(t1b,t2b)\n'
         '    t1r=r1; t2r=u(np.cross(r1,r2)); t3r=np.cross(t1r,t2r)\n'
         '    C=(np.column_stack([t1b,t2b,t3b])@np.column_stack([t1r,t2r,t3r]).T)\n'
         '    tr=np.trace(C)\n'
         '    qw=0.5*np.sqrt(max(0,1+tr))\n'
         '    if qw>1e-10:\n'
         '        qx=(C[2,1]-C[1,2])/(4*qw); qy=(C[0,2]-C[2,0])/(4*qw); qz=(C[1,0]-C[0,1])/(4*qw)\n'
         '    else:\n'
         '        qx=np.sqrt(max(0,(1+C[0,0]-C[1,1]-C[2,2])/4))\n'
         '        qy=np.sqrt(max(0,(1-C[0,0]+C[1,1]-C[2,2])/4))\n'
         '        qz=np.sqrt(max(0,(1-C[0,0]-C[1,1]+C[2,2])/4))\n'
         '    return {"C":C.tolist(),"q_w":float(qw),"q_x":float(qx),"q_y":float(qy),"q_z":float(qz)}\n'
         'export = triad_attitude'
     )},
    {"name": "gravity_gradient_torque", "type": "R", "domain": "attitude",
     "desc": "Gravity gradient torque on a nadir-pointing satellite",
     "tags": ["attitude", "gravity_gradient", "torque", "disturbance"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def gravity_gradient_torque(mu, r, Ix, Iy, Iz,\n'
         '                            theta_pitch_deg=0.0, phi_roll_deg=0.0):\n'
         '    """Gravity gradient torque in orbital (roll-pitch-yaw) frame.\n'
         '    mu [m³/s²], r [m]: orbit radius, I* [kg*m²]: principal moments.\n'
         '    Small-angle linearisation. T_gg_max is worst-case (45 deg) peak.\n'
         '    """\n'
         '    omega2=float(mu)/float(r)**3\n'
         '    theta=np.radians(float(theta_pitch_deg)); phi=np.radians(float(phi_roll_deg))\n'
         '    Ix,Iy,Iz=float(Ix),float(Iy),float(Iz)\n'
         '    T_roll =3*omega2*(Iz-Iy)*phi\n'
         '    T_pitch=3*omega2*(Iy-Ix)*theta\n'
         '    T_gg_max=1.5*omega2*max(abs(Ix-Iy),abs(Iy-Iz),abs(Ix-Iz))\n'
         '    return {"T_roll":Q(float(T_roll),"N*m"),"T_pitch":Q(float(T_pitch),"N*m"),\n'
         '            "T_gg_max":Q(float(T_gg_max),"N*m"),\n'
         '            "omega_orbital":Q(float(np.sqrt(omega2)),"rad/s")}\n'
         'export = gravity_gradient_torque'
     )},
    {"name": "reaction_wheel_sizing", "type": "R", "domain": "attitude",
     "desc": "Reaction wheel angular momentum and torque sizing for a slew maneuver",
     "tags": ["attitude", "reaction_wheel", "sizing", "ADCS"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def reaction_wheel_sizing(I_sc, theta_slew_deg, t_slew, margin=1.5):\n'
         '    """Size a reaction wheel for a bang-bang slew maneuver.\n'
         '    I_sc [kg*m²]: spacecraft MOI about slew axis.\n'
         '    theta_slew_deg [deg]: slew angle. t_slew [s]: slew time.\n'
         '    margin: design margin factor (1.5 = 50% margin).\n'
         '    """\n'
         '    theta=np.radians(float(theta_slew_deg))\n'
         '    omega_max=2*theta/float(t_slew)\n'
         '    alpha_max=omega_max/(float(t_slew)/2)\n'
         '    tau_max=float(I_sc)*alpha_max\n'
         '    H=float(I_sc)*omega_max*float(margin)\n'
         '    P_peak=tau_max*omega_max*float(margin)\n'
         '    return {"H_rw":Q(H,"N*m*s"),"tau_rw":Q(tau_max,"N*m"),\n'
         '            "omega_slew_max":Q(omega_max,"rad/s"),"P_peak":Q(P_peak,"W")}\n'
         'export = reaction_wheel_sizing'
     )},

    # ==================== MISSION BUDGETS ====================
    {"name": "link_budget", "type": "R", "domain": "mission",
     "desc": "RF link budget: received power and FSPL via Friis equation",
     "tags": ["mission", "link_budget", "RF", "communications", "FSPL"],
     "source": (
         'import math\n'
         'from anvil import Q\n'
         'def link_budget(P_tx_W, G_tx_dBi, G_rx_dBi, freq_Hz, distance_m, losses_dB=3.0):\n'
         '    """Friis free-space link budget.\n'
         '    P_tx_W: transmit power [W]. G_*_dBi: antenna gains [dBi].\n'
         '    freq_Hz: carrier frequency. distance_m: range. losses_dB: misc losses.\n'
         '    """\n'
         '    c=2.998e8\n'
         '    FSPL_dB=20*math.log10(4*math.pi*float(distance_m)*float(freq_Hz)/c)\n'
         '    P_tx_dBW=10*math.log10(float(P_tx_W))\n'
         '    P_rx_dBW=P_tx_dBW+float(G_tx_dBi)+float(G_rx_dBi)-FSPL_dB-float(losses_dB)\n'
         '    EIRP_dBW=P_tx_dBW+float(G_tx_dBi)\n'
         '    return {"P_rx_W":Q(10**(P_rx_dBW/10),"W"),"P_rx_dBW":P_rx_dBW,\n'
         '            "FSPL_dB":FSPL_dB,"EIRP_dBW":EIRP_dBW}\n'
         'export = link_budget'
     )},
    {"name": "power_budget", "type": "R", "domain": "mission",
     "desc": "Spacecraft solar array area and battery sizing from load and eclipse fraction",
     "tags": ["mission", "power_budget", "solar", "battery", "eclipse"],
     "source": (
         'from anvil import Q\n'
         'def power_budget(P_load_W, T_orbit_min, eclipse_frac,\n'
         '                 eta_solar=0.28, flux_solar=1361.0, DOD=0.8, eta_battery=0.9):\n'
         '    """Solar panel area and battery capacity sizing.\n'
         '    P_load_W: average load. T_orbit_min: orbital period [min].\n'
         '    eclipse_frac: fraction in shadow. eta_solar: panel efficiency.\n'
         '    flux_solar [W/m²]: solar irradiance. DOD: depth of discharge.\n'
         '    """\n'
         '    t_sun=float(T_orbit_min)*60*(1-float(eclipse_frac))\n'
         '    t_ecl=float(T_orbit_min)*60*float(eclipse_frac)\n'
         '    P_load=float(P_load_W)\n'
         '    E_bat_J=P_load*t_ecl\n'
         '    P_charge=E_bat_J/(t_sun*float(eta_battery)) if t_sun>0 else 0\n'
         '    P_from_panel=P_load+P_charge\n'
         '    A_panel=P_from_panel/(float(eta_solar)*float(flux_solar))\n'
         '    E_bat_Wh=P_load*t_ecl/3600/float(DOD)\n'
         '    m_bat=E_bat_Wh/120  # 120 Wh/kg Li-ion\n'
         '    return {"A_panel_m2":Q(A_panel,"m^2"),"E_bat_Wh":E_bat_Wh,\n'
         '            "m_bat_kg":Q(m_bat,"kg"),"P_from_panel_W":Q(P_from_panel,"W")}\n'
         'export = power_budget'
     )},

    # ==================== CONTROLS (EXTENDED) ====================
    {"name": "state_space_poles", "type": "R", "domain": "controls",
     "desc": "Eigenvalues (poles) of a state matrix A; stability check",
     "tags": ["controls", "state_space", "poles", "stability", "eigenvalues"],
     "source": (
         'import numpy as np\n'
         'def state_space_poles(A_flat, n_states):\n'
         '    """Compute poles (eigenvalues) of state matrix A.\n'
         '    A_flat: row-major list of n_states² floats.\n'
         '    n_states: system order.\n'
         '    """\n'
         '    A=np.array([float(x) for x in A_flat],dtype=float).reshape(int(n_states),int(n_states))\n'
         '    poles=np.linalg.eigvals(A)\n'
         '    stable=bool(np.all(poles.real<0))\n'
         '    min_damp=float(min((-p.real/abs(p) if abs(p)>1e-20 else (1.0 if p.real<0 else -1.0))\n'
         '                       for p in poles))\n'
         '    return {"poles_real":poles.real.tolist(),"poles_imag":poles.imag.tolist(),\n'
         '            "stable":stable,"min_damping":min_damp}\n'
         'export = state_space_poles'
     )},
    {"name": "lqr_bryson", "type": "R", "domain": "controls",
     "desc": "Bryson's rule for LQR Q and R weighting matrices from max allowable values",
     "tags": ["controls", "LQR", "bryson", "optimal_control", "tuning"],
     "source": (
         'def lqr_bryson(state_bounds, input_bounds):\n'
         '    """Bryson rule: Q_ii=1/x_max_i², R_jj=1/u_max_j².\n'
         '    state_bounds: list of max allowable state deviations.\n'
         '    input_bounds: list of max allowable control inputs.\n'
         '    Returns diagonal entries of Q and R.\n'
         '    """\n'
         '    Q_diag=[1.0/float(x)**2 for x in state_bounds]\n'
         '    R_diag=[1.0/float(u)**2 for u in input_bounds]\n'
         '    return {"Q_diag":Q_diag,"R_diag":R_diag,"n_states":len(Q_diag),"n_inputs":len(R_diag)}\n'
         'export = lqr_bryson'
     )},
    {"name": "gain_phase_margin", "type": "R", "domain": "controls",
     "desc": "Gain margin and phase margin for an open-loop transfer function",
     "tags": ["controls", "stability", "gain_margin", "phase_margin", "bode"],
     "source": (
         'import numpy as np\n'
         'def gain_phase_margin(num_coeffs, den_coeffs, omega_lo=1e-3, omega_hi=1e4, n=2000):\n'
         '    """Gain and phase margins from frequency sweep of G(s)=num/den.\n'
         '    Polynomial coefficients in descending order [s^n, ..., s^0].\n'
         '    """\n'
         '    omega=np.logspace(np.log10(float(omega_lo)),np.log10(float(omega_hi)),int(n))\n'
         '    num=[float(c) for c in num_coeffs]; den=[float(c) for c in den_coeffs]\n'
         '    def polyval(coeffs,s):\n'
         '        n=len(coeffs)-1; return sum(c*s**(n-k) for k,c in enumerate(coeffs))\n'
         '    G=np.array([polyval(num,1j*w)/polyval(den,1j*w) for w in omega])\n'
         '    mag=np.abs(G); phase_deg=np.angle(G,deg=True)\n'
         '    # Phase crossover (phase = -180 deg)\n'
         '    GM_dB=float("inf")\n'
         '    cross_p=np.where(np.diff(np.sign(phase_deg+180)))[0]\n'
         '    if len(cross_p)>0:\n'
         '        i=int(cross_p[-1])\n'
         '        GM_dB=float(-20*np.log10(mag[i])) if mag[i]>0 else float("inf")\n'
         '    # Gain crossover (mag = 1)\n'
         '    PM_deg=float("inf")\n'
         '    cross_g=np.where(np.diff(np.sign(mag-1)))[0]\n'
         '    if len(cross_g)>0:\n'
         '        i=int(cross_g[-1])\n'
         '        PM_deg=float(phase_deg[i]+180)\n'
         '    return {"GM_dB":GM_dB,"PM_deg":PM_deg,"stable":GM_dB>0 and PM_deg>0}\n'
         'export = gain_phase_margin'
     )},
]
