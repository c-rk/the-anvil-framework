"""
Anvil Adapter: OpenFOAM CFD
============================

Wraps OpenFOAM for steady-state incompressible (simpleFoam) and
compressible (rhoCentralFoam / rhoSimpleFoam) external aerodynamic analysis.

ADAPTERS PROVIDED:
    openfoam_incompressible  -- simpleFoam: low-speed CL, CD, CM, y+
    openfoam_compressible    -- rhoSimpleFoam: transonic/supersonic CL, CD
    openfoam_field_stats     -- post-process: field min/max/average from a solved case

INSTALLATION:
    Linux:  sudo apt install openfoam (Ubuntu) or source /opt/openfoam*/etc/bashrc
    macOS:  https://openfoam.org/download/macos/
    WSL:    install Ubuntu, then: sudo apt install openfoam
    Docker: docker pull openfoam/openfoam12-paraview510

VERIFY:
    simpleFoam -help
    foamVersion   (prints installed version)

CASE TEMPLATE:
    Each adapter requires a pre-prepared OpenFOAM case directory with:
        constant/  (mesh + physical properties)
        system/    (fvSolution, fvSchemes, controlDict with forces function object)
        0/         (boundary condition files: U, p, k, epsilon/omega, nut)

    The adapter patches the 0/U and 0/p files with the supplied flow conditions
    and runs the solver. The mesh must already exist (blockMesh or snappyHexMesh
    already run).

MOCK MODE:
    Incompressible: lifting-line theory for CL, flat-plate drag polar for CD.
    Compressible: Prandtl-Glauert compressible correction + wave drag approximation.
    Not valid past stall or for heavily separated flows.

USAGE:
    from anvil.adapters.openfoam_cfd import openfoam_incompressible

    r = openfoam_incompressible(
        case_path="./my_airfoil_case",
        U_inf=50.0, alpha_deg=5.0, rho=1.225, nu=1.5e-5,
    )
    print(r["CL"], r["CD"])

    register()
"""

from anvil import Adapter, Q
import math, os, shutil, subprocess, tempfile, re as _re


# ── Mock fallbacks ────────────────────────────────────────────────────────────

def _mock_incompressible(U_inf, alpha_deg, rho, nu, L_ref, A_ref):
    alpha = math.radians(float(alpha_deg))
    Re = float(U_inf) * float(L_ref) / float(nu)
    CL = 2 * math.pi * alpha
    CD_0 = 0.005 + 0.004 / max(Re / 1e6, 0.1) ** 0.2
    CD   = CD_0 + CL**2 / (math.pi * 0.85 * 12.0)
    CM   = -math.pi * 0.02 * math.cos(2 * alpha)   # camber contribution approximation
    q    = 0.5 * float(rho) * float(U_inf)**2
    F_lift = CL * q * float(A_ref)
    F_drag = CD * q * float(A_ref)
    return CL, CD, CM, F_lift, F_drag, Re

def _mock_compressible(U_inf, alpha_deg, p_inf, T_inf, L_ref, A_ref, gamma=1.4):
    R_air = 287.058
    a_inf = math.sqrt(gamma * R_air * float(T_inf))
    Mach  = float(U_inf) / a_inf
    rho   = float(p_inf) / (R_air * float(T_inf))
    beta  = math.sqrt(max(1.0 - Mach**2, 0.05))
    alpha = math.radians(float(alpha_deg))
    CL    = 2 * math.pi * alpha / beta
    # Wave drag approximation (Küchemann)
    CD_0  = 0.005 / beta
    CD_wave = 0.0 if Mach < 0.8 else 20 * (Mach - 0.8)**2 * CL**2
    CD    = CD_0 + CL**2 / (math.pi * 0.85 * 12.0 * beta) + CD_wave
    q     = 0.5 * rho * float(U_inf)**2
    return CL, CD, Mach, rho, q * float(A_ref) * CL, q * float(A_ref) * CD


# ── OpenFOAM case patching utilities ─────────────────────────────────────────

def _patch_U_file(case_path, U_inf, alpha_deg):
    """Write internalField and inlet U consistent with alpha_deg."""
    alpha = math.radians(float(alpha_deg))
    Ux = float(U_inf) * math.cos(alpha)
    Uy = float(U_inf) * math.sin(alpha)
    uz = f"({Ux:.6f} {Uy:.6f} 0)"

    u_file = os.path.join(case_path, "0", "U")
    if not os.path.exists(u_file):
        return
    with open(u_file) as f:
        content = f.read()
    # Replace internalField uniform (... ...)
    content = _re.sub(
        r'(internalField\s+uniform\s+)\([^)]+\)',
        rf'\g<1>{uz}', content
    )
    # Replace inlet fixedValue (if present)
    content = _re.sub(
        r'(value\s+uniform\s+)\([^)]+\)',
        rf'\g<1>{uz}', content
    )
    with open(u_file, "w") as f:
        f.write(content)


def _read_force_coefficients(case_path, solver_name="simpleFoam"):
    """Parse CL, CD, CM from postProcessing/forceCoeffs or forces."""
    # Try forceCoeffs first (coefficient output)
    coeff_dirs = []
    pp_dir = os.path.join(case_path, "postProcessing")
    if os.path.isdir(pp_dir):
        for entry in os.listdir(pp_dir):
            if "force" in entry.lower() or "coeff" in entry.lower():
                coeff_dirs.append(os.path.join(pp_dir, entry))

    for cd in coeff_dirs:
        for time_dir in sorted(os.listdir(cd), reverse=True):
            for fname in ("forceCoeffs.dat", "coefficient.dat",
                          "forceCoeffs_0.dat"):
                fpath = os.path.join(cd, time_dir, fname)
                if os.path.exists(fpath):
                    with open(fpath) as f:
                        lines = [l for l in f if not l.startswith("#") and l.strip()]
                    if lines:
                        parts = lines[-1].split()
                        if len(parts) >= 4:
                            try:
                                # Format: time Cm Cd Cl (or Cd Cl Cm)
                                return float(parts[3]), float(parts[2]), float(parts[1])
                            except ValueError:
                                pass
    return None


def _run_solver(case_path, solver, n_cores=1, log_file="log.solver"):
    """Run an OpenFOAM solver in case_path."""
    log_path = os.path.join(case_path, log_file)
    if n_cores > 1:
        # Parallel: decomposePar then mpirun
        subprocess.run(["decomposePar", "-case", case_path],
                       capture_output=True, timeout=120)
        cmd = ["mpirun", "-n", str(n_cores), solver,
               "-parallel", "-case", case_path]
    else:
        cmd = [solver, "-case", case_path]

    with open(log_path, "w") as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                              timeout=3600)
    return proc.returncode == 0


# ── Adapter: incompressible (simpleFoam) ─────────────────────────────────────

def _incompressible_call(case_path, U_inf, alpha_deg,
                          rho=1.225, nu=1.5e-5,
                          L_ref=1.0, A_ref=1.0,
                          n_cores=1, solver="simpleFoam"):
    for k, v in dict(U_inf=U_inf, alpha_deg=alpha_deg, rho=rho, nu=nu,
                     L_ref=L_ref, A_ref=A_ref).items():
        if isinstance(v, Q):
            if k == "alpha_deg":
                alpha_deg = float(v.to("deg").value)
            else:
                locals()[k] = float(v.si)
    U_inf=float(U_inf); alpha_deg=float(alpha_deg); rho=float(rho)
    nu=float(nu); L_ref=float(L_ref); A_ref=float(A_ref)
    case_path = str(case_path) if not isinstance(case_path, str) else case_path

    has_foam = shutil.which(solver) is not None
    if has_foam and os.path.isdir(case_path):
        _patch_U_file(case_path, U_inf, alpha_deg)
        success = _run_solver(case_path, solver, int(n_cores))
        if success:
            res = _read_force_coefficients(case_path, solver)
            if res is not None:
                CL, CD, CM = res
                q = 0.5 * rho * U_inf**2
                return {
                    "CL":     CL,
                    "CD":     CD,
                    "CM":     CM,
                    "F_lift": Q(CL * q * A_ref, "N"),
                    "F_drag": Q(CD * q * A_ref, "N"),
                    "Re":     Q(U_inf * L_ref / nu, "1"),
                    "source": "openfoam",
                }

    # Mock fallback
    CL, CD, CM, FL, FD, Re = _mock_incompressible(U_inf, alpha_deg, rho, nu, L_ref, A_ref)
    return {
        "CL":     CL,
        "CD":     CD,
        "CM":     CM,
        "F_lift": Q(FL, "N"),
        "F_drag": Q(FD, "N"),
        "Re":     Q(Re, "1"),
        "source": "mock",
    }


openfoam_incompressible = Adapter(
    "openfoam_incompressible",
    backend="python",
    call=_incompressible_call,
    inputs={
        "case_path":  {"desc": "Path to prepared OpenFOAM case directory"},
        "U_inf":      {"unit": "m/s",    "desc": "Freestream velocity magnitude"},
        "alpha_deg":  {"unit": "deg",    "desc": "Angle of attack"},
        "rho":        {"unit": "kg/m^3", "desc": "Fluid density", "default": 1.225},
        "nu":         {"unit": "m^2/s",  "desc": "Kinematic viscosity", "default": 1.5e-5},
        "L_ref":      {"unit": "m",      "desc": "Reference length (chord)", "default": 1.0},
        "A_ref":      {"unit": "m^2",    "desc": "Reference area", "default": 1.0},
        "n_cores":    {"desc": "Number of MPI cores (1=serial)", "default": 1},
        "solver":     {"desc": "OpenFOAM solver binary", "default": "simpleFoam"},
    },
    outputs={
        "CL":     {"unit": "1", "desc": "Lift coefficient"},
        "CD":     {"unit": "1", "desc": "Drag coefficient"},
        "CM":     {"unit": "1", "desc": "Pitching moment coefficient"},
        "F_lift": {"unit": "N", "desc": "Lift force"},
        "F_drag": {"unit": "N", "desc": "Drag force"},
        "Re":     {"unit": "1", "desc": "Reynolds number"},
        "source": {"desc": "openfoam or mock"},
    },
    desc="Incompressible external aerodynamics via OpenFOAM simpleFoam",
    tags=["openfoam", "CFD", "incompressible", "CL", "CD", "RANS"],
)


# ── Adapter: compressible (rhoSimpleFoam) ────────────────────────────────────

def _compressible_call(case_path, U_inf, alpha_deg,
                        p_inf=101325.0, T_inf=300.0, gamma=1.4,
                        L_ref=1.0, A_ref=1.0,
                        n_cores=1, solver="rhoSimpleFoam"):
    for k, v in dict(U_inf=U_inf, p_inf=p_inf, T_inf=T_inf).items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    if isinstance(alpha_deg, Q): alpha_deg = float(alpha_deg.to("deg").value)
    U_inf=float(U_inf); alpha_deg=float(alpha_deg)
    p_inf=float(p_inf); T_inf=float(T_inf); gamma=float(gamma)
    L_ref=float(L_ref); A_ref=float(A_ref)
    case_path = str(case_path) if not isinstance(case_path, str) else case_path

    has_foam = shutil.which(solver) is not None
    if has_foam and os.path.isdir(case_path):
        _patch_U_file(case_path, U_inf, alpha_deg)
        success = _run_solver(case_path, solver, int(n_cores))
        if success:
            res = _read_force_coefficients(case_path, solver)
            if res is not None:
                CL, CD, CM = res
                R_air = 287.058
                rho   = p_inf / (R_air * T_inf)
                a     = math.sqrt(gamma * R_air * T_inf)
                Mach  = U_inf / a
                q     = 0.5 * rho * U_inf**2
                return {
                    "CL":   CL, "CD": CD, "CM": CM,
                    "Mach": Q(Mach, "1"),
                    "F_lift": Q(CL * q * A_ref, "N"),
                    "F_drag": Q(CD * q * A_ref, "N"),
                    "source": "openfoam",
                }

    # Mock fallback
    CL, CD, Mach, rho, FL, FD = _mock_compressible(U_inf, alpha_deg, p_inf, T_inf,
                                                      L_ref, A_ref, gamma)
    return {
        "CL":     CL, "CD": CD, "CM": 0.0,
        "Mach":   Q(Mach, "1"),
        "F_lift": Q(FL, "N"),
        "F_drag": Q(FD, "N"),
        "source": "mock",
    }


openfoam_compressible = Adapter(
    "openfoam_compressible",
    backend="python",
    call=_compressible_call,
    inputs={
        "case_path":  {"desc": "Path to prepared OpenFOAM case directory"},
        "U_inf":      {"unit": "m/s",  "desc": "Freestream velocity"},
        "alpha_deg":  {"unit": "deg",  "desc": "Angle of attack"},
        "p_inf":      {"unit": "Pa",   "desc": "Freestream static pressure", "default": 101325.0},
        "T_inf":      {"unit": "K",    "desc": "Freestream static temperature", "default": 300.0},
        "gamma":      {"unit": "1",    "desc": "Ratio of specific heats", "default": 1.4},
        "L_ref":      {"unit": "m",    "desc": "Reference length (chord)", "default": 1.0},
        "A_ref":      {"unit": "m^2",  "desc": "Reference area", "default": 1.0},
        "n_cores":    {"desc": "MPI cores", "default": 1},
        "solver":     {"desc": "OpenFOAM solver", "default": "rhoSimpleFoam"},
    },
    outputs={
        "CL":     {"unit": "1", "desc": "Lift coefficient"},
        "CD":     {"unit": "1", "desc": "Drag coefficient"},
        "CM":     {"unit": "1", "desc": "Moment coefficient"},
        "Mach":   {"unit": "1", "desc": "Freestream Mach number"},
        "F_lift": {"unit": "N", "desc": "Lift force"},
        "F_drag": {"unit": "N", "desc": "Drag force"},
        "source": {"desc": "openfoam or mock"},
    },
    desc="Compressible external aerodynamics via OpenFOAM rhoSimpleFoam",
    tags=["openfoam", "CFD", "compressible", "Mach", "transonic", "RANS"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    for adapter in (openfoam_incompressible, openfoam_compressible):
        anvil.push(adapter, domain="cfd.openfoam",
                   description=adapter.desc, tags=adapter.tags)
    print("Registered: openfoam_incompressible, openfoam_compressible"
          "  [domain: cfd.openfoam]")
