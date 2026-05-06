"""
anvil.cfd.mesh — Structured 2D mesh generation and geometry.

Cell-centred finite volume layout (ghost-cell approach):
    Physical cells: (nx, ny) — index (i, j), i=0..nx-1, j=0..ny-1
    Extended array (with ghost ring): shape (nx+2, ny+2)
    Ghost cells: index 0 and nx+1 in i; 0 and ny+1 in j

Face data (normals scaled by face area):
    i-faces (between cell columns): shape (nx+1, ny)
        face I is between physical cells i=I-1 and i=I
    j-faces (between cell rows):    shape (nx, ny+1)
        face J is between physical cells j=J-1 and j=J

Convention: face normal points from lower index to higher index.
    i-face: from cell (i,j) toward cell (i+1,j)  → outward at east boundary
    j-face: from cell (i,j) toward cell (i,j+1)  → outward at north boundary

Extensibility note:
    For 3D, add k-dimension and w-faces (shape nx,ny,nz+1).
    The solver loop pattern is identical; only an extra face direction is added.
"""

from __future__ import annotations
import numpy as np


class StructuredMesh2D:
    """
    2D structured body-fitted mesh for finite volume CFD.

    Parameters
    ----------
    X, Y : ndarray, shape (nx+1, ny+1)
        Node (vertex) coordinates.  X[i,j] = x-coord of node (i,j).

    Geometry attributes
    -------------------
    nx, ny      : physical cell counts
    xc, yc      : cell centres,  shape (nx, ny)
    vol         : cell areas,    shape (nx, ny)
    i_nxa, i_nya: i-face (n*dA), shape (nx+1, ny)   [n points +x for Cartesian]
    i_area      : i-face lengths, shape (nx+1, ny)
    j_nxa, j_nya: j-face (n*dA), shape (nx, ny+1)
    j_area      : j-face lengths, shape (nx, ny+1)
    """

    def __init__(self, X: np.ndarray, Y: np.ndarray):
        assert X.shape == Y.shape and X.ndim == 2
        self.X = np.asarray(X, dtype=np.float64)
        self.Y = np.asarray(Y, dtype=np.float64)
        self.nx = X.shape[0] - 1
        self.ny = X.shape[1] - 1
        self._compute_geometry()

    def _compute_geometry(self):
        X, Y = self.X, self.Y
        nx, ny = self.nx, self.ny

        # ── Cell centres ───────────────────────────────────────────────────────
        self.xc = 0.25 * (X[:-1, :-1] + X[1:, :-1] + X[:-1, 1:] + X[1:, 1:])
        self.yc = 0.25 * (Y[:-1, :-1] + Y[1:, :-1] + Y[:-1, 1:] + Y[1:, 1:])

        # ── Cell volumes (areas in 2D) via shoelace on each quadrilateral ──────
        d1x = X[1:, 1:] - X[:-1, :-1]
        d1y = Y[1:, 1:] - Y[:-1, :-1]
        d2x = X[1:, :-1] - X[:-1, 1:]
        d2y = Y[1:, :-1] - Y[:-1, 1:]
        self.vol = 0.5 * np.abs(d1x * d2y - d1y * d2x)   # shape (nx, ny)

        # ── i-face geometry: face between column i and column i+1 ─────────────
        # Face at column I connects nodes (I, j) → (I, j+1) for j=0..ny-1.
        # dX = X[I, j+1] - X[I, j],  dY = Y[I, j+1] - Y[I, j]
        # Normal (from cell i=I-1 toward i=I, i.e., +x for Cartesian):
        #   n*area = (dY, -dX)
        dxi = X[:, 1:] - X[:, :-1]     # (nx+1, ny)
        dyi = Y[:, 1:] - Y[:, :-1]     # (nx+1, ny)
        self.i_nxa  =  dyi               # nx * area
        self.i_nya  = -dxi               # ny * area
        self.i_area = np.sqrt(dxi**2 + dyi**2)

        # ── j-face geometry: face between row j and row j+1 ───────────────────
        # Face at row J connects nodes (i, J) → (i+1, J) for i=0..nx-1.
        # dX = X[i+1, J] - X[i, J],  dY = Y[i+1, J] - Y[i, J]
        # Normal (from cell j=J-1 toward j=J, i.e., +y for Cartesian):
        #   n*area = (-dY, dX)
        dxj = X[1:, :] - X[:-1, :]     # (nx, ny+1)
        dyj = Y[1:, :] - Y[:-1, :]     # (nx, ny+1)
        self.j_nxa  = -dyj               # nx * area
        self.j_nya  =  dxj               # ny * area
        self.j_area = np.sqrt(dxj**2 + dyj**2)

    # ── Named constructors ─────────────────────────────────────────────────────

    @classmethod
    def cartesian(cls, x_span, y_span, nx: int, ny: int) -> "StructuredMesh2D":
        """
        Uniform Cartesian mesh.

        Parameters
        ----------
        x_span : (x_lo, x_hi)
        y_span : (y_lo, y_hi)
        nx, ny : cell counts
        """
        x = np.linspace(x_span[0], x_span[1], nx + 1)
        y = np.linspace(y_span[0], y_span[1], ny + 1)
        X, Y = np.meshgrid(x, y, indexing='ij')
        return cls(X, Y)

    @classmethod
    def wedge(cls, half_angle_deg: float, chord: float, height: float,
              nx: int, ny: int, x_start: float = 0.0) -> "StructuredMesh2D":
        """
        Body-fitted algebraic mesh for a 2D wedge (flat-bottom ramp).

        The wedge lower surface rises at angle half_angle_deg from x_start.
        Upper boundary is offset by `height` normal to the wedge direction.
        Grid lines in i-direction are vertical (constant x); j-direction
        lines go from the wedge surface to the upper boundary.

        Parameters
        ----------
        half_angle_deg : float  wedge half-angle (degrees)
        chord          : float  wedge chord length
        height         : float  domain height above wedge surface
        nx, ny         : int    cell counts
        x_start        : float  x-coordinate where wedge begins
        """
        theta = np.radians(half_angle_deg)
        x_nodes = np.linspace(x_start, x_start + chord, nx + 1)
        t_nodes = np.linspace(0.0, 1.0, ny + 1)

        X = np.zeros((nx + 1, ny + 1))
        Y = np.zeros((nx + 1, ny + 1))
        for i, xi in enumerate(x_nodes):
            y_wall = max(xi - x_start, 0.0) * np.tan(theta)
            for j, tj in enumerate(t_nodes):
                X[i, j] = xi
                Y[i, j] = y_wall + tj * height
        return cls(X, Y)

    @classmethod
    def from_arrays(cls, X, Y) -> "StructuredMesh2D":
        """Create from user-supplied node-coordinate arrays."""
        return cls(np.asarray(X, dtype=np.float64),
                   np.asarray(Y, dtype=np.float64))

    def info(self):
        dx_mean = (self.X[-1, 0] - self.X[0, 0]) / self.nx
        dy_mean = (self.Y[0, -1] - self.Y[0, 0]) / self.ny
        ar = (self.vol.max() / self.vol.min()) if self.vol.min() > 0 else float('inf')
        print(f"  Mesh: {self.nx} x {self.ny} cells")
        print(f"  x: [{self.X.min():.4g}, {self.X.max():.4g}]  "
              f"y: [{self.Y.min():.4g}, {self.Y.max():.4g}]")
        print(f"  Mean dx={dx_mean:.4g}  dy={dy_mean:.4g}")
        print(f"  Cell area ratio (max/min): {ar:.2f}")
