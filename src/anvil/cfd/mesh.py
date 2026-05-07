"""
anvil.cfd.mesh — Structured 2D mesh generation, file I/O, and geometry.

Named boundary patches allow arbitrary sub-divisions of the four sides so BCs
can be applied to named regions (e.g. "inlet", "wall", "ramp") rather than
the generic cardinal names.

File format  (.amesh)
---------------------
    # Anvil CFD Mesh v1
    TYPE structured
    NX 80
    NY 40
    PATCH inlet    west
    PATCH outlet   east
    PATCH wall     south 0:60
    PATCH ramp     south 60:80
    PATCH farfield north
    NODES
    x00 y00
    x10 y00
    ...  # (NX+1)*(NY+1) lines, i varies fastest

Extensibility
-------------
For 3D: add k-dimension; node array becomes (nx+1,ny+1,nz+1); add k-faces.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class MeshPatch:
    """Named boundary patch — a contiguous sub-range of one domain side.

    Parameters
    ----------
    side  : "west" | "east" | "south" | "north"
    start : first cell index along the boundary (0-based, inclusive)
    end   : last  cell index along the boundary (exclusive)
            west/east → j-cell range [0, ny)
            south/north → i-cell range [0, nx)
    """
    side:  str
    start: int
    end:   int


def _default_patches(nx: int, ny: int) -> Dict[str, MeshPatch]:
    return {
        "west":  MeshPatch("west",  0, ny),
        "east":  MeshPatch("east",  0, ny),
        "south": MeshPatch("south", 0, nx),
        "north": MeshPatch("north", 0, nx),
    }


class StructuredMesh2D:
    """
    2D structured body-fitted mesh for finite volume CFD.

    Parameters
    ----------
    X, Y    : ndarray, shape (nx+1, ny+1)  — node coordinates
    patches : dict of name → MeshPatch, optional
              If None, defaults to full-side patches named
              "west", "east", "south", "north".
    """

    def __init__(self, X: np.ndarray, Y: np.ndarray,
                 patches: Optional[Dict[str, MeshPatch]] = None):
        assert X.shape == Y.shape and X.ndim == 2
        self.X = np.asarray(X, dtype=np.float64)
        self.Y = np.asarray(Y, dtype=np.float64)
        self.nx = X.shape[0] - 1
        self.ny = X.shape[1] - 1
        self.patches = patches if patches is not None else _default_patches(self.nx, self.ny)
        self._compute_geometry()

    def _compute_geometry(self):
        X, Y = self.X, self.Y

        # Cell centres
        self.xc = 0.25 * (X[:-1, :-1] + X[1:, :-1] + X[:-1, 1:] + X[1:, 1:])
        self.yc = 0.25 * (Y[:-1, :-1] + Y[1:, :-1] + Y[:-1, 1:] + Y[1:, 1:])

        # Cell volumes (areas) via diagonal cross-product on each quad
        d1x = X[1:, 1:] - X[:-1, :-1]
        d1y = Y[1:, 1:] - Y[:-1, :-1]
        d2x = X[1:, :-1] - X[:-1, 1:]
        d2y = Y[1:, :-1] - Y[:-1, 1:]
        self.vol = 0.5 * np.abs(d1x * d2y - d1y * d2x)

        # i-face geometry: normal points from cell (i-1,j) → (i,j) (+x for Cartesian)
        dxi = X[:, 1:] - X[:, :-1]    # (nx+1, ny)
        dyi = Y[:, 1:] - Y[:, :-1]
        self.i_nxa  =  dyi
        self.i_nya  = -dxi
        self.i_area = np.sqrt(dxi**2 + dyi**2)

        # j-face geometry: normal points from cell (i,j-1) → (i,j) (+y for Cartesian)
        dxj = X[1:, :] - X[:-1, :]    # (nx, ny+1)
        dyj = Y[1:, :] - Y[:-1, :]
        self.j_nxa  = -dyj
        self.j_nya  =  dxj
        self.j_area = np.sqrt(dxj**2 + dyj**2)

    # ── Named constructors ─────────────────────────────────────────────────────

    @classmethod
    def cartesian(cls, x_span, y_span, nx: int, ny: int,
                  patches=None) -> "StructuredMesh2D":
        """Uniform Cartesian mesh."""
        x = np.linspace(x_span[0], x_span[1], nx + 1)
        y = np.linspace(y_span[0], y_span[1], ny + 1)
        X, Y = np.meshgrid(x, y, indexing='ij')
        return cls(X, Y, patches)

    @classmethod
    def wedge(cls, half_angle_deg: float, chord: float, height: float,
              nx: int, ny: int, x_start: float = 0.0,
              patches=None) -> "StructuredMesh2D":
        """Body-fitted mesh for a 2D wedge (flat-bottom ramp)."""
        theta   = np.radians(half_angle_deg)
        x_nodes = np.linspace(x_start, x_start + chord, nx + 1)
        t_nodes = np.linspace(0.0, 1.0, ny + 1)
        X = np.zeros((nx + 1, ny + 1))
        Y = np.zeros((nx + 1, ny + 1))
        for i, xi in enumerate(x_nodes):
            y_wall = max(xi - x_start, 0.0) * np.tan(theta)
            for j, tj in enumerate(t_nodes):
                X[i, j] = xi
                Y[i, j] = y_wall + tj * height
        return cls(X, Y, patches)

    @classmethod
    def bump(cls, length: float, height: float, nx: int, ny: int,
             bump_height: float = 0.1, bump_x0: float = None,
             bump_sigma: float = None, patches=None) -> "StructuredMesh2D":
        """
        Channel mesh with a Gaussian bump on the lower wall.

        Parameters
        ----------
        length, height  : domain extent in x and y
        bump_height     : peak bump height above y=0
        bump_x0         : bump centre x (default: length/2)
        bump_sigma      : bump half-width (default: length/10)
        """
        if bump_x0 is None:
            bump_x0 = length * 0.5
        if bump_sigma is None:
            bump_sigma = length * 0.1

        x_nodes = np.linspace(0.0, length, nx + 1)
        t_nodes = np.linspace(0.0, 1.0, ny + 1)
        X = np.zeros((nx + 1, ny + 1))
        Y = np.zeros((nx + 1, ny + 1))
        for i, xi in enumerate(x_nodes):
            y_wall = bump_height * np.exp(-0.5 * ((xi - bump_x0) / bump_sigma) ** 2)
            for j, tj in enumerate(t_nodes):
                X[i, j] = xi
                Y[i, j] = y_wall + tj * (height - y_wall)
        return cls(X, Y, patches)

    @classmethod
    def compression_ramp(cls, length: float, height: float,
                         ramp_x0: float, ramp_angle_deg: float,
                         nx: int, ny: int,
                         smooth_width: float = None,
                         patches=None) -> "StructuredMesh2D":
        """
        Channel mesh with a compression ramp on the lower wall.

        The lower wall rises smoothly from y=0 (x < ramp_x0) at
        ramp_angle_deg via a tanh transition (avoids mesh kinks).

        Parameters
        ----------
        length, height   : domain size
        ramp_x0          : ramp start x-coordinate
        ramp_angle_deg   : ramp angle (degrees)
        smooth_width     : transition width (default length/20)
        """
        if smooth_width is None:
            smooth_width = length / 20.0
        theta = np.radians(ramp_angle_deg)
        rise_per_x = np.tan(theta)

        x_nodes = np.linspace(0.0, length, nx + 1)
        t_nodes = np.linspace(0.0, 1.0, ny + 1)
        X = np.zeros((nx + 1, ny + 1))
        Y = np.zeros((nx + 1, ny + 1))
        for i, xi in enumerate(x_nodes):
            # Smooth tanh transition
            frac = 0.5 * (np.tanh((xi - ramp_x0) / smooth_width) + 1.0)
            y_wall = rise_per_x * frac * (xi - ramp_x0) * (xi >= ramp_x0)
            for j, tj in enumerate(t_nodes):
                X[i, j] = xi
                Y[i, j] = y_wall + tj * (height - y_wall)
        return cls(X, Y, patches)

    @classmethod
    def from_arrays(cls, X, Y, patches=None) -> "StructuredMesh2D":
        """Create from user-supplied node-coordinate arrays."""
        return cls(np.asarray(X, dtype=np.float64),
                   np.asarray(Y, dtype=np.float64), patches)

    @classmethod
    def from_file(cls, path: str) -> "StructuredMesh2D":
        """
        Load mesh from .amesh coordinate file.

        Format::

            # comment
            TYPE structured
            NX 80
            NY 40
            PATCH inlet   west
            PATCH outlet  east
            PATCH wall    south 0:60
            PATCH ramp    south 60:80
            NODES
            x00 y00
            x10 y00
            ...    # (NX+1)*(NY+1) lines, i varies fastest
        """
        nx = ny = None
        patches: Dict[str, MeshPatch] = {}
        node_lines = []
        in_nodes = False

        with open(path, "r") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if in_nodes:
                    if not line[0].isalpha():
                        node_lines.append(line)
                    continue
                parts = line.split()
                key = parts[0].upper()
                if key == "TYPE":
                    pass
                elif key == "NX":
                    nx = int(parts[1])
                elif key == "NY":
                    ny = int(parts[1])
                elif key == "PATCH":
                    name = parts[1]
                    side = parts[2].lower()
                    if len(parts) >= 4:
                        s, e = parts[3].split(":")
                        patch = MeshPatch(side, int(s), int(e))
                    else:
                        end_val = ny if side in ("west", "east") else nx
                        patch = MeshPatch(side, 0, end_val)
                    patches[name] = patch
                elif key == "NODES":
                    in_nodes = True

        if nx is None or ny is None:
            raise ValueError(f"Missing NX or NY in {path}")

        n_nodes = (nx + 1) * (ny + 1)
        if len(node_lines) < n_nodes:
            raise ValueError(
                f"Expected {n_nodes} NODES lines, found {len(node_lines)}")

        coords = np.array([list(map(float, l.split())) for l in node_lines[:n_nodes]])
        X = coords[:, 0].reshape(nx + 1, ny + 1, order='F')
        Y = coords[:, 1].reshape(nx + 1, ny + 1, order='F')

        if not patches:
            patches = _default_patches(nx, ny)
        return cls(X, Y, patches)

    # ── Output ────────────────────────────────────────────────────────────────

    def to_file(self, path: str):
        """Save mesh to .amesh coordinate file."""
        nx, ny = self.nx, self.ny
        with open(path, "w") as f:
            f.write("# Anvil CFD Mesh v1\n")
            f.write("TYPE structured\n")
            f.write(f"NX {nx}\nNY {ny}\n")
            for name, p in self.patches.items():
                f.write(f"PATCH {name}  {p.side}  {p.start}:{p.end}\n")
            f.write("NODES\n")
            for j in range(ny + 1):
                for i in range(nx + 1):
                    f.write(f"{self.X[i, j]:.10e}  {self.Y[i, j]:.10e}\n")

    # ── Info / plot ───────────────────────────────────────────────────────────

    def info(self):
        """Print mesh statistics to stdout."""
        nx, ny = self.nx, self.ny
        dx_mean = (self.X[-1, 0] - self.X[0, 0]) / nx
        dy_mean = (self.Y[0, -1] - self.Y[0, 0]) / ny
        ar = (self.vol.max() / self.vol.min()) if self.vol.min() > 0 else float('inf')
        n_nodes = (nx + 1) * (ny + 1)
        print(f"  Mesh: {nx} x {ny} cells  |  {n_nodes} nodes")
        print(f"  x: [{self.X.min():.4g}, {self.X.max():.4g}]  "
              f"y: [{self.Y.min():.4g}, {self.Y.max():.4g}]")
        print(f"  Mean dx={dx_mean:.4g}  dy={dy_mean:.4g}")
        print(f"  Cell area ratio (max/min): {ar:.2f}")
        if self.patches:
            print(f"  Patches ({len(self.patches)}): "
                  + ", ".join(f"{n}[{p.side},{p.start}:{p.end}]"
                              for n, p in self.patches.items()))

    def plot(self, ax=None, show=True, show_patches=True, show_mesh=True,
             mesh_skip=None, figsize=(11, 5), title=None, save_path=None):
        """
        Plot mesh grid and named boundary patches.

        Parameters
        ----------
        show_patches : bool  colour-code and label each named patch
        show_mesh    : bool  draw interior grid lines
        mesh_skip    : int   draw every Nth grid line (default: auto)
        save_path    : str   save PNG/PDF instead of showing
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
        except ImportError:
            raise ImportError("pip install matplotlib")

        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)

        # Domain outline
        ax.plot(self.X[0,  :], self.Y[0,  :], 'k-', lw=1.5)
        ax.plot(self.X[-1, :], self.Y[-1, :], 'k-', lw=1.5)
        ax.plot(self.X[:,  0], self.Y[:,  0], 'k-', lw=1.5)
        ax.plot(self.X[:, -1], self.Y[:, -1], 'k-', lw=1.5)

        # Interior grid lines
        if show_mesh:
            skip = mesh_skip or max(1, min(self.nx, self.ny) // 20)
            for i in range(0, self.nx + 1, skip):
                ax.plot(self.X[i, :], self.Y[i, :], 'k-', lw=0.25, alpha=0.4)
            for j in range(0, self.ny + 1, skip):
                ax.plot(self.X[:, j], self.Y[:, j], 'k-', lw=0.25, alpha=0.4)

        # Named patches
        legend_handles = []
        if show_patches and self.patches:
            cmap = plt.get_cmap("tab10")
            for idx, (name, p) in enumerate(self.patches.items()):
                color = cmap(idx % 10)
                s, e = p.start, p.end
                if p.side == "west":
                    xs = self.X[0, s:e + 1]; ys = self.Y[0, s:e + 1]
                elif p.side == "east":
                    xs = self.X[-1, s:e + 1]; ys = self.Y[-1, s:e + 1]
                elif p.side == "south":
                    xs = self.X[s:e + 1, 0]; ys = self.Y[s:e + 1, 0]
                else:  # north
                    xs = self.X[s:e + 1, -1]; ys = self.Y[s:e + 1, -1]

                ax.plot(xs, ys, '-', color=color, lw=4, solid_capstyle='round')
                mx, my = float(xs.mean()), float(ys.mean())
                offset = 0.02 * (self.Y.max() - self.Y.min())
                ax.text(mx, my + offset, name, color=color, fontsize=8,
                        ha='center', va='bottom', fontweight='bold')
                legend_handles.append(mpatches.Patch(color=color, label=name))

        n_nodes = (self.nx + 1) * (self.ny + 1)
        hdr = (title or
               f"{self.nx}×{self.ny} cells  |  {n_nodes} nodes  |  "
               f"{len(self.patches)} patches")
        ax.set_title(hdr, fontsize=10)
        ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
        ax.set_aspect('equal', adjustable='datalim')
        if legend_handles:
            ax.legend(handles=legend_handles, fontsize=8, loc='upper right',
                      framealpha=0.8)

        if save_path:
            plt.tight_layout()
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
        elif show:
            plt.tight_layout()
            plt.show()
        return ax
