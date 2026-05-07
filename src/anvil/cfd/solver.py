"""
anvil.cfd.solver — CFDSolver: main 2D Euler solver and CFDResult.

Solver overview
---------------
Time marching: explicit 4-stage Runge-Kutta (Jameson's scheme)
    For steady-state: local time stepping (each cell uses its own dt)
    For transient:    global dt from minimum CFL condition

Spatial discretization: cell-centred finite volume
    1st order: piecewise-constant reconstruction (Roe flux on cell averages)
    2nd order: MUSCL + van Leer limiter then Roe flux on reconstructed states

Shock capturing: inherent in Roe flux (upwind dissipation)
Entropy fix:     Harten's scheme prevents sonic expansion shocks

Anvil integration
-----------------
    result = solver.run()          → CFDResult (like System's Result)
    solver.as_relation(...)        → Anvil Relation (scalar Q in, scalar Q out)
    sys.use(solver.as_relation())  → plugs into System.use() / sweep()
    sweep(..., parallel=4)         → each point runs an independent CFDSolver

Convergence history is stored in result.history compatible with the
existing anvil.viz.convergence() plotter.

Extensibility
-------------
Viscous:    add a viscous_flux step inside _residual() after inviscid flux.
            Requires gradient reconstruction at faces (Green-Gauss or LS).
Turbulence: add extra state variables (k, omega) and their equations.
3D:         add k-direction in mesh, w-velocity in state, and a third
            face sweep (w-faces) in _residual().
"""

from __future__ import annotations
import time as _time
import numpy as np
from typing import Optional, Dict

from anvil.cfd.mesh import StructuredMesh2D
from anvil.cfd.flux import roe_flux_2d, hllc_flux_2d, muscl_reconstruct
from anvil.cfd.bc   import BoundaryCondition
from anvil.cfd.io   import write_vtk, write_tecplot, write_restart

# Conservative variable indices
RHO = 0; RHOU = 1; RHOV = 2; E = 3
_TINY    = 1.0e-30
_RHO_MIN = 1.0e-4   # kg/m³ — floor for positivity fix
_P_MIN   = 1.0      # Pa   — floor for positivity fix


# ── Helper: primitive variables ───────────────────────────────────────────────

def _to_prim(U_ext, gamma):
    """Physical cells [1:-1, 1:-1] → (rho, u, v, p, T, M, a) all (nx, ny)."""
    Up = U_ext[1:-1, 1:-1]
    rho = Up[..., RHO]
    u   = Up[..., RHOU] / (rho + _TINY)
    v   = Up[..., RHOV] / (rho + _TINY)
    p   = (gamma - 1.0) * (Up[..., E] - 0.5 * rho * (u**2 + v**2))
    p   = np.maximum(p, _TINY)
    a   = np.sqrt(gamma * p / (rho + _TINY))
    T   = p / ((rho + _TINY) * 287.058)   # default R; solver overrides
    M   = np.sqrt(u**2 + v**2) / (a + _TINY)
    return rho, u, v, p, a, T, M


# ── CFDResult ─────────────────────────────────────────────────────────────────

class CFDResult:
    """
    Solution from CFDSolver.run().

    Attributes
    ----------
    rho, u, v, p, T, M : ndarray (nx, ny)   primitive fields
    U_ext              : ndarray (nx+2, ny+2, 4)  full conservative state
    mesh               : StructuredMesh2D
    converged          : bool
    n_iter             : int    iterations run
    residuals          : list of float   L2 residual per iteration
    history            : list of dicts   compatible with anvil.viz.convergence
    """

    def __init__(self, U_ext, mesh, gamma, R_gas, history, converged, n_iter):
        self.U_ext     = U_ext
        self.mesh      = mesh
        self.gamma     = gamma
        self.R_gas     = R_gas
        self.converged = converged
        self.n_iter    = n_iter
        self.history   = history
        self.residuals = [h["residual"] for h in history]

        # Unpack physical primitives
        Up = U_ext[1:-1, 1:-1]
        rho = Up[..., RHO]
        u   = Up[..., RHOU] / (rho + _TINY)
        v   = Up[..., RHOV] / (rho + _TINY)
        p   = (gamma - 1.0) * (Up[..., E] - 0.5 * rho * (u**2 + v**2))
        p   = np.maximum(p, _TINY)
        a   = np.sqrt(gamma * p / (rho + _TINY))
        T   = p / ((rho + _TINY) * R_gas)
        M   = np.sqrt(u**2 + v**2) / (a + _TINY)

        self.rho = rho
        self.u   = u
        self.v   = v
        self.p   = p
        self.T   = T
        self.M   = M

    # ── Surface / integral post-processing ────────────────────────────────────

    def wall_pressure(self, side="south"):
        """Mean static pressure on a wall boundary."""
        if side == "south":
            return float(self.p[:, 0].mean())
        elif side == "north":
            return float(self.p[:, -1].mean())
        elif side == "west":
            return float(self.p[0, :].mean())
        elif side == "east":
            return float(self.p[-1, :].mean())

    def force_coefficients(self, p_ref, rho_ref, V_ref, S_ref,
                           wall_side="south"):
        """
        Compute lift and drag coefficients from wall pressure integration.

        Pressure force on the wall:
            F = -integral(p * n_out * dA)  [n_out = outward domain normal]
        Lift = F in y-direction (perpendicular to flow)
        Drag = F in x-direction (parallel to flow)

        Parameters
        ----------
        p_ref, rho_ref, V_ref : reference pressure, density, velocity
        S_ref                 : reference area (chord * 1 for 2D per unit span)
        wall_side             : "south", "north", "east", or "west"
        """
        q_ref = 0.5 * rho_ref * V_ref**2
        mesh  = self.mesh

        if wall_side == "south":
            # j-face at J=0 (between ghost j=0 and cell j=1)
            nxa = -mesh.j_nxa[:, 0]   # outward = opposite of face normal
            nya = -mesh.j_nya[:, 0]
            p_wall = (self.U_ext[1:-1, 1][..., RHO] * 0 +
                      np.maximum(
                          (self.gamma - 1.0) * (
                              self.U_ext[1:-1, 1][..., E] -
                              0.5 * self.U_ext[1:-1, 1][..., RHO] *
                              (
                                  (self.U_ext[1:-1,1][...,RHOU] /
                                   (self.U_ext[1:-1,1][...,RHO]+_TINY))**2 +
                                  (self.U_ext[1:-1,1][...,RHOV] /
                                   (self.U_ext[1:-1,1][...,RHO]+_TINY))**2
                              )
                          ), _TINY))
        else:
            raise NotImplementedError(f"wall_side='{wall_side}' not yet implemented")

        # Pressure force components
        Fx = np.sum(p_wall * nxa)
        Fy = np.sum(p_wall * nya)

        CD = Fx / (q_ref * S_ref + _TINY)
        CL = Fy / (q_ref * S_ref + _TINY)
        return float(CL), float(CD)

    # ── Output ────────────────────────────────────────────────────────────────

    def _field_dict(self):
        p0 = self.p * (1 + (self.gamma - 1) / 2 * self.M**2) ** (
            self.gamma / (self.gamma - 1))
        return {
            "rho":   self.rho,
            "u":     self.u,
            "v":     self.v,
            "p":     self.p,
            "T":     self.T,
            "Mach":  self.M,
            "p0":    p0,
        }

    def to_vtk(self, path: str):
        """Write VTK legacy file for ParaView."""
        write_vtk(path, self.mesh, self._field_dict(),
                  title="anvil_cfd_result")
        print(f"  Saved VTK:     {path}")

    def to_tecplot(self, path: str):
        """Write Tecplot ASCII file."""
        write_tecplot(path, self.mesh, self._field_dict(),
                      title="anvil_cfd_result")
        print(f"  Saved Tecplot: {path}")

    def to_restart(self, path: str):
        """Save full state for restart."""
        write_restart(path, self.U_ext, self.n_iter, 0.0)
        print(f"  Saved restart: {path}")

    def summary(self):
        status = "CONVERGED" if self.converged else "NOT CONVERGED"
        print(f"\n{'-'*56}")
        print(f"  CFD Solve — {status}  ({self.n_iter} iterations)")
        print(f"{'-'*56}")
        print(f"  Grid        : {self.mesh.nx} x {self.mesh.ny} cells")
        print(f"  rho  range  : [{self.rho.min():.4f}, {self.rho.max():.4f}] kg/m3")
        print(f"  p    range  : [{self.p.min():.4f}, {self.p.max():.4f}] Pa")
        print(f"  T    range  : [{self.T.min():.2f}, {self.T.max():.2f}] K")
        print(f"  Mach range  : [{self.M.min():.4f}, {self.M.max():.4f}]")
        if self.residuals:
            print(f"  Final res   : {self.residuals[-1]:.4e}")
        print(f"{'-'*56}")

    def _repr_html_(self):
        status = "converged" if self.converged else "NOT CONVERGED"
        color  = "#2e7d32" if self.converged else "#c62828"
        rows = [
            ("Status",      f'<span style="color:{color}">{status}</span>'),
            ("Iterations",  str(self.n_iter)),
            ("Grid",        f"{self.mesh.nx} x {self.mesh.ny}"),
            ("rho [kg/m3]", f"{self.rho.min():.4f} … {self.rho.max():.4f}"),
            ("p [Pa]",      f"{self.p.min():.4g} … {self.p.max():.4g}"),
            ("T [K]",       f"{self.T.min():.2f} … {self.T.max():.2f}"),
            ("Mach",        f"{self.M.min():.4f} … {self.M.max():.4f}"),
            ("Final residual", f"{self.residuals[-1]:.4e}" if self.residuals else "—"),
        ]
        body = "".join(
            f'<tr><td style="padding:3px 12px;font-weight:bold">{k}</td>'
            f'<td style="padding:3px 12px;font-family:monospace">{v}</td></tr>'
            for k, v in rows
        )
        return (
            f'<div style="font-family:sans-serif">'
            f'<b>CFDResult</b>'
            f'<table style="border-collapse:collapse;font-size:.9em;margin-top:6px">'
            f'{body}</table></div>'
        )


# ── CFDSolver ─────────────────────────────────────────────────────────────────

class CFDSolver:
    """
    2D Euler finite volume solver.

    Parameters
    ----------
    mesh : StructuredMesh2D
    bcs  : dict
        Mapping of side name to BoundaryCondition object.
        Side names: "west", "east", "south", "north".
        All four sides must be specified.
    gamma : float
        Ratio of specific heats (default 1.4 for air).
    R_gas : float
        Specific gas constant in J/kg/K (default 287.058 for air).
    flux_scheme : str
        "roe" (default) or "hllc".
    order : int
        Spatial order: 1 (piecewise constant) or 2 (MUSCL van Leer).
    time_scheme : str
        "rk4"  — 4-stage Runge-Kutta (recommended)
        "euler"— explicit Euler (1st order in time, for debugging)
    cfl : float
        CFL number for local time-step computation (default 0.5).
        Reduce to 0.3 for difficult transonic/supersonic cases.
    transient : bool
        False (default) = local time stepping for steady-state convergence.
        True = global dt for time-accurate transient simulation.
    U0_ext : ndarray, optional
        Initial extended state (nx+2, ny+2, 4) for restart.
        If None, call initialize() before run().

    Usage
    -----
    mesh   = Mesh.wedge(half_angle_deg=10, chord=1.0, height=0.8, nx=80, ny=40)
    bcs    = {"west":  SupersonicInlet(M=2.0, p=101325, T=300),
              "east":  SupersonicOutlet(),
              "south": SlipWall(),
              "north": Farfield(M=2.0, p=101325, T=300)}
    solver = CFDSolver(mesh, bcs, gamma=1.4)
    solver.initialize(M=2.0, p=101325, T=300, alpha_deg=0.0)
    result = solver.run(max_iter=3000, tol=1e-6, monitor=True)
    result.to_vtk("wedge.vtk")

    # Integrate with Anvil System:
    rel = solver.as_relation(inputs=["M_inf", "p_inf", "T_inf"],
                             outputs=["CL", "CD", "M_max", "p_wall"])
    sys.use(rel)
    sweep = sys.sweep("M_inf", [1.5, 2.0, 2.5, 3.0], parallel=4)
    """

    def __init__(self, mesh: StructuredMesh2D,
                 bcs: Dict[str, BoundaryCondition],
                 gamma: float = 1.4,
                 R_gas: float = 287.058,
                 flux_scheme: str = "roe",
                 order: int = 2,
                 time_scheme: str = "rk4",
                 cfl: float = 0.5,
                 transient: bool = False,
                 U0_ext=None):
        self.mesh        = mesh
        self.bcs         = bcs
        self.gamma       = float(gamma)
        self.R_gas       = float(R_gas)
        self.order       = int(order)
        self.time_scheme = time_scheme
        self.cfl         = float(cfl)
        self.transient   = bool(transient)

        # Select flux function
        if flux_scheme == "roe":
            self._flux_fn = roe_flux_2d
        elif flux_scheme == "hllc":
            self._flux_fn = hllc_flux_2d
        else:
            raise ValueError(f"flux_scheme must be 'roe' or 'hllc', got '{flux_scheme}'")

        nx, ny = mesh.nx, mesh.ny
        if U0_ext is not None:
            self._U_ext = np.asarray(U0_ext, dtype=np.float64)
        else:
            self._U_ext = np.zeros((nx + 2, ny + 2, 4), dtype=np.float64)

    def initialize(self, M: float, p: float, T: float, alpha_deg: float = 0.0):
        """Fill the entire domain (including ghost cells) with uniform freestream."""
        gamma, R = self.gamma, self.R_gas
        alpha = np.radians(alpha_deg)
        a     = np.sqrt(gamma * R * T)
        V     = M * a
        u     = V * np.cos(alpha)
        v     = V * np.sin(alpha)
        rho   = p / (R * T)
        E_tot = p / (gamma - 1.0) + 0.5 * rho * (u**2 + v**2)
        self._U_ext[..., RHO]  = rho
        self._U_ext[..., RHOU] = rho * u
        self._U_ext[..., RHOV] = rho * v
        self._U_ext[..., E]    = E_tot

    # ── Apply all boundary conditions ─────────────────────────────────────────

    def _apply_bcs(self, U_ext):
        mesh = self.mesh
        for patch_name, bc in self.bcs.items():
            patch = mesh.patches.get(patch_name)
            if patch is None:
                continue
            s, e, side = patch.start, patch.end, patch.side

            if side == "west":
                U_g  = U_ext[0,  s+1:e+1, :]
                U_i  = U_ext[1,  s+1:e+1, :]
                nxa  = -mesh.i_nxa[0,  s:e]
                nya  = -mesh.i_nya[0,  s:e]
            elif side == "east":
                U_g  = U_ext[-1, s+1:e+1, :]
                U_i  = U_ext[-2, s+1:e+1, :]
                nxa  =  mesh.i_nxa[-1, s:e]
                nya  =  mesh.i_nya[-1, s:e]
            elif side == "south":
                U_g  = U_ext[s+1:e+1, 0,  :]
                U_i  = U_ext[s+1:e+1, 1,  :]
                nxa  = -mesh.j_nxa[s:e, 0]
                nya  = -mesh.j_nya[s:e, 0]
            elif side == "north":
                U_g  = U_ext[s+1:e+1, -1, :]
                U_i  = U_ext[s+1:e+1, -2, :]
                nxa  =  mesh.j_nxa[s:e, -1]
                nya  =  mesh.j_nya[s:e, -1]
            else:
                continue

            dA   = np.sqrt(nxa**2 + nya**2) + _TINY
            bc.apply(U_g, U_i, nxa / dA, nya / dA, self.gamma, self.R_gas)

    # ── Compute residual (spatial operator) ───────────────────────────────────

    def _residual(self, U_ext):
        """
        Compute dU/dt = -R(U) for physical cells.
        Returns array shape (nx, ny, 4): net flux divergence per unit volume.

        i-faces: between extended column I and I+1 for I=0..nx  → shape (nx+1, ny)
        j-faces: between extended row    J and J+1 for J=0..ny  → shape (nx, ny+1)
        """
        flux_fn = self._flux_fn
        order   = self.order
        gamma   = self.gamma

        # ── i-direction: (nx+1) faces, each spanning ny cells ───────────────
        # 1st-order states at each face (piecewise constant)
        UL_i_1st = U_ext[:-1, 1:-1]    # shape (nx+1, ny, 4) — left  of face
        UR_i_1st = U_ext[1:,  1:-1]    # shape (nx+1, ny, 4) — cells 1..nx+1

        if order == 1:
            UL_i_all = UL_i_1st
            UR_i_all = UR_i_1st
        else:
            # MUSCL: for each i-face I, use cells I-1, I, I+1, I+2
            # i-face I is between U_ext[I,:] and U_ext[I+1,:]
            # Need I-1 and I+2 for MUSCL slopes
            # I ranges from 0 to nx (nx+1 faces)
            # U_ext has shape (nx+2, ny+2), indices 0..nx+1
            # For I=0: need U_ext[-1] (doesn't exist) → use 1st order at boundaries
            # Simple fix: 2nd order only for I=1..nx-1, 1st order at I=0 and I=nx
            im1 = U_ext[:-3, 1:-1]   # (nx-1, ny, 4) for faces 1..nx-1
            i0  = U_ext[1:-2, 1:-1]  # left  cell
            ip1 = U_ext[2:-1, 1:-1]  # right cell
            ip2 = U_ext[3:,   1:-1]  # (nx-1, ny, 4)

            dL = i0  - im1
            dC = ip1 - i0
            dR = ip2 - ip1

            # r = backward/forward ratio; preserve sign of denominator
            dC_si = dC + np.where(dC >= 0, _TINY, -_TINY)
            rL = dL / dC_si
            rR = dR / dC_si
            phiL = (rL + np.abs(rL)) / (1.0 + np.abs(rL) + _TINY)
            phiR = (rR + np.abs(rR)) / (1.0 + np.abs(rR) + _TINY)

            UL_mid = i0  + 0.5 * phiL * dC
            UR_mid = ip1 - 0.5 * phiR * dC

            # Assemble: boundary faces use 1st order, interior use MUSCL
            UL_i_all = np.concatenate([
                UL_i_1st[:1],      # face 0: 1st order
                UL_mid,            # faces 1..nx-1: MUSCL
                UL_i_1st[-1:],     # face nx: 1st order
            ], axis=0)
            UR_i_all = np.concatenate([
                UR_i_1st[:1],
                UR_mid,
                UR_i_1st[-1:],
            ], axis=0)

        F_i = flux_fn(UL_i_all, UR_i_all, self.mesh.i_nxa, self.mesh.i_nya, gamma)
        # F_i: shape (nx+1, ny, 4)

        # ── j-direction flux ────────────────────────────────────────────────
        UL_j_1st = U_ext[1:-1, :-1]    # shape (nx, ny+1, 4)
        UR_j_1st = U_ext[1:-1, 1:]     # shape (nx, ny+1, 4)

        if order == 1:
            UL_j_all = UL_j_1st
            UR_j_all = UR_j_1st
        else:
            jm1 = U_ext[1:-1, :-3]
            j0  = U_ext[1:-1, 1:-2]
            jp1 = U_ext[1:-1, 2:-1]
            jp2 = U_ext[1:-1, 3:]

            dL = j0  - jm1
            dC = jp1 - j0
            dR = jp2 - jp1

            dC_sj = dC + np.where(dC >= 0, _TINY, -_TINY)
            rL = dL / dC_sj
            rR = dR / dC_sj
            phiL = (rL + np.abs(rL)) / (1.0 + np.abs(rL) + _TINY)
            phiR = (rR + np.abs(rR)) / (1.0 + np.abs(rR) + _TINY)

            UL_mid_j = j0  + 0.5 * phiL * dC
            UR_mid_j = jp1 - 0.5 * phiR * dC

            UL_j_all = np.concatenate([
                UL_j_1st[:, :1],
                UL_mid_j,
                UL_j_1st[:, -1:],
            ], axis=1)
            UR_j_all = np.concatenate([
                UR_j_1st[:, :1],
                UR_mid_j,
                UR_j_1st[:, -1:],
            ], axis=1)

        F_j = flux_fn(UL_j_all, UR_j_all, self.mesh.j_nxa, self.mesh.j_nya, gamma)
        # F_j: shape (nx, ny+1, 4)

        # ── Net flux divergence per cell ─────────────────────────────────────
        # dU/dt = -(1/vol) * (F_i[i+1] - F_i[i] + F_j[j+1] - F_j[j])
        dF  = (F_i[1:, :, :] - F_i[:-1, :, :]    # (nx, ny, 4) i-contribution
             + F_j[:, 1:, :] - F_j[:, :-1, :])   # (nx, ny, 4) j-contribution
        R   = dF / self.mesh.vol[..., np.newaxis]  # (nx, ny, 4)
        return R

    # ── Time step computation ─────────────────────────────────────────────────

    def _compute_dt(self, U_ext):
        """
        Local time step for each cell based on CFL condition.
        Returns dt_field: shape (nx, ny).
        For transient (global) mode: returns the minimum dt as a scalar.
        """
        Up = U_ext[1:-1, 1:-1]
        rho = Up[..., RHO]
        u   = Up[..., RHOU] / (rho + _TINY)
        v   = Up[..., RHOV] / (rho + _TINY)
        p   = (self.gamma - 1.0) * (Up[..., E] - 0.5 * rho * (u**2 + v**2))
        p   = np.maximum(p, _TINY)
        a   = np.sqrt(self.gamma * p / (rho + _TINY))

        # Spectral radii per cell face direction
        lam_i = (np.abs(u) + a) * (self.mesh.i_area[1:, :] + self.mesh.i_area[:-1, :]) / 2.0
        lam_j = (np.abs(v) + a) * (self.mesh.j_area[:, 1:] + self.mesh.j_area[:, :-1]) / 2.0

        dt = self.cfl * self.mesh.vol / (lam_i + lam_j + _TINY)

        if self.transient:
            return float(dt.min())
        return dt

    # ── Positivity fix ────────────────────────────────────────────────────────

    def _positivity_clamp(self, U_ext):
        """Clamp interior cells to physically valid states (rho > 0, p > 0)."""
        U = U_ext[1:-1, 1:-1]
        np.clip(U[..., RHO], _RHO_MIN, None, out=U[..., RHO])
        u   = U[..., RHOU] / U[..., RHO]
        v   = U[..., RHOV] / U[..., RHO]
        p   = (self.gamma - 1.0) * (U[..., E] - 0.5 * U[..., RHO] * (u**2 + v**2))
        bad = p < _P_MIN
        if bad.any():
            U[..., E][bad] = (_P_MIN / (self.gamma - 1.0)
                              + 0.5 * U[..., RHO][bad] * (u[bad]**2 + v[bad]**2))

    # ── RK4 step ──────────────────────────────────────────────────────────────

    def _rk4_step(self, U_ext):
        """One 4-stage Runge-Kutta iteration."""
        dt_field = self._compute_dt(U_ext)

        def update(U, R, alpha):
            U_new = U_ext.copy()
            U_new[1:-1, 1:-1] = U[1:-1, 1:-1] - alpha * dt_field[..., np.newaxis] * R
            self._positivity_clamp(U_new)
            return U_new

        # Stage 1
        U1 = update(U_ext, self._residual_with_bc(U_ext), 0.25)
        # Stage 2
        U2 = update(U_ext, self._residual_with_bc(U1), 1.0 / 3.0)
        # Stage 3
        U3 = update(U_ext, self._residual_with_bc(U2), 0.5)
        # Stage 4
        R4 = self._residual_with_bc(U3)
        U_ext[1:-1, 1:-1] -= dt_field[..., np.newaxis] * R4
        self._positivity_clamp(U_ext)
        return U_ext

    def _euler_step(self, U_ext):
        """One explicit Euler step."""
        dt_field = self._compute_dt(U_ext)
        R = self._residual_with_bc(U_ext)
        U_ext[1:-1, 1:-1] -= dt_field[..., np.newaxis] * R
        self._positivity_clamp(U_ext)
        return U_ext

    def _residual_with_bc(self, U_ext):
        """Apply BCs then compute residual."""
        self._apply_bcs(U_ext)
        return self._residual(U_ext)

    # ── L2 residual ───────────────────────────────────────────────────────────

    @staticmethod
    def _l2_residual(R):
        """L2 norm of residual vector (density equation only for convergence monitor)."""
        return float(np.sqrt(np.mean(R[..., RHO]**2)))

    # ── Main solve loop ───────────────────────────────────────────────────────

    def run(self, max_iter: int = 5000, tol: float = 1e-6,
            monitor: bool = True, verbose: bool = True,
            print_every: int = 100,
            restart_every: int = 0,
            restart_prefix: str = "restart",
            save_every: int = 0,
            save_field: str = "p",
            save_dir: str = ".",
            save_vmin=None,
            save_vmax=None) -> CFDResult:
        """
        Run the solver until convergence or max_iter.

        Parameters
        ----------
        max_iter     : int     maximum number of iterations
        tol          : float   convergence tolerance on L2 density residual
        monitor      : bool    store iteration history (compatible with anvil.viz)
        verbose      : bool    print residual to stdout
        print_every  : int     print interval
        restart_every: int     0 = disabled; N = save restart every N iters
        restart_prefix: str    prefix for restart files
        save_every   : int     0 = disabled; N = save PNG contour every N iters
        save_field   : str     field to save ("p", "M", "rho", "T", "u", "v")
        save_dir     : str     directory for saved PNG files

        Returns
        -------
        CFDResult
        """
        U_ext   = self._U_ext.copy()
        history = []
        converged = False
        res0 = None
        t0   = _time.monotonic()

        step_fn = self._rk4_step if self.time_scheme == "rk4" else self._euler_step

        for it in range(max_iter):
            self._apply_bcs(U_ext)
            R   = self._residual(U_ext)
            res = self._l2_residual(R)

            if res0 is None:
                res0 = max(res, _TINY)

            elapsed = _time.monotonic() - t0

            if monitor:
                history.append({
                    "iteration": it,
                    "residual":  res,
                    "wallclock": elapsed,
                    "variables": {"residual": res, "res_norm": res / res0},
                })

            if verbose and (it % print_every == 0 or it < 5):
                print(f"  iter {it:5d}  |  res = {res:.4e}"
                      f"  |  res/res0 = {res/res0:.4e}"
                      f"  |  t = {elapsed:.1f}s")

            if res / res0 < tol or res < tol * 1e-3:
                converged = True
                if verbose:
                    print(f"  Converged at iter {it}: res = {res:.4e}")
                break

            # Time march
            U_ext = step_fn(U_ext)

            # Restart checkpoint
            if restart_every > 0 and (it + 1) % restart_every == 0:
                write_restart(f"{restart_prefix}_{it+1:05d}.npz",
                              U_ext, it + 1, 0.0)

            # PNG snapshot
            if save_every > 0 and (it + 1) % save_every == 0:
                import os as _os
                from anvil.cfd.viz import save_png as _save_png
                _os.makedirs(save_dir, exist_ok=True)
                snap = CFDResult(U_ext, self.mesh, self.gamma, self.R_gas,
                                 [], False, it + 1)
                _save_png(snap, save_field,
                          _os.path.join(save_dir,
                                        f"{save_field}_{it+1:05d}.png"),
                          vmin=save_vmin, vmax=save_vmax,
                          title=f"iter {it+1}  res={res:.3e}")

        self._U_ext = U_ext
        return CFDResult(U_ext, self.mesh, self.gamma, self.R_gas,
                         history, converged, it + 1)

    # ── Anvil Relation interface ───────────────────────────────────────────────

    def as_relation(self, inputs=None, outputs=None, name="cfd_solver",
                    bc_factory=None, run_kwargs=None):
        """
        Wrap this CFDSolver as an Anvil Relation for use in System.use().

        The returned Relation:
            - Accepts scalar Quantity inputs (M_inf, p_inf, T_inf, alpha_deg, ...)
            - Calls self.run() with those parameters
            - Returns scalar Quantity outputs (CL, CD, M_max, p_wall, ...)
            - Is compatible with System.sweep(parallel=N)

        Parameters
        ----------
        inputs  : list of str, e.g. ["M_inf", "p_inf", "T_inf", "alpha_deg"]
        outputs : list of str, e.g. ["CL", "CD", "M_max", "p_wall"]
        name    : str  Relation name for display
        bc_factory : callable(M_inf, p_inf, T_inf, alpha_deg) -> dict
            Factory to build fresh BCs for each evaluation — required when
            inputs include M_inf / p_inf / T_inf so BCs use the correct
            freestream. If None, the solver's existing BCs are reused (only
            correct when BCs don't depend on freestream conditions).
        run_kwargs : dict, optional
            Keyword arguments forwarded to solver.run() — e.g.
            {"max_iter": 1000, "tol": 1e-4, "verbose": False}.
        """
        from anvil.relation import Relation
        from anvil.quantity import Q

        _inputs     = inputs  or ["M_inf", "p_inf", "T_inf", "alpha_deg"]
        _outputs    = outputs or ["CL", "CD", "M_max", "p_wall"]
        _gamma      = self.gamma
        _R_gas      = self.R_gas
        _mesh       = self.mesh
        _bcs_static = self.bcs      # used only when bc_factory is None
        _order      = self.order
        _flux       = "roe"
        _cfl        = self.cfl
        _transient  = self.transient
        _bc_factory = bc_factory
        _run_kw     = dict(max_iter=3000, tol=1e-5, verbose=False, monitor=False)
        if run_kwargs:
            _run_kw.update(run_kwargs)

        def _fn(**kwargs):
            # Unpack Quantity or float inputs
            def _si(v):
                return float(v._si_value) if hasattr(v, '_si_value') else float(v)

            M_inf     = _si(kwargs.get("M_inf",     2.0))
            p_inf     = _si(kwargs.get("p_inf",     101325.0))
            T_inf     = _si(kwargs.get("T_inf",     300.0))
            alpha_deg = _si(kwargs.get("alpha_deg", 0.0))

            bcs = (_bc_factory(M_inf, p_inf, T_inf, alpha_deg)
                   if _bc_factory is not None else _bcs_static)

            # Build and run solver
            solver = CFDSolver(_mesh, bcs, gamma=_gamma, R_gas=_R_gas,
                               flux_scheme=_flux, order=_order,
                               cfl=_cfl, transient=_transient)
            solver.initialize(M_inf, p_inf, T_inf, alpha_deg)
            result = solver.run(**_run_kw)

            # Compute requested outputs
            rho_ref = p_inf / (_R_gas * T_inf)
            V_ref   = M_inf * np.sqrt(_gamma * _R_gas * T_inf)
            q_ref   = 0.5 * rho_ref * V_ref**2

            out = {}
            for key in _outputs:
                if key == "M_max":
                    out[key] = Q(float(result.M.max()), "")
                elif key == "M_min":
                    out[key] = Q(float(result.M.min()), "")
                elif key == "p_wall":
                    out[key] = Q(result.wall_pressure("south"), "Pa")
                elif key in ("CL", "CD"):
                    # Rough chord estimate from mesh
                    chord = _mesh.X[-1, 0] - _mesh.X[0, 0]
                    CL, CD = result.force_coefficients(
                        p_inf, rho_ref, V_ref, S_ref=chord)
                    out["CL"] = Q(CL, "")
                    out["CD"] = Q(CD, "")
                elif key == "rho_max":
                    out[key] = Q(float(result.rho.max()), "kg/m^3")
                elif key == "T_max":
                    out[key] = Q(float(result.T.max()), "K")
                elif key == "p_max":
                    out[key] = Q(float(result.p.max()), "Pa")

            return {k: out[k] for k in _outputs if k in out}

        rel = Relation(name=name)
        rel.func    = _fn
        rel._inputs  = _inputs
        rel._outputs = _outputs
        rel._defaults = {}
        return rel
