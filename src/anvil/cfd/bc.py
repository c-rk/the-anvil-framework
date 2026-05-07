"""
anvil.cfd.bc — Boundary condition types for 2D Euler CFD.

Ghost-cell approach: each BC sets ghost cell values at the start of
every iteration so the flux computation treats boundaries naturally.

Side naming convention (matches dict keys passed to CFDSolver):
    "west"  — i = 0   boundary (left  / inlet for +x flow)
    "east"  — i = nx  boundary (right / outlet)
    "south" — j = 0   boundary (bottom wall or lower farfield)
    "north" — j = ny  boundary (top   farfield or symmetry)

Extended array layout (physical cells at [1..nx, 1..ny]):
    Ghost row/col 0 at west and south edges.
    Ghost row/col nx+1 / ny+1 at east and north edges.

Extensibility
-------------
To add: SubsonicInlet (total pressure+temperature), periodic (shared ghost
cells), no-slip wall (zero velocity, requires viscous flux layer).
For 3D: add "bottom"/"top" sides and handle k-ghost layers identically.
"""

from __future__ import annotations
import numpy as np

_TINY = 1.0e-30

# Conservative variable indices
RHO = 0; RHOU = 1; RHOV = 2; E = 3


class BoundaryCondition:
    """Base class.  Subclasses implement apply()."""

    def apply(self, U_ext, mesh, side, gamma, R_gas):
        raise NotImplementedError

    @staticmethod
    def _freestream_state(M, p, T, alpha_deg, gamma, R_gas):
        """Return [rho, rho*u, rho*v, E] for uniform freestream."""
        alpha = np.radians(alpha_deg)
        a_inf = np.sqrt(gamma * R_gas * T)
        V_inf = M * a_inf
        u_inf = V_inf * np.cos(alpha)
        v_inf = V_inf * np.sin(alpha)
        rho   = p / (R_gas * T)
        E_inf = p / (gamma - 1.0) + 0.5 * rho * (u_inf**2 + v_inf**2)
        return np.array([rho, rho * u_inf, rho * v_inf, E_inf])


class SupersonicInlet(BoundaryCondition):
    """
    All four characteristics enter the domain — set ghost = freestream.

    Parameters
    ----------
    M : float       Freestream Mach number (> 1)
    p : float       Static pressure   [Pa]
    T : float       Static temperature [K]
    alpha_deg : float  Flow angle from +x axis [deg]
    gamma : float   Ratio of specific heats
    R_gas : float   Specific gas constant [J/kg/K]
    """

    def __init__(self, M, p, T, alpha_deg=0.0, gamma=1.4, R_gas=287.058):
        self._U_fs = self._freestream_state(M, p, T, alpha_deg, gamma, R_gas)

    def apply(self, U_ext, mesh, side, gamma, R_gas):
        U = self._U_fs
        if side == "west":
            U_ext[0, 1:-1] = U
        elif side == "east":
            U_ext[-1, 1:-1] = U
        elif side == "south":
            U_ext[1:-1, 0] = U
        elif side == "north":
            U_ext[1:-1, -1] = U


class SupersonicOutlet(BoundaryCondition):
    """
    All characteristics leave — extrapolate (zero-gradient) from interior.
    """

    def apply(self, U_ext, mesh, side, gamma, R_gas):
        if side == "west":
            U_ext[0, 1:-1] = U_ext[1, 1:-1]
        elif side == "east":
            U_ext[-1, 1:-1] = U_ext[-2, 1:-1]
        elif side == "south":
            U_ext[1:-1, 0] = U_ext[1:-1, 1]
        elif side == "north":
            U_ext[1:-1, -1] = U_ext[1:-1, -2]


class SubsonicOutlet(BoundaryCondition):
    """
    Subsonic outlet: specify back pressure; extrapolate other quantities.

    One characteristic re-enters from downstream.  Pressure is fixed;
    density, velocities are extrapolated from interior.
    """

    def __init__(self, p_back, gamma=1.4):
        self.p_back = float(p_back)
        self.gamma  = float(gamma)

    def _apply_side(self, U_int, p_back, gamma):
        """Return ghost state for one layer of interior cells."""
        rho_i = U_int[..., RHO]
        u_i   = U_int[..., RHOU] / (rho_i + _TINY)
        v_i   = U_int[..., RHOV] / (rho_i + _TINY)
        p_i   = (gamma - 1.0) * (U_int[..., E]
                                  - 0.5 * rho_i * (u_i**2 + v_i**2))
        # Extrapolate rho from pressure ratio (isentropic)
        rho_g = rho_i * (p_back / np.maximum(p_i, _TINY)) ** (1.0 / gamma)
        E_g   = p_back / (gamma - 1.0) + 0.5 * rho_g * (u_i**2 + v_i**2)
        return np.stack([rho_g, rho_g * u_i, rho_g * v_i, E_g], axis=-1)

    def apply(self, U_ext, mesh, side, gamma, R_gas):
        g = gamma
        if side == "east":
            U_ext[-1, 1:-1] = self._apply_side(U_ext[-2, 1:-1], self.p_back, g)
        elif side == "west":
            U_ext[0, 1:-1]  = self._apply_side(U_ext[1, 1:-1],  self.p_back, g)
        elif side == "north":
            U_ext[1:-1, -1] = self._apply_side(U_ext[1:-1, -2], self.p_back, g)
        elif side == "south":
            U_ext[1:-1, 0]  = self._apply_side(U_ext[1:-1, 1],  self.p_back, g)


class SlipWall(BoundaryCondition):
    """
    Inviscid (slip) wall: zero normal velocity, mirror normal component.

    The ghost cell has:
        rho_g = rho_i
        V_g   = V_i - 2*(V_i . n_out) * n_out
        p_g   = p_i
        E_g   = E_i  (pressure same → energy same for same speed magnitude)

    n_out is the outward domain normal (pointing away from fluid domain).
    For south wall: n_out points in -y direction for Cartesian mesh.
    For a wedge, n_out is computed from the actual face geometry.

    When `auto_normal=True` (default), the BC reads the face geometry
    from the mesh to get the correct outward normal for body-fitted grids.
    """

    def __init__(self, auto_normal: bool = True):
        self.auto_normal = auto_normal

    def _reflect(self, U_int, nx_out, ny_out):
        """
        Reflect velocity about face normal.
        nx_out, ny_out: outward normal (from domain), shape (...).
        """
        rho = U_int[..., RHO]
        u   = U_int[..., RHOU] / (rho + _TINY)
        v   = U_int[..., RHOV] / (rho + _TINY)

        Vn = u * nx_out + v * ny_out
        u_g = u - 2.0 * Vn * nx_out
        v_g = v - 2.0 * Vn * ny_out
        E_g = U_int[..., E]                           # same total energy (|V| unchanged)

        U_g = np.empty_like(U_int)
        U_g[..., RHO]  = rho
        U_g[..., RHOU] = rho * u_g
        U_g[..., RHOV] = rho * v_g
        U_g[..., E]    = E_g
        return U_g

    def apply(self, U_ext, mesh, side, gamma, R_gas):
        if side == "south":
            if self.auto_normal:
                # j-face at J=0: n*a = (j_nxa[:,0], j_nya[:,0])
                # This normal points from ghost INTO domain (+j direction)
                # Outward (into ghost) = opposite
                nxa = -mesh.j_nxa[:, 0]
                nya = -mesh.j_nya[:, 0]
            else:
                nxa = np.zeros(mesh.nx); nya = -np.ones(mesh.nx)
            dA  = np.sqrt(nxa**2 + nya**2) + _TINY
            n_out_x = nxa / dA
            n_out_y = nya / dA
            U_ext[1:-1, 0] = self._reflect(U_ext[1:-1, 1], n_out_x, n_out_y)
        elif side == "north":
            nxa = mesh.j_nxa[:, -1]
            nya = mesh.j_nya[:, -1]
            dA  = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[1:-1, -1] = self._reflect(U_ext[1:-1, -2], nxa / dA, nya / dA)
        elif side == "west":
            nxa = -mesh.i_nxa[0, :]
            nya = -mesh.i_nya[0, :]
            dA  = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[0, 1:-1] = self._reflect(U_ext[1, 1:-1], nxa / dA, nya / dA)
        elif side == "east":
            nxa = mesh.i_nxa[-1, :]
            nya = mesh.i_nya[-1, :]
            dA  = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[-1, 1:-1] = self._reflect(U_ext[-2, 1:-1], nxa / dA, nya / dA)


class Symmetry(SlipWall):
    """Symmetry plane — identical to slip wall."""
    pass


class Farfield(BoundaryCondition):
    """
    Riemann-invariant farfield BC.

    For subsonic: uses one outgoing + one incoming characteristic.
    For supersonic inflow:  sets all from freestream.
    For supersonic outflow: extrapolates all from interior.

    Parameters
    ----------
    M, p, T, alpha_deg : freestream conditions
    gamma, R_gas       : gas properties
    """

    def __init__(self, M, p, T, alpha_deg=0.0, gamma=1.4, R_gas=287.058):
        self.M    = M
        self.p    = p
        self.T    = T
        self.alpha_deg = alpha_deg
        self.gamma = gamma
        self.R_gas = R_gas
        self._U_fs = BoundaryCondition._freestream_state(
            M, p, T, alpha_deg, gamma, R_gas)

    def _farfield_ghost(self, U_int, n_out_x, n_out_y, gamma, R_gas):
        """Compute ghost state using Riemann invariants at each face."""
        rho_i = U_int[..., RHO]
        u_i   = U_int[..., RHOU] / (rho_i + _TINY)
        v_i   = U_int[..., RHOV] / (rho_i + _TINY)
        p_i   = (gamma - 1.0) * (U_int[..., E]
                                   - 0.5 * rho_i * (u_i**2 + v_i**2))
        p_i   = np.maximum(p_i, _TINY)
        a_i   = np.sqrt(gamma * p_i / (rho_i + _TINY))
        Vn_i  = u_i * n_out_x + v_i * n_out_y

        # Freestream values
        fs = self._U_fs
        rho_fs = fs[RHO]
        u_fs   = fs[RHOU] / rho_fs
        v_fs   = fs[RHOV] / rho_fs
        p_fs   = (gamma - 1.0) * (fs[E] - 0.5 * rho_fs * (u_fs**2 + v_fs**2))
        a_fs   = np.sqrt(gamma * p_fs / rho_fs)
        Vn_fs  = u_fs * n_out_x + v_fs * n_out_y

        # Riemann invariants (characteristic variables along n_out)
        R_plus  = Vn_i  + 2.0 * a_i   / (gamma - 1.0)    # outgoing
        R_minus = Vn_fs - 2.0 * a_fs  / (gamma - 1.0)    # incoming from ∞

        Vn_g = 0.5 * (R_plus + R_minus)
        a_g  = 0.25 * (gamma - 1.0) * (R_plus - R_minus)
        a_g  = np.maximum(a_g, _TINY)

        # Tangential velocity: from interior if outflow, freestream if inflow
        is_outflow = Vn_i >= 0
        Vt_i_x = u_i - Vn_i * n_out_x
        Vt_i_y = v_i - Vn_i * n_out_y
        Vt_fs_x = u_fs - Vn_fs * n_out_x
        Vt_fs_y = v_fs - Vn_fs * n_out_y
        Vt_x = np.where(is_outflow, Vt_i_x, Vt_fs_x)
        Vt_y = np.where(is_outflow, Vt_i_y, Vt_fs_y)

        u_g = Vn_g * n_out_x + Vt_x
        v_g = Vn_g * n_out_y + Vt_y

        # Entropy: from interior (outflow) or freestream (inflow)
        s_i  = p_i  / (rho_i  + _TINY) ** gamma
        s_fs = p_fs / rho_fs ** gamma
        s_g  = np.where(is_outflow, s_i, s_fs)

        rho_g = (a_g**2 / (gamma * s_g + _TINY)) ** (1.0 / (gamma - 1.0))
        p_g   = s_g * rho_g ** gamma
        p_g   = np.maximum(p_g, _TINY)
        E_g   = p_g / (gamma - 1.0) + 0.5 * rho_g * (u_g**2 + v_g**2)

        U_g = np.zeros_like(U_int)
        U_g[..., RHO]  = rho_g
        U_g[..., RHOU] = rho_g * u_g
        U_g[..., RHOV] = rho_g * v_g
        U_g[..., E]    = E_g
        return U_g

    def apply(self, U_ext, mesh, side, gamma, R_gas):
        g = gamma
        if side == "west":
            # Outward normal at west = -i direction = pointing into ghost = (-1, 0) for Cartesian
            nxa = -mesh.i_nxa[0, :]; nya = -mesh.i_nya[0, :]
            dA = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[0, 1:-1] = self._farfield_ghost(
                U_ext[1, 1:-1], nxa / dA, nya / dA, g, R_gas)
        elif side == "east":
            nxa = mesh.i_nxa[-1, :]; nya = mesh.i_nya[-1, :]
            dA = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[-1, 1:-1] = self._farfield_ghost(
                U_ext[-2, 1:-1], nxa / dA, nya / dA, g, R_gas)
        elif side == "south":
            nxa = -mesh.j_nxa[:, 0]; nya = -mesh.j_nya[:, 0]
            dA = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[1:-1, 0] = self._farfield_ghost(
                U_ext[1:-1, 1], nxa / dA, nya / dA, g, R_gas)
        elif side == "north":
            nxa = mesh.j_nxa[:, -1]; nya = mesh.j_nya[:, -1]
            dA = np.sqrt(nxa**2 + nya**2) + _TINY
            U_ext[1:-1, -1] = self._farfield_ghost(
                U_ext[1:-1, -2], nxa / dA, nya / dA, g, R_gas)
