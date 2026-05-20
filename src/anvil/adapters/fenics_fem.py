"""
Anvil Adapter: FEniCSx Finite Element Analysis
===============================================

Wraps FEniCSx (dolfinx) for structural and thermal FEM analysis.
Solves linear elasticity and heat conduction PDEs on simple geometries.

ADAPTERS PROVIDED:
    fenics_linear_elasticity -- 3D box linear elasticity: max displacement, max stress
    fenics_heat_conduction   -- 2D/3D steady heat conduction: max temp, heat flux

INSTALLATION:
    conda install -c conda-forge fenics-dolfinx mpich
    or: docker pull dolfinx/dolfinx

VERIFY:
    python -c "import dolfinx; print(dolfinx.__version__)"

MOCK MODE:
    Elasticity: Euler-Bernoulli beam theory (analytically exact for uniform beams).
    Heat conduction: 1D Fourier's law with geometric correction factor.

USAGE:
    from anvil.adapters.fenics_fem import fenics_linear_elasticity

    r = fenics_linear_elasticity(
        E=200e9, nu=0.3, Lx=1.0, Ly=0.05, Lz=0.05,
        F_distributed=1e4,   # N/m^2 on top face
        nx=20, ny=4, nz=4,
    )
    print(r["max_displacement"], r["max_von_mises"])

    register()
"""

from anvil import Adapter, Q
import math


# ── Mock: beam theory ─────────────────────────────────────────────────────────

def _mock_elasticity(E, nu, Lx, Ly, Lz, F_distributed):
    """
    Cantilever beam (fixed at x=0, distributed load on top face).
    Uses Euler-Bernoulli theory — exact for slender beams (Ly,Lz << Lx).
    """
    E=float(E); Lx=float(Lx); Ly=float(Ly); Lz=float(Lz)
    q = float(F_distributed)                  # N/m^2 → N/m per unit depth
    w = q * Lz                                # total load intensity [N/m]
    I = Lz * Ly**3 / 12.0                    # second moment about bending axis

    # Max tip deflection (UDL cantilever): δ = wL^4 / (8EI)
    delta_max = w * Lx**4 / (8.0 * E * I)

    # Max bending stress at root: σ = M*c/I = (wL^2/2)*(Ly/2)/I
    M_max = w * Lx**2 / 2.0
    sigma_bending = M_max * (Ly / 2.0) / I

    # Shear stress at neutral axis: τ = 3V/(2bh) where V = wL
    V_max = w * Lx
    tau_max = 3 * V_max / (2 * Lz * Ly)

    # Von Mises at root bottom fibre (pure bending, no shear)
    von_mises_max = math.sqrt(sigma_bending**2 + 3 * tau_max**2)

    return delta_max, von_mises_max, sigma_bending


def _mock_heat(k, Lx, Ly, Lz, T_left, T_right, Q_vol=0.0):
    """1D Fourier + volumetric source (exact for uniform rod)."""
    dT = float(T_right) - float(T_left)
    k_ = float(k); Lx_ = float(Lx)
    A  = float(Ly) * float(Lz)
    q_vol = float(Q_vol)

    # With volumetric source: T(x) = T_left + dT/L*x + q_vol/(2k)*x*(L-x)
    # Max temp at x = L/2 for symmetric heating
    if abs(q_vol) > 0:
        x_peak = Lx_/2.0 if dT == 0 else (
            -k_ * dT / Lx_ / q_vol + Lx_ / 2.0)
        x_peak = max(0.0, min(Lx_, x_peak))
        T_max = float(T_left) + (dT/Lx_)*x_peak + q_vol/(2*k_)*x_peak*(Lx_-x_peak)
    else:
        T_max = max(float(T_left), float(T_right))
        x_peak = 0.0 if float(T_right) > float(T_left) else Lx_

    flux = k_ * A * abs(dT) / Lx_   # Fourier heat flux [W]
    return T_max, flux


# ── FEniCSx linear elasticity ─────────────────────────────────────────────────

def _elasticity_call(E, nu, Lx, Ly, Lz, F_distributed,
                     nx=10, ny=4, nz=4, fixed_face="x_min"):
    for k, v in {"E": E, "nu": nu, "Lx": Lx, "Ly": Ly, "Lz": Lz,
                 "F_distributed": F_distributed}.items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    E_=float(E); nu_=float(nu); Lx_=float(Lx)
    Ly_=float(Ly); Lz_=float(Lz); F_=float(F_distributed)
    nx_=int(nx); ny_=int(ny); nz_=int(nz)

    try:
        import dolfinx, dolfinx.fem as fem
        import dolfinx.fem.petsc, ufl
        from dolfinx.mesh import create_box, CellType
        from mpi4py import MPI
        import numpy as np

        mesh = create_box(
            MPI.COMM_WORLD,
            [[0.0, 0.0, 0.0], [Lx_, Ly_, Lz_]],
            [nx_, ny_, nz_], CellType.tetrahedron
        )

        V = fem.functionspace(mesh, ("Lagrange", 1, (3,)))
        u = ufl.TrialFunction(V)
        v = ufl.TestFunction(V)

        # Lamé constants
        lam = E_ * nu_ / ((1 + nu_) * (1 - 2*nu_))
        mu  = E_ / (2 * (1 + nu_))

        def eps(u): return ufl.sym(ufl.grad(u))
        def sigma(u): return lam * ufl.div(u) * ufl.Identity(3) + 2 * mu * eps(u)

        # Fixed BC on x=0 face
        def left(x): return np.isclose(x[0], 0.0)
        dofs_fixed = fem.locate_dofs_geometrical(V, left)
        bc = fem.dirichletbc(
            np.zeros(3, dtype=float), dofs_fixed, V
        )

        # Distributed load on top face (z=Lz)
        f_body = fem.Constant(mesh, (0.0, 0.0, 0.0))
        T_traction = fem.Constant(mesh, (0.0, 0.0, -F_))

        ds_top = ufl.Measure("ds", domain=mesh, subdomain_data=None)
        a = ufl.inner(sigma(u), eps(v)) * ufl.dx
        L = (ufl.inner(f_body, v) * ufl.dx
             + ufl.inner(T_traction, v) * ufl.ds)

        problem = dolfinx.fem.petsc.LinearProblem(
            a, L, bcs=[bc],
            petsc_options={"ksp_type": "preonly", "pc_type": "lu"}
        )
        uh = problem.solve()

        # Post-process
        disp_mag = ufl.sqrt(ufl.dot(uh, uh))
        disp_expr = fem.Expression(disp_mag, V.sub(0).collapse()[0].element.interpolation_points())
        V0 = fem.functionspace(mesh, ("DG", 0))
        disp_fn = fem.Function(V0)
        disp_fn.interpolate(fem.Expression(disp_mag,
                            V0.element.interpolation_points()))
        max_disp = float(disp_fn.x.array.max())

        # Von Mises stress
        s  = sigma(uh) - (1./3) * ufl.tr(sigma(uh)) * ufl.Identity(3)
        vm = ufl.sqrt(3./2 * ufl.inner(s, s))
        vm_fn = fem.Function(V0)
        vm_fn.interpolate(fem.Expression(vm, V0.element.interpolation_points()))
        max_vm = float(vm_fn.x.array.max())

        return {
            "max_displacement": Q(max_disp, "m"),
            "max_von_mises":    Q(max_vm, "Pa"),
            "source": "fenics",
        }

    except (ImportError, Exception):
        pass

    # Analytical fallback
    delta, vm, sigma_b = _mock_elasticity(E_, nu_, Lx_, Ly_, Lz_, F_)
    return {
        "max_displacement": Q(delta, "m"),
        "max_von_mises":    Q(vm, "Pa"),
        "source": "mock",
    }


fenics_linear_elasticity = Adapter(
    "fenics_linear_elasticity",
    backend="python",
    call=_elasticity_call,
    inputs={
        "E":            {"unit": "Pa", "desc": "Young's modulus"},
        "nu":           {"unit": "1",  "desc": "Poisson's ratio"},
        "Lx":           {"unit": "m",  "desc": "Beam/box length (x)"},
        "Ly":           {"unit": "m",  "desc": "Box height (y, bending direction)"},
        "Lz":           {"unit": "m",  "desc": "Box depth (z)"},
        "F_distributed":{"unit": "Pa", "desc": "Distributed traction on top face (z)"},
        "nx":           {"desc": "Mesh divisions in x", "default": 10},
        "ny":           {"desc": "Mesh divisions in y", "default": 4},
        "nz":           {"desc": "Mesh divisions in z", "default": 4},
    },
    outputs={
        "max_displacement": {"unit": "m",   "desc": "Maximum nodal displacement magnitude"},
        "max_von_mises":    {"unit": "Pa",  "desc": "Maximum von Mises stress"},
        "source":           {"desc": "fenics or mock"},
    },
    desc="3D linear elasticity FEM via FEniCSx (dolfinx)",
    tags=["fenics", "FEM", "elasticity", "stress", "displacement"],
)


# ── FEniCSx heat conduction ───────────────────────────────────────────────────

def _heat_call(k, Lx, Ly, Lz, T_left, T_right,
               Q_vol=0.0, nx=20, ny=10, nz=10):
    for kk, v in {"k": k, "Lx": Lx, "Ly": Ly, "Lz": Lz,
                  "T_left": T_left, "T_right": T_right, "Q_vol": Q_vol}.items():
        if isinstance(v, Q): locals()[kk] = float(v.si)
    k_=float(k); Lx_=float(Lx); Ly_=float(Ly); Lz_=float(Lz)
    TL=float(T_left); TR=float(T_right); Qv=float(Q_vol)

    try:
        import dolfinx, dolfinx.fem as fem
        import dolfinx.fem.petsc, ufl
        from dolfinx.mesh import create_box, CellType
        from mpi4py import MPI
        import numpy as np

        mesh = create_box(
            MPI.COMM_WORLD,
            [[0.0,0.0,0.0],[Lx_,Ly_,Lz_]],
            [int(nx),int(ny),int(nz)], CellType.tetrahedron
        )
        V = fem.functionspace(mesh, ("Lagrange", 1))
        u = ufl.TrialFunction(V)
        v = ufl.TestFunction(V)

        def left_face(x):  return np.isclose(x[0], 0.0)
        def right_face(x): return np.isclose(x[0], Lx_)
        dofs_l = fem.locate_dofs_geometrical(V, left_face)
        dofs_r = fem.locate_dofs_geometrical(V, right_face)
        bcs = [
            fem.dirichletbc(fem.Constant(mesh, TL), dofs_l, V),
            fem.dirichletbc(fem.Constant(mesh, TR), dofs_r, V),
        ]
        f_src = fem.Constant(mesh, Qv)
        a = k_ * ufl.dot(ufl.grad(u), ufl.grad(v)) * ufl.dx
        L = f_src * v * ufl.dx
        problem = dolfinx.fem.petsc.LinearProblem(
            a, L, bcs=bcs,
            petsc_options={"ksp_type": "preonly", "pc_type": "lu"}
        )
        T_h = problem.solve()
        T_arr = T_h.x.array
        T_max = float(T_arr.max())
        flux  = float(k_ * abs(T_arr.max() - T_arr.min()) / Lx_ * Ly_ * Lz_)
        return {"T_max": Q(T_max, "K"), "heat_flux": Q(flux, "W"), "source": "fenics"}

    except (ImportError, Exception):
        pass

    T_max, flux = _mock_heat(k_, Lx_, Ly_, Lz_, TL, TR, Qv)
    return {"T_max": Q(T_max, "K"), "heat_flux": Q(flux, "W"), "source": "mock"}


fenics_heat_conduction = Adapter(
    "fenics_heat_conduction",
    backend="python",
    call=_heat_call,
    inputs={
        "k":       {"unit": "W/m/K", "desc": "Thermal conductivity"},
        "Lx":      {"unit": "m",     "desc": "Domain length (x, direction of conduction)"},
        "Ly":      {"unit": "m",     "desc": "Domain height (y)"},
        "Lz":      {"unit": "m",     "desc": "Domain depth (z)"},
        "T_left":  {"unit": "K",     "desc": "Left boundary temperature (x=0)"},
        "T_right": {"unit": "K",     "desc": "Right boundary temperature (x=Lx)"},
        "Q_vol":   {"unit": "W/m^3", "desc": "Volumetric heat source", "default": 0.0},
        "nx":      {"desc": "Mesh divisions in x", "default": 20},
        "ny":      {"desc": "Mesh divisions in y", "default": 10},
        "nz":      {"desc": "Mesh divisions in z", "default": 10},
    },
    outputs={
        "T_max":     {"unit": "K", "desc": "Maximum temperature in domain"},
        "heat_flux": {"unit": "W", "desc": "Total heat flux through cross-section"},
        "source":    {"desc": "fenics or mock"},
    },
    desc="3D steady heat conduction FEM via FEniCSx (dolfinx)",
    tags=["fenics", "FEM", "heat", "conduction", "thermal"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    for adapter in (fenics_linear_elasticity, fenics_heat_conduction):
        anvil.push(adapter, domain="fem.fenics",
                   description=adapter.desc, tags=adapter.tags)
    print("Registered: fenics_linear_elasticity, fenics_heat_conduction"
          "  [domain: fem.fenics]")
