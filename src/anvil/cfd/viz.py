"""
anvil.cfd.viz — CFD-specific visualization.

Functions
---------
contour(result, field, ...)      : filled contour plot, optionally with boundary labels
save_png(result, field, path, .) : save a single contour snapshot to PNG
convergence_png(history, path)   : save residual convergence to PNG
mesh_plot(mesh, ...)             : plot mesh + named boundary patches

Usage::

    from anvil.cfd import viz as cfd_viz
    cfd_viz.contour(result, "p")              # interactive
    cfd_viz.save_png(result, "M", "mach.png") # save file
    cfd_viz.mesh_plot(mesh, save_path="mesh.png")
"""

from __future__ import annotations
import numpy as np


# Field metadata: (label, default cmap)
_FIELD_INFO = {
    "p":   ("Pressure [Pa]",        "jet"),
    "T":   ("Temperature [K]",      "hot"),
    "M":   ("Mach number",          "RdBu_r"),
    "rho": ("Density [kg/m³]",      "viridis"),
    "u":   ("u-velocity [m/s]",     "seismic"),
    "v":   ("v-velocity [m/s]",     "seismic"),
    "cp":  ("Pressure coeff Cp",    "coolwarm"),
    "pt":  ("Total pressure [Pa]",  "plasma"),
}


def _get_plt():
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        raise ImportError("pip install matplotlib")


def _extract_field(result, field: str) -> np.ndarray:
    """Return (nx, ny) array for requested field name."""
    if field == "p":
        return result.p
    elif field == "T":
        return result.T
    elif field == "M":
        return result.M
    elif field == "rho":
        return result.rho
    elif field == "u":
        return result.u
    elif field == "v":
        return result.v
    elif field == "cp":
        # Cp = (p - p_ref) / q_ref — needs reference; use min p as p_ref
        p_ref = result.p.min(); q_ref = max(result.p.max() - p_ref, 1.0)
        return (result.p - p_ref) / q_ref
    elif field == "pt":
        g = result.gamma
        return result.p * (1.0 + 0.5*(g-1)*result.M**2) ** (g/(g-1))
    else:
        raise ValueError(f"Unknown field '{field}'. Choose from: {list(_FIELD_INFO)}")


def contour(result, field: str = "p", ax=None, show: bool = True,
            cmap: str = None, levels: int = 60, show_patches: bool = True,
            figsize=(11, 5), title: str = None, save_path: str = None):
    """
    Filled contour plot of a CFD result field.

    Parameters
    ----------
    result      : CFDResult
    field       : "p", "T", "M", "rho", "u", "v", "cp", "pt"
    show_patches: overlay named boundary patches
    save_path   : if given, save to this path and close figure
    """
    plt = _get_plt()
    label, default_cmap = _FIELD_INFO.get(field, (field, "jet"))
    cmap = cmap or default_cmap

    data = _extract_field(result, field)
    mesh = result.mesh

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    cf = ax.contourf(mesh.xc, mesh.yc, data, levels=levels, cmap=cmap)
    plt.colorbar(cf, ax=ax, label=label, fraction=0.03, pad=0.02)

    # Domain outline
    ax.plot(mesh.X[0,  :], mesh.Y[0,  :], 'k-', lw=1.0)
    ax.plot(mesh.X[-1, :], mesh.Y[-1, :], 'k-', lw=1.0)
    ax.plot(mesh.X[:,  0], mesh.Y[:,  0], 'k-', lw=1.5)
    ax.plot(mesh.X[:, -1], mesh.Y[:, -1], 'k-', lw=1.0)

    # Named patches
    if show_patches and mesh.patches:
        tab10 = plt.get_cmap("tab10")
        for idx, (name, p) in enumerate(mesh.patches.items()):
            color = tab10(idx % 10)
            s, e = p.start, p.end
            if p.side == "west":
                xs = mesh.X[0,  s:e+1]; ys = mesh.Y[0,  s:e+1]
            elif p.side == "east":
                xs = mesh.X[-1, s:e+1]; ys = mesh.Y[-1, s:e+1]
            elif p.side == "south":
                xs = mesh.X[s:e+1, 0];  ys = mesh.Y[s:e+1, 0]
            else:
                xs = mesh.X[s:e+1, -1]; ys = mesh.Y[s:e+1, -1]
            ax.plot(xs, ys, '-', color=color, lw=3)
            ax.text(float(xs.mean()), float(ys.mean()), name,
                    color=color, fontsize=7, ha='center', va='bottom',
                    fontweight='bold')

    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    hdr = title or (
        f"{label}  |  {mesh.nx}×{mesh.ny} cells  |  "
        f"{'converged' if result.converged else 'not converged'}"
        f"  ({result.n_iter} iter)")
    ax.set_title(hdr, fontsize=9)

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    elif show:
        plt.tight_layout()
        plt.show()
    return ax


def save_png(result, field: str, path: str, title: str = None, **kwargs):
    """Save contour plot to PNG (non-interactive)."""
    contour(result, field=field, show=False, save_path=path,
            title=title, **kwargs)


def convergence_png(history: list, path: str, title: str = "Residual convergence"):
    """Save residual convergence plot to PNG."""
    plt = _get_plt()
    if not history:
        return
    iters = [h["iteration"] for h in history]
    res0  = history[0]["residual"] or 1.0
    norms = [h["residual"] / res0 for h in history]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.semilogy(iters, norms, 'b-', lw=1.2)
    ax.set_xlabel("Iteration"); ax.set_ylabel("res / res₀")
    ax.set_title(title); ax.grid(True, which='both', alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()


def multi_field(result, fields=("M", "p", "T", "rho"),
                figsize=None, show=True, save_path=None):
    """
    2×2 (or 1×N) panel plot of multiple fields side by side.

    Parameters
    ----------
    fields : list of field names to plot (max 4 for 2×2 layout)
    """
    plt = _get_plt()
    n = len(fields)
    ncols = min(n, 2); nrows = (n + 1) // 2
    if figsize is None:
        figsize = (6 * ncols, 4 * nrows)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axs = [axes[r][c] for r in range(nrows) for c in range(ncols)]

    for i, f in enumerate(fields):
        contour(result, f, ax=axs[i], show=False)
    for j in range(i + 1, len(axs)):
        axs[j].set_visible(False)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    elif show:
        plt.show()
    return fig, axes


def mesh_plot(mesh, show=True, save_path=None, **kwargs):
    """Convenience wrapper for mesh.plot()."""
    return mesh.plot(show=show, save_path=save_path, **kwargs)
