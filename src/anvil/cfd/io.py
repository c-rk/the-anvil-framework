"""
anvil.cfd.io — Output writers for ParaView (VTK) and Tecplot.

Supports:
    VTK legacy ASCII  (.vtk)  — opens directly in ParaView and VisIt
    Tecplot ASCII     (.dat)  — opens in Tecplot or ParaView (ASCII reader)
    NumPy restart     (.npz)  — for restarting a solve

Field names written: rho, u, v, p, T, Mach, total_pressure_ratio.

Extensibility
-------------
For 3D: extend _write_vtk_structured to write rectilinear/curvilinear 3D.
For binary: use struct.pack or vtk library for faster I/O on large grids.
"""

from __future__ import annotations
import numpy as np


def write_vtk(path: str, mesh, fields: dict, title: str = "anvil_cfd"):
    """
    Write VTK legacy structured grid file (ASCII).

    Parameters
    ----------
    path   : output file path (.vtk)
    mesh   : StructuredMesh2D
    fields : dict of str -> 2D ndarray (nx, ny), cell-centred scalars
             or 3-tuple of 2D arrays for vector field
    title  : dataset title
    """
    nx, ny = mesh.nx, mesh.ny
    n_pts  = (nx + 1) * (ny + 1)
    n_cells = nx * ny

    with open(path, "w") as f:
        # Header
        f.write("# vtk DataFile Version 3.0\n")
        f.write(f"{title}\n")
        f.write("ASCII\n")
        f.write("DATASET STRUCTURED_GRID\n")
        f.write(f"DIMENSIONS {nx+1} {ny+1} 1\n")
        f.write(f"POINTS {n_pts} double\n")

        # Node coordinates (VTK needs X Y Z for each node)
        for j in range(ny + 1):
            for i in range(nx + 1):
                f.write(f"{mesh.X[i,j]:.8e} {mesh.Y[i,j]:.8e} 0.0\n")

        # Cell data
        f.write(f"\nCELL_DATA {n_cells}\n")
        for name, data in fields.items():
            if isinstance(data, tuple) and len(data) == 2:
                # Vector field (u, v) → store as 3-component vector
                u_arr, v_arr = data
                f.write(f"VECTORS {name} double\n")
                for j in range(ny):
                    for i in range(nx):
                        f.write(f"{float(u_arr[i,j]):.8e} "
                                f"{float(v_arr[i,j]):.8e} 0.0\n")
            else:
                f.write(f"SCALARS {name} double 1\n")
                f.write("LOOKUP_TABLE default\n")
                arr = np.asarray(data)
                for j in range(ny):
                    for i in range(nx):
                        f.write(f"{float(arr[i,j]):.8e}\n")


def write_tecplot(path: str, mesh, fields: dict, title: str = "anvil_cfd"):
    """
    Write Tecplot ASCII POINT file (cell-centred data).

    Parameters
    ----------
    path   : output file path (.dat)
    mesh   : StructuredMesh2D
    fields : dict of str -> 2D ndarray (nx, ny)
    title  : zone title
    """
    nx, ny = mesh.nx, mesh.ny
    var_names = ["x", "y"] + list(fields.keys())

    with open(path, "w") as f:
        f.write(f'TITLE="{title}"\n')
        f.write('VARIABLES=' + ' '.join(f'"{n}"' for n in var_names) + '\n')
        f.write(f'ZONE T="Fluid", I={nx}, J={ny}, DATAPACKING=POINT\n')

        for j in range(ny):
            for i in range(nx):
                row = [f"{mesh.xc[i,j]:.8e}", f"{mesh.yc[i,j]:.8e}"]
                for name, arr in fields.items():
                    row.append(f"{float(arr[i,j]):.8e}")
                f.write(" ".join(row) + "\n")


def write_restart(path: str, U_ext, iteration: int, time: float):
    """Save solver state as numpy compressed file."""
    np.savez_compressed(path, U_ext=U_ext,
                        iteration=iteration, time=time)


def load_restart(path: str):
    """Load solver state. Returns (U_ext, iteration, time)."""
    d = np.load(path)
    return d["U_ext"], int(d["iteration"]), float(d["time"])
