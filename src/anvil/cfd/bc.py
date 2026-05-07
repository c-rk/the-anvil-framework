"""
anvil.cfd.bc — Boundary condition types for 2D Euler CFD.

Ghost-cell approach: the solver extracts ghost and interior cell arrays for
each named patch, then calls bc.apply() to fill ghost cells in-place.

BC apply signature
------------------
    bc.apply(U_ghost, U_int, nx_out, ny_out, gamma, R_gas)

    U_ghost, U_int : ndarray (N, 4)   ghost / interior conservative states
    nx_out, ny_out : ndarray (N,)     outward unit normals at each face
    gamma, R_gas   : float            gas properties

Extensibility
-------------
Add a new BC by subclassing BoundaryCondition and implementing apply().
No changes needed in solver or mesh — just pass an instance in the bcs dict.
"""

from __future__ import annotations
import numpy as np

_TINY = 1.0e-30

# Conservative variable indices
RHO = 0; RHOU = 1; RHOV = 2; E = 3


def _freestream_state(M, p, T, alpha_deg, gamma, R_gas):
    """Return 1-D array [rho, rho*u, rho*v, E] for uniform freestream."""
    alpha = np.radians(alpha_deg)
    a     = np.sqrt(gamma * R_gas * T)
    V     = M * a
    u     = V * np.cos(alpha)
    v     = V * np.sin(alpha)
    rho   = p / (R_gas * T)
    E_tot = p / (gamma - 1.0) + 0.5 * rho * (u**2 + v**2)
    return np.array([rho, rho * u, rho * v, E_tot])


class BoundaryCondition:
    """Base class — subclasses implement apply()."""

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        """
        Fill U_ghost in-place.

        Parameters
        ----------
        U_ghost : (N, 4)  ghost cell conservative state — write here
        U_int   : (N, 4)  adjacent interior cell state   — read only
        nx_out  : (N,)    x-component of outward unit normal
        ny_out  : (N,)    y-component of outward unit normal
        """
        raise NotImplementedError


# ── Supersonic ────────────────────────────────────────────────────────────────

class SupersonicInlet(BoundaryCondition):
    """
    All characteristics enter — set ghost to fixed freestream state.

    Parameters
    ----------
    M         : freestream Mach number (> 1)
    p         : static pressure [Pa]
    T         : static temperature [K]
    alpha_deg : flow angle from +x axis [deg]
    """
    def __init__(self, M, p, T, alpha_deg=0.0, gamma=1.4, R_gas=287.058):
        self._U_fs = _freestream_state(M, p, T, alpha_deg, gamma, R_gas)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        U_ghost[:] = self._U_fs


class SupersonicOutlet(BoundaryCondition):
    """All characteristics leave — zero-gradient extrapolation."""

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        U_ghost[:] = U_int


# ── Subsonic inlet / outlet ───────────────────────────────────────────────────

class SubsonicInlet(BoundaryCondition):
    """
    Fixed-state subsonic inlet specified via total (stagnation) conditions.

    Isentropic conversion from total → static at the given Mach number.
    This is a fixed-ghost approach: use for steady-state where upstream
    conditions don't vary.  For transient accuracy, prefer PressureInlet.

    Parameters
    ----------
    M         : inlet Mach number (< 1)
    p0        : total pressure    [Pa]
    T0        : total temperature [K]
    alpha_deg : flow angle from +x axis [deg]
    """
    def __init__(self, M, p0, T0, alpha_deg=0.0, gamma=1.4, R_gas=287.058):
        g   = gamma
        fac = 1.0 + 0.5 * (g - 1.0) * M**2
        p_s = p0 / fac ** (g / (g - 1.0))
        T_s = T0 / fac
        self._U_fs = _freestream_state(M, p_s, T_s, alpha_deg, gamma, R_gas)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        U_ghost[:] = self._U_fs


class PressureInlet(BoundaryCondition):
    """
    Characteristic-based subsonic inlet: total pressure p0 and temperature T0.

    Uses the outgoing R+ Riemann invariant from the interior and the
    isentropic energy constraint from the specified total conditions to
    find the incoming normal velocity at each face.  Correctly handles
    varying normal directions (body-fitted meshes).

    Parameters
    ----------
    p0        : total (stagnation) pressure    [Pa]
    T0        : total (stagnation) temperature [K]
    alpha_deg : desired flow angle from +x [deg] (0 = normal to inlet)
    """
    def __init__(self, p0, T0, alpha_deg=0.0, gamma=1.4, R_gas=287.058):
        self.p0    = float(p0)
        self.T0    = float(T0)
        self.alpha = float(np.radians(alpha_deg))
        self.gamma = float(gamma)
        self.R_gas = float(R_gas)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        g = self.gamma; R = self.R_gas
        p0 = self.p0;   T0 = self.T0
        b  = 0.5 * (g - 1.0)
        a0_sq = g * R * T0    # stagnation a² = g*R*T0

        rho_i = U_int[:, RHO]
        u_i   = U_int[:, RHOU] / (rho_i + _TINY)
        v_i   = U_int[:, RHOV] / (rho_i + _TINY)
        p_i   = (g - 1.0) * (U_int[:, E] - 0.5 * rho_i * (u_i**2 + v_i**2))
        p_i   = np.maximum(p_i, _TINY)
        a_i   = np.sqrt(g * p_i / (rho_i + _TINY))
        Vn_i  = u_i * nx_out + v_i * ny_out

        R_plus = Vn_i + 2.0 * a_i / (g - 1.0)   # outgoing Riemann invariant

        # Solve: b*(b+1)*Vn² - 2*b²*R+*Vn + (b²*R+² - a0²) = 0
        A_q = b * (b + 1.0)
        B_q = -2.0 * b * b * R_plus
        C_q = b * b * R_plus**2 - a0_sq
        disc = np.maximum(B_q**2 - 4.0 * A_q * C_q, 0.0)
        Vn1  = (-B_q + np.sqrt(disc)) / (2.0 * A_q)
        Vn2  = (-B_q - np.sqrt(disc)) / (2.0 * A_q)
        # Pick root closest to current interior (stability)
        Vn_g = np.where(np.abs(Vn1 - Vn_i) <= np.abs(Vn2 - Vn_i), Vn1, Vn2)

        a_g  = np.maximum(b * (R_plus - Vn_g), 1.0)
        T_g  = a_g**2 / (g * R)
        p_g  = np.maximum(p0 * (T_g / T0) ** (g / (g - 1.0)), _TINY)
        rho_g = p_g / (R * np.maximum(T_g, _TINY))

        # Tangential velocity from total energy + Vn
        V_sq  = np.maximum(2.0 * (a0_sq - a_g**2) / (g - 1.0), Vn_g**2)
        Vt_sq = V_sq - Vn_g**2
        # Tangent direction (CCW 90° from outward normal)
        tx = -ny_out; ty = nx_out
        Vt_sign = np.sign(np.cos(self.alpha) * tx + np.sin(self.alpha) * ty + _TINY)
        Vt_g = np.sqrt(Vt_sq) * Vt_sign

        u_g = Vn_g * nx_out + Vt_g * tx
        v_g = Vn_g * ny_out + Vt_g * ty
        E_g = p_g / (g - 1.0) + 0.5 * rho_g * (u_g**2 + v_g**2)

        U_ghost[:, RHO]  = rho_g
        U_ghost[:, RHOU] = rho_g * u_g
        U_ghost[:, RHOV] = rho_g * v_g
        U_ghost[:, E]    = E_g


class VelocityInlet(BoundaryCondition):
    """
    Specified velocity and temperature at inlet.

    Density is set from a fixed reference pressure (or extrapolated).

    Parameters
    ----------
    u, v   : velocity components [m/s]
    T      : static temperature  [K]
    p_ref  : reference pressure for ρ = p/(R*T) [Pa]; None → extrapolate from interior
    """
    def __init__(self, u, v, T, p_ref=None, gamma=1.4, R_gas=287.058):
        self.u = float(u); self.v = float(v); self.T = float(T)
        self.p_ref = float(p_ref) if p_ref is not None else None
        self.gamma = float(gamma); self.R_gas = float(R_gas)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        g = self.gamma; R = self.R_gas
        if self.p_ref is not None:
            p_g = self.p_ref
        else:
            rho_i = U_int[:, RHO]
            u_i   = U_int[:, RHOU] / (rho_i + _TINY)
            v_i   = U_int[:, RHOV] / (rho_i + _TINY)
            p_g   = np.maximum(
                (g - 1.0) * (U_int[:, E] - 0.5 * rho_i * (u_i**2 + v_i**2)), _TINY)
        rho_g = p_g / (R * self.T)
        E_g   = p_g / (g - 1.0) + 0.5 * rho_g * (self.u**2 + self.v**2)
        U_ghost[:, RHO]  = rho_g
        U_ghost[:, RHOU] = rho_g * self.u
        U_ghost[:, RHOV] = rho_g * self.v
        U_ghost[:, E]    = E_g


class MassFlowInlet(BoundaryCondition):
    """
    Mass-flow-rate inlet: mdot = ρ * V * A.

    Flow is assumed normal to the inlet face unless alpha_deg is set.

    Parameters
    ----------
    mdot      : mass flow rate [kg/s]
    T         : static temperature  [K]
    area      : face area [m²] (2D: span × chord, or just 1 for per-unit-span)
    alpha_deg : flow angle from +x axis
    """
    def __init__(self, mdot, T, area=1.0, alpha_deg=0.0,
                 gamma=1.4, R_gas=287.058):
        self.mdot  = float(mdot)
        self.T     = float(T)
        self.area  = float(area)
        self.alpha = float(np.radians(alpha_deg))
        self.gamma = float(gamma)
        self.R_gas = float(R_gas)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        g = self.gamma; R = self.R_gas
        N = U_ghost.shape[0]
        # rho from continuity: ρ*V = mdot/A; V = mdot/(ρ*A) → iterate once
        rho_i = U_int[:, RHO]
        V_mag = self.mdot / (np.maximum(rho_i, 1e-6) * self.area)
        a_i   = np.sqrt(g * R * self.T)
        # Extrapolate pressure from interior
        u_i = U_int[:, RHOU] / (rho_i + _TINY)
        v_i = U_int[:, RHOV] / (rho_i + _TINY)
        p_g = np.maximum(
            (g - 1.0) * (U_int[:, E] - 0.5 * rho_i * (u_i**2 + v_i**2)), _TINY)
        rho_g = p_g / (R * self.T)
        V_mag = self.mdot / (np.maximum(rho_g, 1e-6) * self.area / N)
        u_g   = V_mag * np.cos(self.alpha)
        v_g   = V_mag * np.sin(self.alpha)
        E_g   = p_g / (g - 1.0) + 0.5 * rho_g * (u_g**2 + v_g**2)
        U_ghost[:, RHO]  = rho_g
        U_ghost[:, RHOU] = rho_g * u_g
        U_ghost[:, RHOV] = rho_g * v_g
        U_ghost[:, E]    = E_g


class SubsonicOutlet(BoundaryCondition):
    """
    Subsonic outlet: specify back pressure; extrapolate other quantities.
    One characteristic re-enters from downstream (pressure is fixed).
    """
    def __init__(self, p_back, gamma=1.4):
        self.p_back = float(p_back)
        self.gamma  = float(gamma)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        g     = self.gamma
        p_b   = self.p_back
        rho_i = U_int[:, RHO]
        u_i   = U_int[:, RHOU] / (rho_i + _TINY)
        v_i   = U_int[:, RHOV] / (rho_i + _TINY)
        p_i   = np.maximum(
            (g - 1.0) * (U_int[:, E] - 0.5 * rho_i * (u_i**2 + v_i**2)), _TINY)
        # Isentropic density adjustment
        rho_g = rho_i * (p_b / p_i) ** (1.0 / g)
        E_g   = p_b / (g - 1.0) + 0.5 * rho_g * (u_i**2 + v_i**2)
        U_ghost[:, RHO]  = rho_g
        U_ghost[:, RHOU] = rho_g * u_i
        U_ghost[:, RHOV] = rho_g * v_i
        U_ghost[:, E]    = E_g


# Alias for clarity
PressureOutlet = SubsonicOutlet


# ── Walls ─────────────────────────────────────────────────────────────────────

class SlipWall(BoundaryCondition):
    """
    Inviscid (slip) wall: reflects normal velocity component.

    Ghost state: ρ_g = ρ_i, V_g = V_i − 2(V_i·n̂)n̂, E_g = E_i.
    Normal direction is provided by the solver from actual mesh geometry,
    so this works correctly on body-fitted (non-Cartesian) meshes.
    """
    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        rho = U_int[:, RHO]
        u   = U_int[:, RHOU] / (rho + _TINY)
        v   = U_int[:, RHOV] / (rho + _TINY)
        Vn  = u * nx_out + v * ny_out
        u_g = u - 2.0 * Vn * nx_out
        v_g = v - 2.0 * Vn * ny_out
        U_ghost[:, RHO]  = rho
        U_ghost[:, RHOU] = rho * u_g
        U_ghost[:, RHOV] = rho * v_g
        U_ghost[:, E]    = U_int[:, E]


class Symmetry(SlipWall):
    """Symmetry plane — identical physics to slip wall."""
    pass


# ── Farfield (Riemann invariants) ─────────────────────────────────────────────

class Farfield(BoundaryCondition):
    """
    Riemann-invariant farfield BC.

    Supersonic inflow  → all from freestream.
    Supersonic outflow → all extrapolated from interior.
    Subsonic           → R+ from interior, R- from freestream.

    Parameters
    ----------
    M, p, T, alpha_deg : freestream conditions
    gamma, R_gas       : gas properties
    """
    def __init__(self, M, p, T, alpha_deg=0.0, gamma=1.4, R_gas=287.058):
        self._U_fs = _freestream_state(M, p, T, alpha_deg, gamma, R_gas)
        self.gamma = float(gamma)
        self.R_gas = float(R_gas)
        self._M_fs = float(M)

    def apply(self, U_ghost, U_int, nx_out, ny_out, gamma, R_gas):
        g = self.gamma; R = self.R_gas
        fs  = self._U_fs
        rho_fs = fs[RHO]
        u_fs   = fs[RHOU] / rho_fs
        v_fs   = fs[RHOV] / rho_fs
        p_fs   = (g - 1.0) * (fs[E] - 0.5 * rho_fs * (u_fs**2 + v_fs**2))
        a_fs   = np.sqrt(g * p_fs / rho_fs)
        Vn_fs  = u_fs * nx_out + v_fs * ny_out

        rho_i = U_int[:, RHO]
        u_i   = U_int[:, RHOU] / (rho_i + _TINY)
        v_i   = U_int[:, RHOV] / (rho_i + _TINY)
        p_i   = np.maximum(
            (g - 1.0) * (U_int[:, E] - 0.5 * rho_i * (u_i**2 + v_i**2)), _TINY)
        a_i   = np.sqrt(g * p_i / (rho_i + _TINY))
        Vn_i  = u_i * nx_out + v_i * ny_out

        R_plus  = Vn_i  + 2.0 * a_i  / (g - 1.0)   # outgoing
        R_minus = Vn_fs - 2.0 * a_fs / (g - 1.0)   # incoming from ∞

        Vn_g = 0.5 * (R_plus + R_minus)
        a_g  = np.maximum(0.25 * (g - 1.0) * (R_plus - R_minus), _TINY)

        is_outflow = Vn_i >= 0
        tx = -ny_out; ty = nx_out
        Vt_i_x  = u_i  - Vn_i  * nx_out; Vt_i_y  = v_i  - Vn_i  * ny_out
        Vt_fs_x = u_fs - Vn_fs * nx_out; Vt_fs_y = v_fs - Vn_fs * ny_out
        Vt_x = np.where(is_outflow, Vt_i_x, Vt_fs_x)
        Vt_y = np.where(is_outflow, Vt_i_y, Vt_fs_y)

        u_g = Vn_g * nx_out + Vt_x
        v_g = Vn_g * ny_out + Vt_y

        s_i  = p_i  / (rho_i  + _TINY) ** g
        s_fs = p_fs / rho_fs ** g
        s_g  = np.where(is_outflow, s_i, s_fs)

        rho_g = (a_g**2 / (g * np.maximum(s_g, _TINY))) ** (1.0 / (g - 1.0))
        p_g   = np.maximum(s_g * rho_g**g, _TINY)
        E_g   = p_g / (g - 1.0) + 0.5 * rho_g * (u_g**2 + v_g**2)

        U_ghost[:, RHO]  = rho_g
        U_ghost[:, RHOU] = rho_g * u_g
        U_ghost[:, RHOV] = rho_g * v_g
        U_ghost[:, E]    = E_g
