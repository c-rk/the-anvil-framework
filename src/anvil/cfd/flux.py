"""
anvil.cfd.flux — Inviscid flux schemes for 2D Euler equations.

Conservative state vector:  U = [rho, rho*u, rho*v, E]
    E = rho * (e + 0.5*(u^2+v^2))  (total energy per volume)
    p = (gamma-1) * (E - 0.5*rho*(u^2+v^2))

Available schemes
-----------------
roe_flux_2d    — Roe approximate Riemann solver (recommended)
                 Handles shocks and expansion fans correctly.
                 Includes Harten entropy fix to prevent expansion shocks.
hllc_flux_2d   — HLLC (Harten-Lax-van Leer Contact)
                 Simpler than Roe, good for most problems.
muscl_reconstruct — MUSCL with van Leer limiter for 2nd-order accuracy.

Extensibility
-------------
For viscous flows, add viscous_flux_2d() that computes the stress tensor
and heat conduction contributions. The solver calls both and sums them.
For 3D, extend each flux function with a w-velocity component and
k-direction sweep; the function signatures remain the same.

Array conventions
-----------------
All flux functions operate on batched states:
    UL, UR: shape (..., 4) — left and right states
    nxa, nya: shape (...,) — face normal vector * face area
Returns:
    F: shape (..., 4) — net flux through face (already multiplied by dA)
"""

from __future__ import annotations
import numpy as np

# Conservative variable indices
RHO  = 0
RHOU = 1
RHOV = 2
E    = 3

_TINY = 1.0e-30


# ── Primitive variable extraction ─────────────────────────────────────────────

def _to_prim(U, gamma):
    """U (...,4) → (rho, u, v, p, a, H) each shape (...)."""
    rho = U[..., RHO]
    u   = U[..., RHOU] / (rho + _TINY)
    v   = U[..., RHOV] / (rho + _TINY)
    p   = (gamma - 1.0) * (U[..., E] - 0.5 * rho * (u**2 + v**2))
    p   = np.maximum(p, _TINY)
    a   = np.sqrt(gamma * p / (rho + _TINY))
    H   = (U[..., E] + p) / (rho + _TINY)   # total enthalpy per unit mass
    return rho, u, v, p, a, H


def _euler_flux(rho, u, v, p, H, nx, ny):
    """Physical Euler flux in face-normal direction (nx, ny) — not yet × dA."""
    Vn = u * nx + v * ny
    return np.stack([
        rho * Vn,
        rho * u * Vn + p * nx,
        rho * v * Vn + p * ny,
        rho * H * Vn,
    ], axis=-1)


def _entropy_fix(lam, eps):
    """
    Harten's entropy fix: replace |lambda| near zero with smooth approximation.
    Returns a non-negative value ~= |lambda| but >= eps^2/(2*eps).
    """
    abs_lam = np.abs(lam)
    return np.where(abs_lam < eps, (lam**2 + eps**2) / (2.0 * eps), abs_lam)


# ── Roe flux ──────────────────────────────────────────────────────────────────

def roe_flux_2d(UL, UR, nxa, nya, gamma):
    """
    Roe approximate Riemann solver for 2D Euler equations.

    Handles subsonic, transonic, and supersonic flows including shocks.
    Harten entropy fix prevents expansion shocks at sonic points.

    Parameters
    ----------
    UL, UR : ndarray, shape (..., 4)
        Left and right conservative states [rho, rho*u, rho*v, E].
    nxa, nya : ndarray, shape (...)
        Face normal vector scaled by face area: (nx*dA, ny*dA).
    gamma : float
        Ratio of specific heats.

    Returns
    -------
    F : ndarray, shape (..., 4)
        Roe flux through face, already multiplied by face area dA.
    """
    # ── Primitive variables ──────────────────────────────────────────────────
    rhoL, uL, vL, pL, aL, HL = _to_prim(UL, gamma)
    rhoR, uR, vR, pR, aR, HR = _to_prim(UR, gamma)

    # ── Face unit normal ─────────────────────────────────────────────────────
    dA = np.sqrt(nxa**2 + nya**2) + _TINY
    nx = nxa / dA
    ny = nya / dA
    # Tangential: t = (-ny, nx)
    tx = -ny
    ty =  nx

    # ── Physical fluxes (central part) ───────────────────────────────────────
    FL = _euler_flux(rhoL, uL, vL, pL, HL, nx, ny)
    FR = _euler_flux(rhoR, uR, vR, pR, HR, nx, ny)
    F_cen = 0.5 * (FL + FR)

    # ── Roe averages ─────────────────────────────────────────────────────────
    sqL   = np.sqrt(np.maximum(rhoL, _TINY))
    sqR   = np.sqrt(np.maximum(rhoR, _TINY))
    denom = sqL + sqR + _TINY

    u_r   = (sqL * uL + sqR * uR) / denom
    v_r   = (sqL * vL + sqR * vR) / denom
    H_r   = (sqL * HL + sqR * HR) / denom
    rho_r = sqL * sqR                          # geometric mean density

    Vn_r  = u_r * nx + v_r * ny               # normal velocity (Roe)
    Vt_r  = u_r * tx + v_r * ty               # tangential velocity (Roe)

    a_r2  = (gamma - 1.0) * (H_r - 0.5 * (u_r**2 + v_r**2))
    a_r   = np.sqrt(np.maximum(a_r2, _TINY))

    # ── Eigenvalues + entropy fix ─────────────────────────────────────────────
    eps_ac = 0.05 * a_r   # acoustic threshold
    eps_en = 0.05 * a_r   # entropy/shear threshold

    lam1 = _entropy_fix(Vn_r - a_r, eps_ac)   # left-running acoustic
    lam2 = _entropy_fix(Vn_r,       eps_en)   # entropy wave
    lam3 = lam2                                # shear (tangential) wave
    lam4 = _entropy_fix(Vn_r + a_r, eps_ac)   # right-running acoustic

    # ── Primitive jumps ───────────────────────────────────────────────────────
    drho = rhoR - rhoL
    du   = uR   - uL
    dv   = vR   - vL
    dp   = pR   - pL
    dVn  = du * nx + dv * ny     # normal velocity jump
    dVt  = du * tx + dv * ty     # tangential velocity jump

    # ── Wave strengths (characteristic amplitudes) ────────────────────────────
    a2i  = 1.0 / (a_r**2 + _TINY)
    alpha1 = 0.5 * a2i * (dp - rho_r * a_r * dVn)   # left acoustic
    alpha2 = drho - dp * a2i                          # entropy
    alpha3 = rho_r * dVt                              # shear
    alpha4 = 0.5 * a2i * (dp + rho_r * a_r * dVn)   # right acoustic

    # ── Roe dissipation matrix (Σ |λk| αk rk) ────────────────────────────────
    D = np.zeros_like(UL)

    # Wave 1: r1 = [1, u-a*nx, v-a*ny, H-a*Vn]
    d1 = lam1 * alpha1
    D[..., 0] += d1
    D[..., 1] += d1 * (u_r - a_r * nx)
    D[..., 2] += d1 * (v_r - a_r * ny)
    D[..., 3] += d1 * (H_r - a_r * Vn_r)

    # Wave 2: r2 = [1, u, v, 0.5*(u^2+v^2)]   (entropy)
    d2 = lam2 * alpha2
    D[..., 0] += d2
    D[..., 1] += d2 * u_r
    D[..., 2] += d2 * v_r
    D[..., 3] += d2 * 0.5 * (u_r**2 + v_r**2)

    # Wave 3: r3 = [0, tx, ty, Vt]   (shear / tangential)
    d3 = lam3 * alpha3
    D[..., 1] += d3 * tx
    D[..., 2] += d3 * ty
    D[..., 3] += d3 * Vt_r

    # Wave 4: r4 = [1, u+a*nx, v+a*ny, H+a*Vn]
    d4 = lam4 * alpha4
    D[..., 0] += d4
    D[..., 1] += d4 * (u_r + a_r * nx)
    D[..., 2] += d4 * (v_r + a_r * ny)
    D[..., 3] += d4 * (H_r + a_r * Vn_r)

    # ── Multiply by face area ─────────────────────────────────────────────────
    return (F_cen - 0.5 * D) * dA[..., np.newaxis]


# ── HLLC flux ─────────────────────────────────────────────────────────────────

def hllc_flux_2d(UL, UR, nxa, nya, gamma):
    """
    HLLC (Harten-Lax-van Leer Contact) Riemann solver.

    Simpler than Roe; correctly captures contact discontinuities.
    Good for general subsonic/supersonic flows.
    """
    rhoL, uL, vL, pL, aL, HL = _to_prim(UL, gamma)
    rhoR, uR, vR, pR, aR, HR = _to_prim(UR, gamma)

    dA = np.sqrt(nxa**2 + nya**2) + _TINY
    nx = nxa / dA
    ny = nya / dA

    VnL = uL * nx + vL * ny
    VnR = uR * nx + vR * ny

    # Wave speed estimates (Roe-averaged)
    sqL    = np.sqrt(np.maximum(rhoL, _TINY))
    sqR    = np.sqrt(np.maximum(rhoR, _TINY))
    u_roe  = (sqL * uL + sqR * uR) / (sqL + sqR + _TINY)
    v_roe  = (sqL * vL + sqR * vR) / (sqL + sqR + _TINY)
    H_roe  = (sqL * HL + sqR * HR) / (sqL + sqR + _TINY)
    a_roe  = np.sqrt(np.maximum((gamma - 1.0) * (H_roe - 0.5 * (u_roe**2 + v_roe**2)), _TINY))
    Vn_roe = u_roe * nx + v_roe * ny

    SL = np.minimum(VnL - aL, Vn_roe - a_roe)
    SR = np.maximum(VnR + aR, Vn_roe + a_roe)

    # Contact wave speed
    S_star = ((pR - pL + rhoL * VnL * (SL - VnL) - rhoR * VnR * (SR - VnR))
              / (rhoL * (SL - VnL) - rhoR * (SR - VnR) + _TINY))

    def hllc_state(rho, u, v, p, H, Vn, Vt, E_tot, S, S_s):
        """HLLC star state."""
        factor = rho * (S - Vn) / (S - S_s + _TINY)
        vtx = u - Vn * nx   # tangential x: u - Vn*nx
        vty = v - Vn * ny   # tangential y: v - Vn*ny
        # Star state velocities: normal = S_star, tangential = same
        u_s = S_s * nx + vtx
        v_s = S_s * ny + vty
        E_s = E_tot / rho + (S_s - Vn) * (S_s + p / (rho * (S - Vn) + _TINY))
        return np.stack([factor,
                         factor * u_s,
                         factor * v_s,
                         factor * E_s], axis=-1)

    EL = UL[..., E]
    ER = UR[..., E]
    VtL_x = uL - VnL * nx; VtL_y = vL - VnL * ny
    VtR_x = uR - VnR * nx; VtR_y = vR - VnR * ny

    UL_star = hllc_state(rhoL, uL, vL, pL, HL, VnL, 0, EL, SL, S_star)
    UR_star = hllc_state(rhoR, uR, vR, pR, HR, VnR, 0, ER, SR, S_star)

    FL = _euler_flux(rhoL, uL, vL, pL, HL, nx, ny)
    FR = _euler_flux(rhoR, uR, vR, pR, HR, nx, ny)

    # Select flux region
    F = np.where((SL[..., np.newaxis] >= 0),
                 FL,
         np.where((S_star[..., np.newaxis] >= 0),
                  FL + SL[..., np.newaxis] * (UL_star - UL),
         np.where((SR[..., np.newaxis] >= 0),
                  FR + SR[..., np.newaxis] * (UR_star - UR),
                  FR)))

    return F * dA[..., np.newaxis]


# ── MUSCL reconstruction ──────────────────────────────────────────────────────

def _van_leer(r):
    """van Leer slope limiter: phi(r) = (r + |r|) / (1 + |r|). TVD."""
    return (r + np.abs(r)) / (1.0 + np.abs(r) + _TINY)


def muscl_reconstruct(U_ext, axis, order):
    """
    MUSCL reconstruction of left/right states at each face along `axis`.

    Parameters
    ----------
    U_ext : ndarray, shape (nx+2, ny+2, 4)
        Extended state array with ghost cells.
    axis : int
        0 for i-direction faces, 1 for j-direction faces.
    order : int
        1 = first-order (piecewise constant)
        2 = second-order (MUSCL + van Leer limiter)

    Returns
    -------
    UL, UR : each shape (nx+1, ny, 4) for axis=0 or (nx, ny+1, 4) for axis=1
        Left and right reconstructed states at each face.
        Face index I: UL[I] from cell (I), UR[I] from cell (I+1).
    """
    # Shift slices along chosen axis
    if axis == 0:
        # i-direction: faces between columns
        # Cells in extended array: 0..nx+1 (ghost at 0 and nx+1)
        Um2 = U_ext[:-3, 1:-1]   # cell i-1  (im1)
        Um1 = U_ext[1:-2, 1:-1]  # cell i    (left of face)
        Up0 = U_ext[2:-1, 1:-1]  # cell i+1  (right of face)
        Up1 = U_ext[3:,   1:-1]  # cell i+2  (ip1)
    else:
        # j-direction: faces between rows
        Um2 = U_ext[1:-1, :-3]
        Um1 = U_ext[1:-1, 1:-2]
        Up0 = U_ext[1:-1, 2:-1]
        Up1 = U_ext[1:-1, 3:]

    if order == 1:
        return Um1, Up0

    # Slopes
    dL = Um1 - Um2   # left slope
    dC = Up0 - Um1   # central slope (across face)
    dR = Up1 - Up0   # right slope

    # Limiters
    rL = dC / (dL + _TINY)   # for left state
    rR = dC / (dR + _TINY)   # for right state (reversed direction)

    phiL = _van_leer(rL)
    phiR = _van_leer(1.0 / (rR + _TINY))   # van Leer is symmetric

    UL = Um1 + 0.5 * phiL * dC
    UR = Up0 - 0.5 * phiR * dC

    return UL, UR


# ── Utility: local wave speed (for CFL) ───────────────────────────────────────

def max_wave_speeds(U, mesh, gamma):
    """
    Maximum wave speed per cell: max(|u|+a, |v|+a).
    Returns array shape (nx, ny).
    """
    rho, u, v, p, a, H = _to_prim(U[1:-1, 1:-1], gamma)   # physical cells
    dx = mesh.i_area[:-1, :] + mesh.i_area[1:, :]          # (nx, ny) avg i-face
    dy = mesh.j_area[:, :-1] + mesh.j_area[:, 1:]          # (nx, ny) avg j-face
    # Spectral radii
    lam_i = (np.abs(u) + a) * (mesh.i_area[:-1, :] + mesh.i_area[1:, :]) / 2
    lam_j = (np.abs(v) + a) * (mesh.j_area[:, :-1] + mesh.j_area[:, 1:]) / 2
    return lam_i + lam_j   # (nx, ny)
