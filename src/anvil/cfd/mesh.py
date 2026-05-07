"""
anvil.cfd.mesh -- Structured 2D mesh generation, file I/O, and geometry.

What is a structured mesh
--------------------------
Think of it as a deformed rectangular grid -- like stretching a piece of graph
paper to fit your geometry.  Every mesh has exactly four outer edges:

    left edge  (i = 0)      <- inlet / left wall
    right edge (i = NX)     <- outlet / right wall
    bottom edge(j = 0)      <- lower wall / ramp / airfoil
    top edge   (j = NY)     <- upper wall / farfield / ceiling

Any of these four edges can be split into multiple named patches.

.amesh file format
------------------
A plain-text file you can create in any editor or generate in Python/Excel::

    # My airfoil channel -- comment lines start with #
    TITLE  naca0012_channel
    NX     80       # cells in i-direction (columns)
    NY     40       # cells in j-direction (rows)

    # Named patches -- PATCH <name> <edge> [start:end]
    # edge: left | right | top | bottom  (or west|east|north|south)
    # start:end (optional): cell-index range along that edge
    #   left/right edges  -> j-cell indices, range [0, NY)
    #   top/bottom edges  -> i-cell indices, range [0, NX)
    PATCH  inlet      left
    PATCH  outlet     right
    PATCH  airfoil    bottom   20:60
    PATCH  flat_lo    bottom    0:20
    PATCH  flat_hi    bottom   60:80
    PATCH  farfield   top

    # Node coordinates
    # Total (NX+1)*(NY+1) lines, one per node: x  y
    # Ordering: i varies fastest (column-by-column within each row)
    #   j=0  -> bottom row: (i=0,j=0) ... (i=NX,j=0)
    #   j=1  -> next row:   (i=0,j=1) ... (i=NX,j=1)
    #   ...
    #   j=NY -> top row:    (i=0,j=NY) ... (i=NX,j=NY)
    NODES
    0.000  0.000
    0.025  0.000
    ...

Generating node coordinates
---------------------------
For a simple channel with geometry on the bottom wall::

    import numpy as np
    NX, NY = 80, 40
    x = np.linspace(0, 2, NX+1)
    for j in range(NY+1):
        t = j / NY                        # 0 (bottom) -> 1 (top)
        for i in range(NX+1):
            y_wall = my_wall_function(x[i])   # bottom wall shape
            y_node = y_wall + t * (height - y_wall)
            print(f"{x[i]:.6f}  {y_node:.6f}")

Or use Mesh.from_arrays(X, Y, patches) to stay in Python without a file.

Extensibility
-------------
For 3D: add k-dimension; node array becomes (nx+1,ny+1,nz+1); add k-faces.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict

# Accepted edge-name aliases -> internal canonical names
_EDGE_NORM = {
    "left":   "west",  "west":  "west",  "w": "west",
    "right":  "east",  "east":  "east",  "e": "east",
    "bottom": "south", "south": "south", "s": "south", "bot": "south",
    "top":    "north", "north": "north", "n": "north",
}


@dataclass
class MeshPatch:
    """Named boundary patch -- a contiguous sub-range of one domain edge.

    Parameters
    ----------
    edge  : "left"|"right"|"top"|"bottom"  (or west|east|north|south)
            Stored internally as west/east/south/north.
    start : first cell index along the edge (0-based, inclusive)
    end   : last  cell index along the edge (exclusive)
            left/right  edges -> j-cell range [0, ny)
            top/bottom  edges -> i-cell range [0, nx)
    """
    side:  str   # canonical: west|east|south|north
    start: int
    end:   int

    def __post_init__(self):
        key = self.side.strip().lower()
        self.side = _EDGE_NORM.get(key, key)


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
    X, Y    : ndarray, shape (nx+1, ny+1)  -- node coordinates
    patches : dict of name -> MeshPatch, optional
              If None, defaults to full-edge patches named "west"/"east"/"south"/"north".
    title   : str  -- optional geometry/project name (shown in plots, written to file)
    """

    def __init__(self, X: np.ndarray, Y: np.ndarray,
                 patches: Optional[Dict[str, MeshPatch]] = None,
                 title: str = ""):
        assert X.shape == Y.shape and X.ndim == 2
        self.X = np.asarray(X, dtype=np.float64)
        self.Y = np.asarray(Y, dtype=np.float64)
        self.nx = X.shape[0] - 1
        self.ny = X.shape[1] - 1
        self.title = str(title)
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

        # i-face geometry: normal points from cell (i-1,j) -> (i,j) (+x for Cartesian)
        dxi = X[:, 1:] - X[:, :-1]    # (nx+1, ny)
        dyi = Y[:, 1:] - Y[:, :-1]
        self.i_nxa  =  dyi
        self.i_nya  = -dxi
        self.i_area = np.sqrt(dxi**2 + dyi**2)

        # j-face geometry: normal points from cell (i,j-1) -> (i,j) (+y for Cartesian)
        dxj = X[1:, :] - X[:-1, :]    # (nx, ny+1)
        dyj = Y[1:, :] - Y[:-1, :]
        self.j_nxa  = -dyj
        self.j_nya  =  dxj
        self.j_area = np.sqrt(dxj**2 + dyj**2)

    # -- Named constructors -----------------------------------------------------

    @classmethod
    def cartesian(cls, x_span, y_span, nx: int, ny: int,
                  patches=None, title="") -> "StructuredMesh2D":
        """Uniform Cartesian mesh."""
        x = np.linspace(x_span[0], x_span[1], nx + 1)
        y = np.linspace(y_span[0], y_span[1], ny + 1)
        X, Y = np.meshgrid(x, y, indexing='ij')
        return cls(X, Y, patches, title)

    @classmethod
    def wedge(cls, half_angle_deg: float, chord: float, height: float,
              nx: int, ny: int, x_start: float = 0.0,
              patches=None, title="") -> "StructuredMesh2D":
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
        return cls(X, Y, patches, title)

    @classmethod
    def bump(cls, length: float, height: float, nx: int, ny: int,
             bump_height: float = 0.1, bump_x0: float = None,
             bump_sigma: float = None, patches=None, title="") -> "StructuredMesh2D":
        """Channel mesh with a Gaussian bump on the lower wall."""
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
        return cls(X, Y, patches, title)

    @classmethod
    def compression_ramp(cls, length: float, height: float,
                         ramp_x0: float, ramp_angle_deg: float,
                         nx: int, ny: int,
                         smooth_width: float = None,
                         patches=None, title="") -> "StructuredMesh2D":
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
        return cls(X, Y, patches, title)

    @classmethod
    def from_arrays(cls, X, Y, patches=None, title="") -> "StructuredMesh2D":
        """Create from user-supplied node-coordinate arrays."""
        return cls(np.asarray(X, dtype=np.float64),
                   np.asarray(Y, dtype=np.float64), patches, title)

    @classmethod
    def from_file(cls, path: str) -> "StructuredMesh2D":
        """
        Load mesh from an .amesh coordinate file.

        See module docstring or Mesh.amesh_guide() for full format specification.
        """
        nx = ny = None
        title = ""
        patches: Dict[str, MeshPatch] = {}
        node_lines = []
        in_nodes = False

        with open(path, "r") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if in_nodes:
                    if not (line[0].isalpha() and line.upper().split()[0]
                            in ("TYPE", "NX", "NY", "PATCH", "NODES", "TITLE")):
                        node_lines.append(line)
                    continue
                parts = line.split()
                key = parts[0].upper()
                if key in ("TYPE",):
                    pass
                elif key == "TITLE":
                    title = " ".join(parts[1:])
                elif key == "NX":
                    nx = int(parts[1])
                elif key == "NY":
                    ny = int(parts[1])
                elif key == "PATCH":
                    name = parts[1]
                    edge = parts[2].lower()
                    norm_edge = _EDGE_NORM.get(edge, edge)
                    if len(parts) >= 4:
                        s, e = parts[3].split(":")
                        patch = MeshPatch(norm_edge, int(s), int(e))
                    else:
                        end_val = ny if norm_edge in ("west", "east") else nx
                        patch = MeshPatch(norm_edge, 0, end_val)
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
        return cls(X, Y, patches, title)

    @staticmethod
    def amesh_guide(save_example: str = None):
        """
        Print the .amesh file format guide and write an example file.

        Parameters
        ----------
        save_example : str  optional path to write a runnable example .amesh file
        """
        guide = """\
# ---------------------------------------------------------------------
# Anvil CFD  .amesh  --  Structured 2D mesh file format
# ---------------------------------------------------------------------
#
# A structured mesh is a deformed rectangle with NX*NY quadrilateral cells
# and (NX+1)*(NY+1) corner nodes.  The four outer edges are named:
#
#   left  (i=0)    right (i=NX)    bottom (j=0)    top (j=NY)
#
# Each edge can be split into multiple named patches for BCs.
#
# ---------------------------------------------------------------------
# Keywords (case-insensitive):
#
#  TITLE  <name>          optional project/geometry name
#  NX     <int>           number of cells in i-direction (required)
#  NY     <int>           number of cells in j-direction (required)
#
#  PATCH  <name>  <edge>  [start:end]
#    name  : any identifier you choose (inlet, wall, outlet, ...)
#    edge  : left | right | top | bottom   (or west|east|north|south)
#    range : optional cell-index range along that edge (0-based, exclusive end)
#              left/right  edge: j-cell range  [0 .. NY)
#              top/bottom  edge: i-cell range  [0 .. NX)
#            omit range to cover the full edge
#
#  NODES  followed by (NX+1)*(NY+1) lines of  "x  y"
#    ordering: i varies fastest (i=0..NX for each j=0..NY)
#    j=0  ->  bottom row of nodes
#    j=NY ->  top row of nodes
#
# ---------------------------------------------------------------------
TITLE  my_channel_geometry
NX     8
NY     4

PATCH  inlet      left
PATCH  outlet     right
PATCH  bump       bottom   3:6
PATCH  flat_lo    bottom   0:3
PATCH  flat_hi    bottom   6:8
PATCH  ceiling    top

NODES
#  x          y
   0.000000   0.000000
   0.250000   0.000000
   0.500000   0.000000
   0.750000   0.020000
   1.000000   0.060000
   1.250000   0.020000
   1.500000   0.000000
   1.750000   0.000000
   2.000000   0.000000
   0.000000   0.125000
   0.250000   0.125000
   0.500000   0.125000
   0.750000   0.135000
   1.000000   0.155000
   1.250000   0.135000
   1.500000   0.125000
   1.750000   0.125000
   2.000000   0.125000
   0.000000   0.250000
   0.250000   0.250000
   0.500000   0.250000
   0.750000   0.250000
   1.000000   0.250000
   1.250000   0.250000
   1.500000   0.250000
   1.750000   0.250000
   2.000000   0.250000
   0.000000   0.375000
   0.250000   0.375000
   0.500000   0.375000
   0.750000   0.375000
   1.000000   0.375000
   1.250000   0.375000
   1.500000   0.375000
   1.750000   0.375000
   2.000000   0.375000
   0.000000   0.500000
   0.250000   0.500000
   0.500000   0.500000
   0.750000   0.500000
   1.000000   0.500000
   1.250000   0.500000
   1.500000   0.500000
   1.750000   0.500000
   2.000000   0.500000
"""
        print(guide)
        if save_example:
            with open(save_example, "w") as f:
                f.write(guide)
            print(f"  Example saved to: {save_example}")
            print(f"  Load with: mesh = Mesh.from_file('{save_example}')")

    # -- Output ----------------------------------------------------------------

    def to_file(self, path: str):
        """Save mesh to .amesh coordinate file (re-loadable with Mesh.from_file)."""
        nx, ny = self.nx, self.ny
        with open(path, "w") as f:
            f.write("# Anvil CFD Mesh v1\n")
            if self.title:
                f.write(f"TITLE  {self.title}\n")
            f.write(f"NX     {nx}\nNY     {ny}\n")
            for name, p in self.patches.items():
                f.write(f"PATCH  {name:<12s}  {p.side:<8s}  {p.start}:{p.end}\n")
            f.write("NODES\n")
            f.write(f"# {(nx+1)*(ny+1)} nodes: i varies fastest, j=0 is bottom\n")
            for j in range(ny + 1):
                for i in range(nx + 1):
                    f.write(f"  {self.X[i, j]:.10e}  {self.Y[i, j]:.10e}\n")

    # -- Info / plot -----------------------------------------------------------

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
            plt.rcParams.update({'font.family': 'monospace'})
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
        base = self.title or "mesh"
        hdr = (title or
               f"{base}   {self.nx}x{self.ny} cells  |  {n_nodes} nodes  |  "
               f"{len(self.patches)} patches")
        ax.set_title(hdr, fontsize=10, fontfamily='monospace')
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
