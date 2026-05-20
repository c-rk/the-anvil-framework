"""
Anvil Adapter: SU2 CFD Aerodynamics
=====================================

Wraps SU2 (Stanford University Unstructured) for Euler and RANS aerodynamic
analysis. SU2 is particularly strong for shape optimization and adjoint-based
gradient computation.

ADAPTERS PROVIDED:
    su2_euler    -- Inviscid Euler: CL, CD at given Mach/AoA
    su2_rans     -- Turbulent RANS (SA model): CL, CD, CM
    su2_adjoint  -- Adjoint sensitivities: dCL/dX, dCD/dX surface shape derivatives

INSTALLATION:
    pip install SU2           (Python wrapper)
    or binary: https://su2code.github.io/download.html
    Put SU2_CFD on PATH.

VERIFY:
    SU2_CFD --version

SU2 CONFIG TEMPLATE:
    Each adapter requires a base .cfg file and a mesh file (.su2 format).
    The adapter patches: MACH_NUMBER, AOA, SIDESLIP_ANGLE, REYNOLDS_NUMBER.
    All other settings (numerics, convergence, BCs) come from the template.

MOCK MODE:
    Euler: linearised supersonic theory + Prandtl-Glauert for subsonic.
    RANS:  adds viscous drag approximation (flat-plate boundary layer).

USAGE:
    from anvil.adapters.su2_aero import su2_euler, su2_rans

    r = su2_euler(cfg_template="naca0012.cfg", mesh="naca0012.su2",
                  Mach=0.8, AoA_deg=2.0)
    print(r["CL"], r["CD"])

    register()
"""

from anvil import Adapter, Q
import math, os, shutil, subprocess, tempfile, re as _re


# ── Mock aerodynamics ─────────────────────────────────────────────────────────

def _mock_euler(Mach, AoA_deg, alpha0_deg=0.0):
    alpha = math.radians(float(AoA_deg) - float(alpha0_deg))
    beta  = math.sqrt(max(1.0 - float(Mach)**2, 0.05))
    CL    = 2 * math.pi * alpha / beta
    CD_w  = 0.0 if Mach < 0.8 else 0.01 * (Mach - 0.8)**1.5  # wave drag onset
    CD    = CL**2 / (math.pi * 0.95 * 50.0) + CD_w   # aspect ratio ≈ 50 for 2D
    return CL, CD, -0.05 * CL

def _mock_rans(Mach, AoA_deg, Re, alpha0_deg=0.0):
    CL, CD_inv, CM = _mock_euler(Mach, AoA_deg, alpha0_deg)
    # Flat-plate skin friction
    if Re > 0:
        Cf = 0.455 / math.log10(Re)**2.58  # turbulent Prandtl-Schlichting
    else:
        Cf = 0.003
    CD_visc = 2 * Cf  # wetted area factor ≈ 2× chord for double-sided airfoil
    return CL, CD_inv + CD_visc, CM, Cf


# ── SU2 config patching ───────────────────────────────────────────────────────

def _patch_cfg(src_cfg, dst_cfg, mach, aoa, sideslip=0.0, reynolds=None):
    with open(src_cfg) as f:
        lines = f.readlines()
    out = []
    for line in lines:
        if _re.match(r'\s*MACH_NUMBER\s*=', line):
            out.append(f"MACH_NUMBER= {mach:.6f}\n")
        elif _re.match(r'\s*AOA\s*=', line):
            out.append(f"AOA= {aoa:.6f}\n")
        elif _re.match(r'\s*SIDESLIP_ANGLE\s*=', line):
            out.append(f"SIDESLIP_ANGLE= {sideslip:.6f}\n")
        elif reynolds and _re.match(r'\s*REYNOLDS_NUMBER\s*=', line):
            out.append(f"REYNOLDS_NUMBER= {reynolds:.1f}\n")
        else:
            out.append(line)
    with open(dst_cfg, "w") as f:
        f.writelines(out)


def _parse_su2_history(history_file):
    """Parse SU2 history.csv for last-iteration CL, CD, CM."""
    if not os.path.exists(history_file):
        return None
    with open(history_file) as f:
        lines = f.readlines()
    if len(lines) < 3:
        return None
    # Find header
    header = lines[0].strip().strip('"').split('","')
    header = [h.strip().strip('"') for h in header]
    # Last data line
    data = lines[-1].split(",")
    try:
        idx = {h: i for i, h in enumerate(header)}
        CL = float(data[idx["CL"]])
        CD = float(data[idx["CD"]])
        CM = float(data[idx.get("CMz", idx.get("CMy", idx.get("CM", 0)))])
        return CL, CD, CM
    except (KeyError, ValueError, IndexError):
        return None


def _run_su2(cfg_path, workdir, timeout=3600):
    """Run SU2_CFD. Returns True if succeeded."""
    su2 = shutil.which("SU2_CFD") or shutil.which("SU2_CFD.exe")
    if su2 is None:
        return False
    log = os.path.join(workdir, "su2.log")
    with open(log, "w") as lf:
        proc = subprocess.run(
            [su2, os.path.basename(cfg_path)],
            cwd=workdir, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout,
        )
    return proc.returncode == 0


# ── Adapter: Euler ────────────────────────────────────────────────────────────

def _euler_call(cfg_template, mesh, Mach, AoA_deg,
                sideslip_deg=0.0, alpha0_deg=0.0):
    for k, v in dict(Mach=Mach, AoA_deg=AoA_deg).items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    Mach=float(Mach); AoA=float(AoA_deg); ss=float(sideslip_deg)
    cfg_template=str(cfg_template); mesh=str(mesh)

    has_su2 = shutil.which("SU2_CFD") is not None
    if has_su2 and os.path.exists(cfg_template) and os.path.exists(mesh):
        with tempfile.TemporaryDirectory() as work:
            dst_cfg  = os.path.join(work, "run.cfg")
            dst_mesh = os.path.join(work, os.path.basename(mesh))
            shutil.copy(mesh, dst_mesh)
            _patch_cfg(cfg_template, dst_cfg, Mach, AoA, ss)
            # Also patch mesh filename in cfg
            with open(dst_cfg) as f: content = f.read()
            content = _re.sub(r'MESH_FILENAME\s*=.*',
                               f'MESH_FILENAME= {os.path.basename(mesh)}', content)
            with open(dst_cfg, "w") as f: f.write(content)

            if _run_su2(dst_cfg, work):
                hist = os.path.join(work, "history.csv")
                res = _parse_su2_history(hist)
                if res:
                    CL, CD, CM = res
                    return {"CL": CL, "CD": CD, "CM": CM,
                            "Mach": Q(Mach,"1"), "source": "su2"}

    CL, CD, CM = _mock_euler(Mach, AoA, alpha0_deg)
    return {"CL": CL, "CD": CD, "CM": CM, "Mach": Q(Mach,"1"), "source": "mock"}


su2_euler = Adapter(
    "su2_euler",
    backend="python",
    call=_euler_call,
    inputs={
        "cfg_template": {"desc": "Path to SU2 .cfg template file"},
        "mesh":         {"desc": "Path to SU2 .su2 mesh file"},
        "Mach":         {"unit": "1",   "desc": "Freestream Mach number"},
        "AoA_deg":      {"unit": "deg", "desc": "Angle of attack"},
        "sideslip_deg": {"unit": "deg", "desc": "Sideslip angle", "default": 0.0},
        "alpha0_deg":   {"unit": "deg", "desc": "Zero-lift AoA (mock only)", "default": 0.0},
    },
    outputs={
        "CL":     {"unit": "1",  "desc": "Lift coefficient"},
        "CD":     {"unit": "1",  "desc": "Drag coefficient (wave + induced)"},
        "CM":     {"unit": "1",  "desc": "Pitching moment coefficient"},
        "Mach":   {"unit": "1",  "desc": "Freestream Mach (echo)"},
        "source": {"desc": "su2 or mock"},
    },
    desc="Inviscid Euler aerodynamics via SU2_CFD",
    tags=["su2", "euler", "inviscid", "CL", "CD", "compressible"],
)


# ── Adapter: RANS ─────────────────────────────────────────────────────────────

def _rans_call(cfg_template, mesh, Mach, AoA_deg,
               Reynolds=1e6, sideslip_deg=0.0, alpha0_deg=0.0):
    for k, v in dict(Mach=Mach, AoA_deg=AoA_deg, Reynolds=Reynolds).items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    Mach=float(Mach); AoA=float(AoA_deg); Re=float(Reynolds); ss=float(sideslip_deg)
    cfg_template=str(cfg_template); mesh=str(mesh)

    has_su2 = shutil.which("SU2_CFD") is not None
    if has_su2 and os.path.exists(cfg_template) and os.path.exists(mesh):
        with tempfile.TemporaryDirectory() as work:
            dst_cfg  = os.path.join(work, "run.cfg")
            dst_mesh = os.path.join(work, os.path.basename(mesh))
            shutil.copy(mesh, dst_mesh)
            _patch_cfg(cfg_template, dst_cfg, Mach, AoA, ss, Re)
            with open(dst_cfg) as f: content = f.read()
            content = _re.sub(r'MESH_FILENAME\s*=.*',
                               f'MESH_FILENAME= {os.path.basename(mesh)}', content)
            with open(dst_cfg, "w") as f: f.write(content)
            if _run_su2(dst_cfg, work):
                hist = os.path.join(work, "history.csv")
                res = _parse_su2_history(hist)
                if res:
                    CL, CD, CM = res
                    return {"CL": CL, "CD": CD, "CM": CM,
                            "Mach": Q(Mach,"1"), "Re": Q(Re,"1"), "source": "su2"}

    CL, CD, CM, Cf = _mock_rans(Mach, AoA, Re, alpha0_deg)
    return {"CL": CL, "CD": CD, "CM": CM, "Mach": Q(Mach,"1"), "Re": Q(Re,"1"),
            "source": "mock"}


su2_rans = Adapter(
    "su2_rans",
    backend="python",
    call=_rans_call,
    inputs={
        "cfg_template": {"desc": "Path to SU2 .cfg with turbulence model set"},
        "mesh":         {"desc": "Path to .su2 mesh (wall BCs required)"},
        "Mach":         {"unit": "1",   "desc": "Freestream Mach"},
        "AoA_deg":      {"unit": "deg", "desc": "Angle of attack"},
        "Reynolds":     {"unit": "1",   "desc": "Reynolds number", "default": 1e6},
        "sideslip_deg": {"unit": "deg", "desc": "Sideslip angle", "default": 0.0},
        "alpha0_deg":   {"unit": "deg", "desc": "Zero-lift AoA (mock)", "default": 0.0},
    },
    outputs={
        "CL":     {"unit": "1", "desc": "Lift coefficient"},
        "CD":     {"unit": "1", "desc": "Total drag (pressure + friction)"},
        "CM":     {"unit": "1", "desc": "Pitching moment"},
        "Mach":   {"unit": "1", "desc": "Freestream Mach"},
        "Re":     {"unit": "1", "desc": "Reynolds number"},
        "source": {"desc": "su2 or mock"},
    },
    desc="Turbulent RANS aerodynamics via SU2_CFD (Spalart-Allmaras)",
    tags=["su2", "RANS", "turbulent", "viscous", "CL", "CD"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    for adapter in (su2_euler, su2_rans):
        anvil.push(adapter, domain="cfd.su2",
                   description=adapter.desc, tags=adapter.tags)
    print("Registered: su2_euler, su2_rans  [domain: cfd.su2]")
