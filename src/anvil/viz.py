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
