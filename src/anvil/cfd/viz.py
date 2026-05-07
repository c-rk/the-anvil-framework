"""
anvil.cfd.viz — CFD-specific visualization.

All plots use monospace font and support a fixed colorbar scale
so successive snapshots (save_every) are directly comparable.

Functions
---------
contour(result, field, ...)        filled contour with patch labels
save_png(result, field, path, ...) non-interactive contour save
convergence_png(history, path)     residual history plot
multi_field(result, fields, ...)   2x2 panel of multiple fields
mesh_plot(mesh, ...)               mesh + named boundary patches

Usage::

    from anvil.cfd import viz as cfd_viz

    # Fixed colorbar so all snapshots use same scale
    cfd_viz.contour(result, "p", vmin=90000, vmax=180000)
    cfd_viz.save_png(result, "M", "mach.png", vmin=0, vmax=2.5)

    # Multi-field panel
    cfd_viz.multi_field(result, ["M", "p", "T", "rho"],
                        vmin_map={"p": (90e3, 200e3), "M": (0, 3)},
                        save_path="overview.png")
"""

from __future__ import annotations
import numpy as np


# Field metadata: (label, default cmap)
_FIELD_INFO = {
    "p":   ("Pressure [Pa]",       "jet"),
    "T":   ("Temperature [K]",     "hot"),
    "M":   ("Mach number",         "RdBu_r"),
    "rho": ("Density [kg/m3]",     "viridis"),
    "u":   ("u-velocity [m/s]",    "seismic"),
    "v":   ("v-velocity [m/s]",    "seismic"),
    "cp":  ("Pressure coeff Cp",   "coolwarm"),
    "pt":  ("Total pressure [Pa]", "plasma"),
}


def _get_plt():
    try:
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        mpl.rcParams.update({
            'font.family':   'monospace',
            'font.monospace': ['Consolas', 'DejaVu Sans Mono', 'Courier New', 'monospace'],
            'axes.titlesize': 9,
            'axes.labelsize': 8,
            'xtick.labelsize': 7,
            'ytick.labelsize': 7,
        })
        return plt
    except ImportError:
        raise ImportError("pip install matplotlib")


def _extract_field(result, field: str) -> np.ndarray:
    if field == "p":    return result.p
    if field == "T":    return result.T
    if field == "M":    return result.M
    if field == "rho":  return result.rho
    if field == "u":    return result.u
    if field == "v":    return result.v
    if field == "cp":
        p_ref = result.p.min(); q_ref = max(result.p.max() - p_ref, 1.0)
        return (result.p - p_ref) / q_ref
    if field == "pt":
        g = result.gamma
        return result.p * (1.0 + 0.5*(g-1)*result.M**2) ** (g/(g-1))
    raise ValueError(f"Unknown field '{field}'. Choose: {list(_FIELD_INFO)}")


def _draw_patches(ax, mesh, plt_ref):
    """Overlay named boundary patches with colour-coded lines and labels."""
    if not (mesh and hasattr(mesh, 'patches') and mesh.patches):
        return
    tab10 = plt_ref.get_cmap("tab10")
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
                fontweight='bold', fontfamily='monospace')


def contour(result, field: str = "p", ax=None, show: bool = True,
            cmap: str = None, levels: int = 60,
            vmin=None, vmax=None,
            show_patches: bool = True,
            figsize=(11, 5), title: str = None, save_path: str = None):
    """
    Filled contour plot of a CFD result field.

    Parameters
    ----------
    result      : CFDResult
    field       : "p" | "T" | "M" | "rho" | "u" | "v" | "cp" | "pt"
    vmin, vmax  : float  fix colorbar limits (use same values across snapshots
                  for frame-by-frame comparison)
    show_patches: overlay named boundary patches with labels
    save_path   : save to file instead of showing
    """
    plt = _get_plt()
    label, default_cmap = _FIELD_INFO.get(field, (field, "jet"))
    cmap = cmap or default_cmap
    data = _extract_field(result, field)
    mesh = result.mesh

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Build contour levels from vmin/vmax if given
    if vmin is not None or vmax is not None:
        lo = vmin if vmin is not None else float(data.min())
        hi = vmax if vmax is not None else float(data.max())
        lvls = np.linspace(lo, hi, levels)
        cf = ax.contourf(mesh.xc, mesh.yc, data, levels=lvls, cmap=cmap,
                         extend='both')
    else:
        cf = ax.contourf(mesh.xc, mesh.yc, data, levels=levels, cmap=cmap)

    cb = plt.colorbar(cf, ax=ax, label=label, fraction=0.03, pad=0.02)
    cb.ax.tick_params(labelsize=7)

    # Domain outline
    ax.plot(mesh.X[0,  :], mesh.Y[0,  :], 'k-', lw=0.8)
    ax.plot(mesh.X[-1, :], mesh.Y[-1, :], 'k-', lw=0.8)
    ax.plot(mesh.X[:,  0], mesh.Y[:,  0], 'k-', lw=1.2)
    ax.plot(mesh.X[:, -1], mesh.Y[:, -1], 'k-', lw=0.8)

    if show_patches:
        _draw_patches(ax, mesh, plt)

    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    geo = getattr(mesh, 'title', '') or ''
    status = 'converged' if result.converged else 'not converged'
    hdr = title or (
        f"{field}  {geo+'  |  ' if geo else ''}{mesh.nx}x{mesh.ny}  "
        f"{status}  ({result.n_iter} iter)"
    )
    ax.set_title(hdr, fontfamily='monospace')

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    elif show:
        plt.tight_layout()
        plt.show()
    return ax


def save_png(result, field: str, path: str,
             vmin=None, vmax=None, title: str = None, **kwargs):
    """
    Save contour plot to PNG (non-interactive).

    Parameters
    ----------
    vmin, vmax : fix colorbar scale — use same values for all save_every frames
                 so animation stays comparable
    """
    contour(result, field=field, show=False, save_path=path,
            vmin=vmin, vmax=vmax, title=title, **kwargs)


def convergence_png(history: list, path: str, title: str = "Residual convergence"):
    """Save residual convergence plot to PNG."""
    plt = _get_plt()
    if not history:
        return
    iters = [h["iteration"] for h in history]
    res0  = max(history[0]["residual"], 1e-30)
    norms = [h["residual"] / res0 for h in history]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.semilogy(iters, norms, 'b-', lw=1.2)
    ax.set_xlabel("Iteration"); ax.set_ylabel("res / res0")
    ax.set_title(title, fontfamily='monospace')
    ax.grid(True, which='both', alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()


def multi_field(result, fields=("M", "p", "T", "rho"),
                figsize=None, show=True, save_path=None,
                vmin_map: dict = None):
    """
    2x2 (or 1xN) panel plot of multiple fields.

    Parameters
    ----------
    fields   : list of field names (max 4 for 2x2 layout)
    vmin_map : dict mapping field → (vmin, vmax), e.g.
               {"p": (90e3, 200e3), "M": (0.0, 3.0)}
               Fields not in vmin_map use auto-scale.
    """
    plt = _get_plt()
    vmin_map = vmin_map or {}
    n = len(fields)
    ncols = min(n, 2); nrows = (n + 1) // 2
    if figsize is None:
        figsize = (6 * ncols, 4 * nrows)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axs = [axes[r][c] for r in range(nrows) for c in range(ncols)]

    for i, f in enumerate(fields):
        lo, hi = vmin_map.get(f, (None, None))
        contour(result, f, ax=axs[i], show=False, vmin=lo, vmax=hi)
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
