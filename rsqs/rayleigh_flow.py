"""
Rayleigh flow RSQs — 1D flow with heat addition in a constant-area duct.

Two relations:
    rayleigh_ratios  — flow property ratios at a given M referenced to sonic (★)
    rayleigh_heat    — exit conditions given inlet state + heat addition q [J/kg]

Usage — push to a project registry:

    import sys; sys.path.insert(0, "src")
    import anvil
    from rsqs.rayleigh_flow import rayleigh_ratios, rayleigh_heat

    proj = anvil.project("my_study", path="./work")
    proj.push(rayleigh_ratios, domain="aero.compressible", tags=["rayleigh"])
    proj.push(rayleigh_heat,   domain="aero.compressible", tags=["rayleigh"])

    # Use directly
    r = proj.R.rayleigh_ratios(M=0.5)
    r = proj.R.rayleigh_heat(M1=0.3, T01=300.0, P1=101325.0, q_heat=200e3, cp=1005.0)

    # Or push to global registry when ready
    proj.promote("rayleigh_ratios")
    proj.promote("rayleigh_heat")
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anvil import Q, solvers


def rayleigh_ratios(M, gamma=1.4):
    """
    Rayleigh flow ratios at Mach M referenced to sonic (★) conditions.

    Returns T0/T0*, T/T*, P/P*, P0/P0*, rho/rho*, V/V*.
    Valid for any M > 0 (subsonic and supersonic branches).
    """
    g = float(gamma)
    M = float(M)
    gp1 = g + 1
    denom = 1 + g * M**2

    P_Pstar     = gp1 / denom
    T_Tstar     = (gp1 * M / denom)**2
    rho_rhostar = denom / (gp1 * M**2)
    t0          = 1 + (g - 1) / 2 * M**2
    T0_T0star   = 2 * gp1 * M**2 * t0 / denom**2
    P0_P0star   = P_Pstar * (2 * t0 / gp1) ** (g / (g - 1))

    return {
        "T0_T0star":   T0_T0star,
        "T_Tstar":     T_Tstar,
        "P_Pstar":     P_Pstar,
        "P0_P0star":   P0_P0star,
        "rho_rhostar": rho_rhostar,
        "V_Vstar":     1.0 / rho_rhostar,
    }


export = rayleigh_ratios


def rayleigh_heat(M1, T01, P1, q_heat, cp, gamma=1.4):
    """
    Rayleigh flow with heat addition in a constant-area duct.

    Inputs
    ------
    M1      : inlet Mach number (dimensionless)
    T01     : inlet stagnation temperature [K]
    P1      : inlet static pressure [Pa]
    q_heat  : heat added per unit mass [J/kg]  (positive = heating, negative = cooling)
    cp      : specific heat at constant pressure [J/kg/K]
    gamma   : ratio of specific heats (default 1.4)

    Outputs
    -------
    M2       : exit Mach number
    T02      : exit stagnation temperature [K]
    T2       : exit static temperature [K]
    P2       : exit static pressure [Pa]
    P02      : exit stagnation pressure [Pa]
    P01      : inlet stagnation pressure [Pa]  (for reference)
    P02_P01  : stagnation pressure ratio (loss indicator; < 1 for heating)
    T0_T0star: T02/T0* (how close to choking; = 1.0 at M=1)

    Raises
    ------
    ValueError if q_heat would choke the flow (T02/T0* > 1).
    """
    g   = float(gamma)
    M1  = float(M1)
    T01    = float(getattr(T01,    "si", T01))
    P1     = float(getattr(P1,     "si", P1))
    q_heat = float(getattr(q_heat, "si", q_heat))
    cp     = float(getattr(cp,     "si", cp))

    gp1 = g + 1

    def _T0r(M):
        d = 1 + g * M**2
        return 2 * gp1 * M**2 * (1 + (g - 1) / 2 * M**2) / d**2

    def _Pr(M):
        return gp1 / (1 + g * M**2)

    def _Tr(M):
        d = 1 + g * M**2
        return (gp1 * M / d)**2

    r1     = _T0r(M1)
    T02    = T01 + q_heat / cp
    T0star = T01 / r1
    r2     = T02 / T0star

    if r2 > 1.0:
        raise ValueError(
            f"Flow chokes: T02/T0* = {r2:.4f} > 1.0. "
            f"Max q_heat = {cp * (T0star - T01):.1f} J/kg"
        )

    bracket = (1.0001, 50.0) if M1 >= 1.0 else (0.001, 0.9999)
    M2 = solvers.find_root(
        lambda M: _T0r(M) - r2,
        bracket=bracket, method="brent", tol=1e-12,
    )

    P2  = P1  / _Pr(M1) * _Pr(M2)
    T1  = T01 / (1 + (g - 1) / 2 * M1**2)
    T2  = T1  / _Tr(M1) * _Tr(M2)
    P01 = P1  * (1 + (g - 1) / 2 * M1**2) ** (g / (g - 1))
    P02 = P2  * (1 + (g - 1) / 2 * M2**2) ** (g / (g - 1))

    return {
        "M2":        M2,
        "T02":       Q(T02,        "K"),
        "T2":        Q(T2,         "K"),
        "P2":        Q(P2,         "Pa"),
        "P02":       Q(P02,        "Pa"),
        "P01":       Q(P01,        "Pa"),
        "P02_P01":   P02 / P01,
        "T0_T0star": r2,
    }


export = rayleigh_heat


if __name__ == "__main__":
    print("=== rayleigh_ratios at M=1 (all ratios = 1.0) ===")
    r = rayleigh_ratios(M=1.0)
    for k, v in r.items():
        print(f"  {k}: {v:.6f}")

    print("\n=== rayleigh_ratios at M=0.5 ===")
    r = rayleigh_ratios(M=0.5)
    for k, v in r.items():
        print(f"  {k}: {v:.6f}")

    print("\n=== rayleigh_heat: M1=0.3, T01=300 K, P1=101325 Pa, q=200 kJ/kg ===")
    r = rayleigh_heat(M1=0.3, T01=300.0, P1=101325.0, q_heat=200e3, cp=1005.0)
    for k, v in r.items():
        print(f"  {k}: {v}")

    print("\n=== rayleigh_heat: choke limit check ===")
    import sys as _sys
    try:
        rayleigh_heat(M1=0.3, T01=300.0, P1=101325.0, q_heat=999e3, cp=1005.0)
    except ValueError as e:
        print(f"  Caught: {e}")
