"""
Visualization for Anvil results.

Provides plotting functions for:
    - Convergence history (from monitored solves)
    - Parametric sweep results
    - System dependency graphs

All plots use matplotlib. Import is deferred so anvil works without it.

Usage:
    from anvil import viz

    # Convergence plot
    result = system.solve(monitor=True)
    viz.convergence(system)

    # Sweep plot
    sweep = system.sweep("P0", values)
    viz.sweep_plot(sweep, y=["thrust", "Isp"])

    # Variable history during solve
    viz.variable_trace(system, ["T_hot_out", "T_cold_out"])

    # System dependency graph
    viz.dependency_graph(system)
"""

from __future__ import annotations


def _get_plt():
    """Lazy import matplotlib."""
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        raise ImportError(
            "matplotlib is required for visualization.\n"
            "  Install: pip install matplotlib"
        )


def convergence(system, ax=None, show=True):
    """
    Plot convergence residual vs iteration.

    Parameters
    ----------
    system : System
        Must have been solved with monitor=True.
    ax : matplotlib Axes, optional
    show : bool
        Call plt.show() if True.
    """
    plt = _get_plt()

    if not hasattr(system, '_watchdog') or not system._watchdog.history:
        hist = system.history()
        if not hist:
            print("  No monitoring data. Use system.solve(monitor=True).")
            return
        iterations = [h["iteration"] for h in hist]
        residuals = [h["residual"] for h in hist]
    else:
        wd = system._watchdog
        iterations = list(range(len(wd.residuals)))
        residuals = list(wd.residuals)

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))

    ax.semilogy(iterations, residuals, "o-", markersize=3, linewidth=1.5, color="#2E75B6")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Max Relative Change")
    ax.set_title(f"{system.name} -- Convergence")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=1e-6, color="green", linestyle="--", alpha=0.5, label="default rtol")
    ax.legend()

    if show:
        plt.tight_layout()
        plt.show()
    return ax


def variable_trace(system, variables, ax=None, show=True):
    """
    Plot variable values vs iteration during a monitored solve.

    Parameters
    ----------
    system : System
    variables : list of str
        Variable names to plot.
    """
    plt = _get_plt()

    if hasattr(system, '_watchdog') and system._watchdog.history:
        wd = system._watchdog
        hist = wd.history
    else:
        hist = system.history()

    if not hist:
        print("  No monitoring data. Use system.solve(monitor=True).")
        return

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))

    iterations = [h["iteration"] for h in hist]
    for var in variables:
        values = [h["variables"].get(var, float("nan")) for h in hist]
        ax.plot(iterations, values, "o-", markersize=3, linewidth=1.5, label=var)

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Value (SI)")
    ax.set_title(f"{system.name} -- Variable Trace")
    ax.legend()
    ax.grid(True, alpha=0.3)

    if show:
        plt.tight_layout()
        plt.show()
    return ax


def sweep_plot(sweep_result, y=None, x_label=None, ax=None, show=True):
    """
    Plot sweep results.

    Parameters
    ----------
    sweep_result : SweepResult
    y : list of str, optional
        Output names to plot. Defaults to first 4 outputs.
    """
    plt = _get_plt()

    param = sweep_result._param
    x_vals = sweep_result[param]
    outputs = y or sweep_result._output_keys[:4]

    n = len(outputs)
    if n == 0:
        print("  No outputs to plot.")
        return

    if n == 1:
        fig, axes = plt.subplots(1, 1, figsize=(8, 5))
        axes = [axes]
    else:
        cols = min(n, 2)
        rows = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
        if hasattr(axes, "flatten"):
            axes = axes.flatten()
        else:
            axes = [axes]

    for i, key in enumerate(outputs):
        if i >= len(axes):
            break
        ax = axes[i]
        y_vals = sweep_result[key]

        # Get unit from first result
        from anvil.quantity import Quantity
        if sweep_result._results and key in sweep_result._results[0]:
            q = sweep_result._results[0][key]
            unit = q.unit if isinstance(q, Quantity) and q.unit else ""
        else:
            unit = ""

        ax.plot(x_vals, y_vals, "o-", markersize=4, linewidth=1.5, color="#2E75B6")
        ax.set_xlabel(x_label or param)
        ylabel = f"{key} [{unit}]" if unit else key
        ax.set_ylabel(ylabel)
        ax.set_title(key)
        ax.grid(True, alpha=0.3)

    # Hide unused subplots
    for j in range(len(outputs), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(f"{sweep_result._system_name} -- Sweep over {param}",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    if show:
        plt.show()
    return fig


def dependency_graph(system, show=True, save=None):
    """
    Plot the system's dependency graph.

    Nodes: quantities (rectangles) and relations (ellipses).
    Edges: data flow from inputs to outputs.

    Parameters
    ----------
    system : System
    show : bool
    save : str, optional
        Filepath to save the figure.
    """
    plt = _get_plt()

    if not system._validated:
        try:
            system.validate()
        except Exception:
            pass

    # Build graph data
    q_names = list(system._quantities.keys())
    r_names = [r.name for r in system._relations]

    # Edges: quantity -> relation (input), relation -> quantity (output)
    edges_in = []   # (quantity, relation)
    edges_out = []  # (relation, quantity)

    for rel in system._relations:
        for inp in rel._inputs:
            if inp in system._quantities or any(inp in r._outputs for r in system._relations):
                edges_in.append((inp, rel.name))
        for out in rel._outputs:
            edges_out.append((rel.name, out))

    # Layout: quantities on left/right, relations in middle
    fig, ax = plt.subplots(figsize=(12, max(6, len(system._relations) * 1.2)))

    # Position nodes
    n_q = len(q_names)
    n_r = len(r_names)

    # Input quantities on the left
    all_outputs = set()
    for r in system._relations:
        all_outputs.update(r._outputs)
    input_qs = [q for q in q_names if q not in all_outputs]
    output_qs = sorted(all_outputs)

    y_spacing_q = 1.0
    y_spacing_r = 1.0

    positions = {}

    # Input quantities: x=0
    for i, name in enumerate(input_qs):
        positions[name] = (0, -i * y_spacing_q)

    # Relations: x=2
    for i, name in enumerate(r_names):
        positions[name] = (2, -i * y_spacing_r)

    # Output quantities: x=4
    for i, name in enumerate(output_qs):
        positions[name] = (4, -i * y_spacing_q * 0.7)

    # Draw edges
    for src, dst in edges_in:
        if src in positions and dst in positions:
            ax.annotate("", xy=positions[dst], xytext=positions[src],
                        arrowprops=dict(arrowstyle="->", color="#888888",
                                        connectionstyle="arc3,rad=0.1", lw=1))

    for src, dst in edges_out:
        if src in positions and dst in positions:
            ax.annotate("", xy=positions[dst], xytext=positions[src],
                        arrowprops=dict(arrowstyle="->", color="#2E75B6",
                                        connectionstyle="arc3,rad=0.1", lw=1.5))

    # Draw nodes
    for name in input_qs:
        if name in positions:
            x, y = positions[name]
            ax.add_patch(plt.Rectangle((x - 0.6, y - 0.2), 1.2, 0.4,
                         facecolor="#E8F4E8", edgecolor="#4CAF50", linewidth=1.5,
                         zorder=3))
            ax.text(x, y, name, ha="center", va="center", fontsize=8,
                    fontweight="bold", zorder=4)

    for name in r_names:
        if name in positions:
            x, y = positions[name]
            ax.add_patch(plt.FancyBboxPatch((x - 0.8, y - 0.2), 1.6, 0.4,
                         boxstyle="round,pad=0.1",
                         facecolor="#FFF3E0", edgecolor="#FF9800", linewidth=1.5,
                         zorder=3))
            ax.text(x, y, name, ha="center", va="center", fontsize=7, zorder=4)

    for name in output_qs:
        if name in positions:
            x, y = positions[name]
            ax.add_patch(plt.Rectangle((x - 0.5, y - 0.2), 1.0, 0.4,
                         facecolor="#E3F2FD", edgecolor="#2196F3", linewidth=1.5,
                         zorder=3))
            ax.text(x, y, name, ha="center", va="center", fontsize=8,
                    fontweight="bold", zorder=4)

    # Labels
    ax.text(0, 0.8, "Inputs", ha="center", fontsize=11, fontweight="bold", color="#4CAF50")
    ax.text(2, 0.8, "Relations", ha="center", fontsize=11, fontweight="bold", color="#FF9800")
    ax.text(4, 0.8, "Outputs", ha="center", fontsize=11, fontweight="bold", color="#2196F3")

    ax.set_xlim(-1.5, 5.5)
    all_ys = [p[1] for p in positions.values()]
    if all_ys:
        ax.set_ylim(min(all_ys) - 1, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{system.name} -- Dependency Graph", fontsize=13, fontweight="bold")

    plt.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    return fig


def pod_energy(pod_result, ax=None, show=True, threshold=0.99):
    """
    Plot POD singular value spectrum and cumulative energy.

    Parameters
    ----------
    pod_result : dict
        From anvil.decomp.pod().
    threshold : float
        Horizontal guide line at this cumulative energy level (default 0.99).
    ax : array of 2 Axes, optional
        If provided, plots into ax[0] and ax[1].
    show : bool
    """
    plt = _get_plt()
    import numpy as np

    s = pod_result["singular_values"]
    ce = pod_result["cumulative_energy"]
    r = pod_result["rank"]
    modes = np.arange(1, r + 1)

    if ax is None:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    else:
        axes = ax
        fig = axes[0].figure

    # Singular value spectrum
    axes[0].bar(modes, s, color="#2E75B6", alpha=0.8, width=0.7)
    axes[0].set_xlabel("Mode")
    axes[0].set_ylabel("Singular value")
    axes[0].set_title("POD Singular Value Spectrum")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.3, axis="y")

    # Cumulative energy
    axes[1].plot(modes, ce * 100, "o-", color="#E05C2A", linewidth=2, markersize=4)
    axes[1].axhline(y=threshold * 100, color="#4CAF50", linestyle="--",
                    alpha=0.8, label=f"{threshold*100:.0f}% energy")
    n_thresh = min(int(np.searchsorted(ce, threshold)) + 1, r)
    axes[1].axvline(x=n_thresh, color="#4CAF50", linestyle=":", alpha=0.7)
    axes[1].annotate(
        f"{n_thresh} modes",
        xy=(n_thresh, threshold * 100),
        xytext=(n_thresh + max(1, r * 0.03), threshold * 100 - 6),
        fontsize=9, color="#2a6e2a",
    )
    axes[1].set_xlabel("Mode")
    axes[1].set_ylabel("Cumulative energy [%]")
    axes[1].set_title("POD Cumulative Energy")
    axes[1].set_ylim(0, 105)
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    if show:
        plt.show()
    return fig


def dmd_spectrum(dmd_result, ax=None, show=True, unit_circle=True):
    """
    Plot DMD eigenvalue spectrum in the complex plane.

    Marker size and color represent normalized mode amplitude.
    Modes inside the unit circle are stable; outside are growing.

    Parameters
    ----------
    dmd_result : dict
        From anvil.decomp.dmd().
    unit_circle : bool
        Draw the unit circle (|λ|=1 = neutrally stable).
    ax : matplotlib Axes, optional
    show : bool
    """
    plt = _get_plt()
    import numpy as np

    evals = dmd_result["eigenvalues"]
    amps = np.abs(dmd_result["amplitudes"])
    amps_norm = amps / (amps.max() + 1e-30)

    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6))
    else:
        fig = ax.figure

    if unit_circle:
        theta = np.linspace(0, 2 * np.pi, 400)
        ax.plot(np.cos(theta), np.sin(theta), "k--", linewidth=0.8,
                alpha=0.4, label="Unit circle (|λ|=1)")

    sc = ax.scatter(
        evals.real, evals.imag,
        c=amps_norm, cmap="plasma",
        s=40 + 140 * amps_norm,
        edgecolors="k", linewidths=0.5,
        zorder=3, vmin=0, vmax=1,
    )
    plt.colorbar(sc, ax=ax, label="Normalized amplitude")

    ax.axhline(0, color="#aaa", linewidth=0.5)
    ax.axvline(0, color="#aaa", linewidth=0.5)
    ax.set_xlabel("Re(lambda)")
    ax.set_ylabel("Im(lambda)")
    ax.set_title("DMD Eigenvalue Spectrum")
    ax.set_aspect("equal")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    if show:
        plt.show()
    return fig


def abel_compare(image, abel_result, ax=None, show=True, cmap="hot", log_scale=False):
    """
    Side-by-side comparison: raw projection vs Abel-inverted radial distribution.

    Parameters
    ----------
    image : ndarray, shape (n_rows, n_cols)
        Original camera image (projection).
    abel_result : dict
        From anvil.decomp.abel_image().
    ax : array of 2 Axes, optional
        If provided, uses ax[0] for raw and ax[1] for radial.
    show : bool
    cmap : str
        Colormap. Default "hot". Try "inferno", "viridis", "gray".
    log_scale : bool
        Apply log1p to both images (useful for high dynamic-range data).
    """
    plt = _get_plt()
    import numpy as np

    radial = abel_result["radial"]
    _, cc = abel_result["center"]
    method = abel_result["method"]

    if ax is None:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    else:
        axes = ax
        fig = axes[0].figure

    def _imshow(ax_, data, title):
        d = np.log1p(np.maximum(data, 0.0)) if log_scale else data
        finite = d[np.isfinite(d)]
        vmax = float(np.percentile(finite, 99)) if finite.size > 0 else 1.0
        im = ax_.imshow(d, cmap=cmap, origin="upper",
                        vmin=0.0, vmax=max(vmax, 1e-30), aspect="auto")
        ax_.axvline(cc, color="cyan", linewidth=0.8, alpha=0.7, linestyle="--",
                    label=f"axis col {cc}")
        ax_.set_title(title)
        ax_.set_xlabel("x [px]")
        ax_.set_ylabel("y [px]")
        ax_.legend(fontsize=8, loc="upper right")
        plt.colorbar(im, ax=ax_, fraction=0.03, pad=0.02)

    scale_label = " (log1p)" if log_scale else ""
    _imshow(axes[0], image,  f"Projection{scale_label}")
    _imshow(axes[1], radial, f"Abel inverse: {method}{scale_label}")

    plt.tight_layout()
    if show:
        plt.show()
    return fig
