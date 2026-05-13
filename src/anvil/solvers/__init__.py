"""
Built-in solvers: SciPy wrappers with sensible defaults and progress output.

Available:
    find_root(func, ...)               — scalar root f(x) = 0
    solve_nonlinear(func, x0, ...)     — system F(x) = 0
    solve_ode(func, t_span, y0, ...)   — dy/dt = f(t, y)  [explicit, RK45]
    solve_ode_stiff(func, t_span, y0, ...) — stiff ODEs   [BDF/Radau]
    solve_bvp(func, bc, x, y, ...)     — boundary value problem
    solve_pde_heat_1d(...)             — 1D heat / diffusion equation [Crank-Nicolson]
    minimize(func, x0, ...)            — scalar minimization
"""

import numpy as np
from scipy import optimize as _opt
from scipy import integrate as _integ
from typing import Optional, Callable, Sequence


# ============================================================
# Algebraic solvers
# ============================================================

def find_root(func, x0=None, bracket=None, method="auto", tol=1e-12, maxiter=100):
    """
    Find root of f(x) = 0.

    Parameters
    ----------
    func : callable
        f(x) → float
    x0 : float, optional
        Initial guess (Newton / secant).
    bracket : (a, b), optional
        Bracket containing the root (Brent's method).
    method : str
        "auto", "brent", "newton", or "secant".
    """
    if method == "auto":
        method = "brent" if bracket else "newton" if x0 is not None else None
        if method is None:
            raise ValueError("Provide bracket=(a,b) or x0=guess.")

    if method == "brent":
        return float(_opt.brentq(func, bracket[0], bracket[1], xtol=tol, maxiter=maxiter))
    elif method in ("newton", "secant"):
        return float(_opt.newton(func, x0, tol=tol, maxiter=maxiter))
    raise ValueError(f"Unknown method: '{method}'")


def solve_nonlinear(func, x0, method="hybr", tol=1e-10, maxiter=200, jac=None):
    """
    Solve F(x) = 0 for a system of nonlinear equations.

    Parameters
    ----------
    func : callable
        F(x) → array of residuals, same length as x.
    x0 : array-like
        Initial guess.
    method : str
        SciPy root method: "hybr" (Powell hybrid, default), "lm", "broyden1", etc.
    """
    x0 = np.asarray(x0, dtype=np.float64)
    opts = {"maxfev": maxiter * len(x0)} if method == "hybr" else {"maxiter": maxiter}
    result = _opt.root(func, x0, method=method, tol=tol, options=opts, jac=jac)
    if not result.success:
        raise RuntimeError(f"Nonlinear solve failed: {result.message}")
    return result.x


# ============================================================
# ODE solvers
# ============================================================

def solve_ode(func, t_span, y0, method="RK45", t_eval=None, rtol=1e-8, atol=1e-10,
              max_step=np.inf, events=None, verbose=False):
    """
    Integrate dy/dt = f(t, y).   [Explicit — best for non-stiff problems]

    Parameters
    ----------
    func : callable
        f(t, y) → dy/dt array.
    t_span : (t0, tf)
        Integration interval.
    y0 : array-like
        Initial conditions.
    method : str
        "RK45" (default), "RK23", "DOP853". Use solve_ode_stiff() for stiff.
    t_eval : array-like, optional
        Times at which to store the solution.
    rtol, atol : float
        Relative and absolute tolerances.
    events : callable or list, optional
        Event functions; integration stops when an event returns 0.
    verbose : bool
        Print progress every ~10% of integration interval.

    Returns
    -------
    dict with keys: t, y, success, message, nfev
    """
    y0 = np.asarray(y0, dtype=np.float64)
    t0, tf = float(t_span[0]), float(t_span[1])

    wrapped_func = func
    if verbose:
        report_interval = (tf - t0) / 10
        last_report = [t0]
        orig_func = func

        def wrapped_func(t, y):
            if t - last_report[0] >= report_interval:
                print(f"  ODE t = {t:.4e}  (y[0] = {float(y[0]):.4e})")
                last_report[0] = t
            return orig_func(t, y)

    sol = _integ.solve_ivp(
        wrapped_func, t_span, y0, method=method, t_eval=t_eval,
        rtol=rtol, atol=atol, max_step=max_step, events=events,
        dense_output=True,
    )

    if verbose:
        status = "converged" if sol.success else "FAILED"
        print(f"  ODE {status}: {sol.nfev} function evaluations, "
              f"t_final = {sol.t[-1]:.4e}")

    return {
        "t": sol.t,
        "y": sol.y,
        "success": sol.success,
        "message": sol.message,
        "nfev": sol.nfev,
        "sol": sol,  # dense output callable: sol.sol(t) → y(t)
    }


def solve_ode_stiff(func, t_span, y0, method="BDF", t_eval=None,
                    rtol=1e-6, atol=1e-10, jac=None, events=None, verbose=False):
    """
    Integrate stiff dy/dt = f(t, y).   [Implicit — combustion, kinetics, diffusion]

    Same interface as solve_ode() but uses BDF or Radau by default.

    Parameters
    ----------
    method : str
        "BDF" (backward differentiation, default) or "Radau" (implicit Runge-Kutta).
        BDF is faster for large stiff systems; Radau is more accurate for small ones.
    jac : callable, optional
        Jacobian df/dy. If None, estimated by finite differences.
    """
    y0 = np.asarray(y0, dtype=np.float64)
    t0, tf = float(t_span[0]), float(t_span[1])

    wrapped_func = func
    if verbose:
        report_interval = (tf - t0) / 10
        last_report = [t0]
        orig_func = func

        def wrapped_func(t, y):
            if t - last_report[0] >= report_interval:
                print(f"  ODE(stiff) t = {t:.4e}  (y[0] = {float(y[0]):.4e})")
                last_report[0] = t
            return orig_func(t, y)

    sol = _integ.solve_ivp(
        wrapped_func, t_span, y0, method=method, t_eval=t_eval,
        rtol=rtol, atol=atol, jac=jac, events=events, dense_output=True,
    )

    if not sol.success and not verbose:
        raise RuntimeError(
            f"Stiff ODE solver ({method}) failed: {sol.message}\n"
            f"  Try: looser tolerances (rtol=1e-4), different method, "
            f"or provide a Jacobian via jac=."
        )

    if verbose:
        status = "converged" if sol.success else "FAILED"
        print(f"  ODE-stiff {status}: {sol.nfev} rhs evals, "
              f"t_final = {sol.t[-1]:.4e}")

    return {
        "t": sol.t,
        "y": sol.y,
        "success": sol.success,
        "message": sol.message,
        "nfev": sol.nfev,
        "sol": sol,
    }


def solve_bvp(func, bc, x, y_init, tol=1e-3, max_nodes=1000, verbose=False):
    """
    Solve a boundary value problem: dy/dx = f(x, y),  bc(y(a), y(b)) = 0.

    Wrapper around scipy.integrate.solve_bvp.

    Parameters
    ----------
    func : callable
        f(x, y) → dy/dx array, shape (n,) or (n, m) for m collocation points.
    bc : callable
        bc(ya, yb) → residual array of length n.
    x : array-like
        Initial mesh points (1D array from a to b).
    y_init : array-like
        Initial guess for y at each mesh point, shape (n, len(x)).
    tol : float
        Residual tolerance.
    max_nodes : int
        Maximum number of mesh nodes allowed.

    Returns
    -------
    dict with keys: x, y, success, message, sol (dense callable)

    Example
    -------
    Solve y'' = -y,  y(0) = 0,  y(pi) = 0  (sin solution):

        def f(x, y):
            return np.vstack([y[1], -y[0]])

        def bc(ya, yb):
            return np.array([ya[0], yb[0]])

        x = np.linspace(0, np.pi, 5)
        y = np.zeros((2, x.size))
        y[0] = np.sin(x)   # initial guess

        result = anvil.solvers.solve_bvp(f, bc, x, y)
        x_fine = np.linspace(0, np.pi, 100)
        y_fine = result["sol"](x_fine)[0]
    """
    x = np.asarray(x, dtype=np.float64)
    y_init = np.asarray(y_init, dtype=np.float64)

    sol = _integ.solve_bvp(func, bc, x, y_init, tol=tol, max_nodes=max_nodes,
                            verbose=2 if verbose else 0)

    if not sol.success and not verbose:
        raise RuntimeError(
            f"BVP solver failed: {sol.message}\n"
            f"  Try: better initial guess, finer initial mesh, or looser tol."
        )

    return {
        "x": sol.x,
        "y": sol.y,
        "success": sol.success,
        "message": sol.message,
        "residual": sol.rms_residuals,
        "sol": sol.sol,  # callable: sol(x) → y(x)
    }


# ============================================================
# PDE solver: 1D parabolic (heat / diffusion)
# ============================================================

def solve_pde_heat_1d(
    alpha,          # diffusivity [m^2/s] or thermal diffusivity
    x_span,         # (x_left, x_right)
    t_span,         # (t_start, t_end)
    u_init,         # initial condition: callable u(x) or array of length nx
    bc_left=None,   # Dirichlet left: float or callable u_left(t); None = Neumann zero-flux
    bc_right=None,  # Dirichlet right: float or callable u_right(t); None = Neumann zero-flux
    source=None,    # source term: callable f(x, t, u); None = no source
    nx=100,         # number of spatial points
    nt=None,        # number of time steps (auto if None)
    verbose=False,
):
    """
    Solve the 1D parabolic PDE (heat / diffusion equation):

        ∂u/∂t = α · ∂²u/∂x²  +  f(x, t, u)

    Uses the Crank-Nicolson scheme (unconditionally stable, 2nd-order accurate).

    Parameters
    ----------
    alpha : float
        Diffusivity (constant). For heat: α = k / (ρ · cp).
    x_span : (float, float)
        Spatial domain [x_left, x_right].
    t_span : (float, float)
        Time interval [t_start, t_end].
    u_init : callable or array
        Initial condition. Callable: u_init(x) → array. Array: length nx.
    bc_left, bc_right : float, callable, or None
        Boundary conditions. Float/callable → Dirichlet. None → zero-flux Neumann.
    source : callable or None
        Source term f(x, t, u) → array of length nx.
    nx : int
        Number of spatial grid points.
    nt : int or None
        Number of time steps. If None, chosen for stability (CFL-like).

    Returns
    -------
    dict with keys:
        x  : spatial grid, shape (nx,)
        t  : time array, shape (nt+1,)
        u  : solution array, shape (nt+1, nx)

    Example
    -------
    Heat equation on [0, 1], Dirichlet T=0 at both ends, Gaussian initial pulse:

        import numpy as np
        result = anvil.solvers.solve_pde_heat_1d(
            alpha=1e-5,
            x_span=(0, 1),
            t_span=(0, 10),
            u_init=lambda x: np.exp(-100 * (x - 0.5)**2),
            bc_left=0.0,
            bc_right=0.0,
            nx=100,
        )
        T_final = result["u"][-1]   # temperature profile at t=10 s
    """
    from scipy.linalg import solve_banded

    x0, xL = float(x_span[0]), float(x_span[1])
    t0, tf = float(t_span[0]), float(t_span[1])
    alpha = float(alpha)

    dx = (xL - x0) / (nx - 1)
    x = np.linspace(x0, xL, nx)

    # Choose dt for good accuracy (Crank-Nicolson is unconditionally stable,
    # but small dt gives better temporal accuracy)
    if nt is None:
        dt_cfl = 0.25 * dx**2 / (alpha + 1e-300)  # CFL-like estimate
        dt = min(dt_cfl, (tf - t0) / 100)
        nt = max(10, int(np.ceil((tf - t0) / dt)))
    else:
        nt = int(nt)
    dt = (tf - t0) / nt
    t = np.linspace(t0, tf, nt + 1)

    r = alpha * dt / (2 * dx**2)  # Crank-Nicolson parameter

    # Initial condition
    if callable(u_init):
        u = np.asarray(u_init(x), dtype=np.float64)
    else:
        u = np.asarray(u_init, dtype=np.float64)
        if len(u) != nx:
            raise ValueError(f"u_init length {len(u)} != nx={nx}")

    # Storage
    u_all = np.zeros((nt + 1, nx))
    u_all[0] = u.copy()

    # Build tridiagonal LHS (ab format for solve_banded)
    # (I + r*A) u^{n+1} = (I - r*A) u^n  where A is the 2nd-difference matrix
    # LHS diagonal: 1 + 2r; off-diagonals: -r
    diag = np.full(nx, 1 + 2 * r)
    off  = np.full(nx - 1, -r)

    # Apply Dirichlet BCs to LHS by fixing boundary rows
    diag[0]  = 1.0;  off[0]   = 0.0
    diag[-1] = 1.0;  # off[-1] handled by structure

    # ab format: row 0 = superdiag (offset +1), row 1 = diag, row 2 = subdiag (offset -1)
    ab = np.zeros((3, nx))
    ab[0, 1:]  = -r       # superdiagonal
    ab[1, :]   = diag     # main diagonal
    ab[2, :-1] = -r       # subdiagonal
    # BC rows: boundary points have only diagonal = 1
    ab[0, 1]   = 0.0      # left BC: no superdiag coupling
    ab[2, -2]  = 0.0      # right BC: no subdiag coupling

    report_every = max(1, nt // 10)

    for n in range(nt):
        tn = t[n]
        tn1 = t[n + 1]
        u_curr = u_all[n]

        # RHS: (I - r*A) u^n
        rhs = u_curr.copy()
        rhs[1:-1] += r * (u_curr[:-2] - 2*u_curr[1:-1] + u_curr[2:])

        # Add source term (half-step approximation)
        if source is not None:
            f_n  = np.asarray(source(x, tn,  u_curr), dtype=np.float64)
            f_n1 = np.asarray(source(x, tn1, u_curr), dtype=np.float64)
            rhs += 0.5 * dt * (f_n + f_n1)

        # Apply boundary conditions to RHS
        if bc_left is not None:
            bl = float(bc_left(tn1) if callable(bc_left) else bc_left)
            rhs[0] = bl
        else:
            rhs[0] += r * u_curr[1]  # Neumann zero-flux: ghost = u[1]

        if bc_right is not None:
            br = float(bc_right(tn1) if callable(bc_right) else bc_right)
            rhs[-1] = br
        else:
            rhs[-1] += r * u_curr[-2]  # Neumann zero-flux

        u_all[n + 1] = solve_banded((1, 1), ab, rhs)

        if verbose and (n + 1) % report_every == 0:
            print(f"  PDE step {n+1:5d}/{nt}  t = {tn1:.4e}"
                  f"  u_max = {u_all[n+1].max():.4e}")

    if verbose:
        print(f"  PDE done: {nt} steps, dx={dx:.4e}, dt={dt:.4e}")

    return {"x": x, "t": t, "u": u_all, "dx": dx, "dt": dt}


# ============================================================
# Optimization
# ============================================================

def minimize(func, x0, method="L-BFGS-B", bounds=None, tol=1e-8, maxiter=500, jac=None):
    """
    Minimize a scalar objective f(x).

    Parameters
    ----------
    method : str
        "L-BFGS-B" (default, supports bounds), "SLSQP", "Nelder-Mead", etc.
    bounds : list of (lo, hi) or None
        Parameter bounds (used by L-BFGS-B, SLSQP).

    Returns
    -------
    dict with keys: x, fun, success, message, nit
    """
    x0 = np.asarray(x0, dtype=np.float64)
    result = _opt.minimize(func, x0, method=method, bounds=bounds, tol=tol, jac=jac,
                            options={"maxiter": maxiter})
    return {
        "x": result.x,
        "fun": result.fun,
        "success": result.success,
        "message": result.message,
        "nit": result.nit,
    }


def minimize_global(func, bounds, method="differential_evolution", seed=None,
                    maxiter=1000, tol=1e-6, workers=1, callback=None, verbose=False):
    """
    Global minimization — no gradient needed, population-based search.

    Parameters
    ----------
    func : callable
        f(x) → float. Must accept a 1D numpy array.
        For workers != 1 with "differential_evolution", must be picklable
        (module-level function, not a closure).
    bounds : list of (lo, hi)
        Search bounds per dimension. Required.
    method : str
        "differential_evolution" (default) — population DE, robust, parallelizable
        "dual_annealing"                   — simulated annealing + local polish
        "shgo"                             — simplicial homology, handles constraints well
        "basinhopping"                     — multi-start gradient descent
    seed : int or None
        Random seed for reproducibility.
    maxiter : int
        Maximum iterations (DE) or function evaluations (DA/BH).
    tol : float
        Convergence tolerance.
    workers : int
        Parallel workers for "differential_evolution" only (-1 = all CPUs).
        Requires func to be picklable (module-level, not a closure).
    callback : callable or None
        Called each iteration. Signature is method-specific (passed through to scipy).
    verbose : bool
        Print start/finish summary.

    Returns
    -------
    dict with keys: x, fun, success, message, nit, nfev

    Examples
    --------
    Minimize Rosenbrock over [-2, 2]^2:

        from scipy.optimize import rosen
        result = anvil.solvers.minimize_global(rosen, bounds=[(-2, 2), (-2, 2)])
        print(result["x"], result["fun"])

    Maximize thrust by passing negated objective:

        result = anvil.solvers.minimize_global(
            lambda x: -thrust(x), bounds=[(0.01, 0.1), (0.5, 5.0)],
            method="dual_annealing", seed=42,
        )
    """
    bounds = [tuple(b) for b in bounds]
    ndim = len(bounds)

    if verbose:
        print(f"  minimize_global: method={method!r}  ndim={ndim}  maxiter={maxiter}")

    if method == "differential_evolution":
        result = _opt.differential_evolution(
            func, bounds, seed=seed, maxiter=maxiter, tol=tol,
            workers=workers, callback=callback, polish=True,
        )
    elif method == "dual_annealing":
        result = _opt.dual_annealing(
            func, bounds, seed=seed, maxiter=maxiter, callback=callback,
        )
    elif method == "shgo":
        result = _opt.shgo(
            func, bounds,
            options={"maxiter": maxiter, "ftol": tol},
            callback=callback,
        )
    elif method == "basinhopping":
        x0 = np.array([0.5 * (lo + hi) for lo, hi in bounds])
        result = _opt.basinhopping(
            func, x0, niter=maxiter, seed=seed,
            minimizer_kwargs={"method": "L-BFGS-B", "bounds": bounds},
            callback=callback,
        )
    else:
        raise ValueError(
            f"Unknown global method: '{method}'. "
            f"Choose: 'differential_evolution', 'dual_annealing', 'shgo', 'basinhopping'."
        )

    if verbose:
        ok = getattr(result, "success", True)
        status = "converged" if ok else "FAILED"
        print(f"  minimize_global {status}: "
              f"{getattr(result, 'nfev', '?')} evals  "
              f"f_best = {result.fun:.6g}")

    return {
        "x": result.x,
        "fun": result.fun,
        "success": getattr(result, "success", True),
        "message": getattr(result, "message", ""),
        "nit": getattr(result, "nit", 0),
        "nfev": getattr(result, "nfev", 0),
    }
