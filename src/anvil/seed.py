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
]
