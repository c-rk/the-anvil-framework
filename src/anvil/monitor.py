"""
Monitoring and visualization for Anvil systems.

Provides:
    - Pre-solve validation (completeness, unit compatibility, bounds)
    - Runtime convergence tracking with NaN/Inf diagnostics
    - Post-solve visualization: convergence plots, sweep charts, dependency graphs

Usage:
    from anvil.monitor import plot_convergence, plot_sweep, plot_system

    # Convergence plot from a coupled solve
    result = sys.solve(monitor=True)
    plot_convergence(sys)

    # Sweep chart
    sweep = sys.sweep("P0", np.linspace(1e6, 20e6, 20))
    plot_sweep(sweep, x="P0", y=["thrust", "Isp"])

    # System dependency graph
    plot_system(sys)
"""

import numpy as np

# Lazy matplotlib import -- only load when plotting
_plt = None
def _get_plt():
    global _plt
    if _plt is None:
        try:
            import matplotlib
            matplotlib.use("Agg")  # non-interactive backend (works headless)
        except Exception:
            pass
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt


# ============================================================
# Pre-solve diagnostics
# ============================================================

def diagnose(system):
    """
    Run pre-solve diagnostics on a System.

    Checks:
        - All required inputs are provided (not None)
        - No NaN/Inf in input values
        - Bounds violations
        - Dependency completeness
        - Cycle detection

    Returns a list of diagnostic messages.
    """
    from anvil.quantity import Quantity
    msgs = []

    # Check inputs
    for name, q in system._quantities.items():
        if q._si_value is None:
            msgs.append(f"WARNING: '{name}' has no value assigned.")
        elif not np.isfinite(q._si_value):
            msgs.append(f"ERROR: '{name}' is {q._si_value} (NaN or Inf).")
        if q.bounds and q._si_value is not None and not q.in_bounds():
            msgs.append(f"WARNING: '{name}' = {q.value} {q.unit} is outside bounds {q.bounds}.")

    # Discover outputs if not yet known
    from anvil.system import _discover_outputs
    for rel in system._relations:
        if not rel._outputs:
            _discover_outputs(rel, system._quantities, system._relations)

    # Check dependency completeness
    available = set(system._quantities.keys())
    for rel in system._relations:
        for out in rel._outputs:
            available.add(out)

    for rel in system._relations:
        for inp in rel._inputs:
            if inp not in available and inp not in rel._defaults:
                msgs.append(f"ERROR: '{rel.name}' needs '{inp}' -- not provided anywhere.")

    # Check for cycles
    try:
        system._build_exec_order()
        if system._has_cycles:
            # Identify which variables form the cycle
            all_out = set()
            all_in = set()
            for r in system._relations:
                all_out.update(r._outputs)
                all_in.update(r._inputs)
            coupled = sorted(all_out & all_in)
            msgs.append(f"INFO: Coupled variables detected: {', '.join(coupled)}. "
                        f"Will use iterative solver.")
    except Exception as e:
        msgs.append(f"ERROR: Failed to analyze dependencies: {e}")

    if not msgs:
        msgs.append("OK: System looks well-posed.")

    return msgs


# ============================================================
# Convergence plotting
# ============================================================

def plot_convergence(system, save=None, show=True, figsize=(10, 5)):
    """
    Plot convergence history from a monitored solve.

    Parameters
    ----------
    system : System
        Must have been solved with monitor=True.
    save : str, optional
        File path to save the figure (e.g., "convergence.png").
    show : bool
        Whether to display the plot interactively.
    figsize : tuple
        Figure size in inches.
    """
    plt = _get_plt()
    hist = system.history()
    if not hist:
        print("  No convergence history. Solve with monitor=True first.")
        return

    iters = [h["iteration"] for h in hist]
    residuals = [h["residual"] for h in hist]
    wallclock = [h["wallclock"] for h in hist]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    # Residual vs iteration
    ax1.semilogy(iters, residuals, "b-o", markersize=3, linewidth=1.5)
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Max relative change")
    ax1.set_title("Convergence: Residual vs Iteration")
    ax1.grid(True, alpha=0.3)

    # Residual vs wall clock
    ax2.semilogy(wallclock, residuals, "r-o", markersize=3, linewidth=1.5)
    ax2.set_xlabel("Wall clock (s)")
    ax2.set_ylabel("Max relative change")
    ax2.set_title("Convergence: Residual vs Time")
    ax2.grid(True, alpha=0.3)

    fig.suptitle(f"{system.name} -- Convergence", fontsize=13, fontweight="bold")
    fig.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save}")
    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


def plot_variables(system, variables=None, save=None, show=True, figsize=(10, 5)):
    """
    Plot variable evolution over iterations from a monitored solve.

    Parameters
    ----------
    system : System
        Must have been solved with monitor=True.
    variables : list of str, optional
        Which variables to plot. Default: all computed (non-input) variables.
    """
    plt = _get_plt()
    hist = system.history()
    if not hist:
        print("  No convergence history. Solve with monitor=True first.")
        return

    # Determine which variables to plot
    all_vars = set()
    for h in hist:
        all_vars.update(h["variables"].keys())

    input_vars = set(system._quantities.keys())
    if variables is None:
        variables = sorted(all_vars - input_vars)
    if not variables:
        variables = sorted(all_vars)[:8]  # cap at 8

    iters = [h["iteration"] for h in hist]

    fig, ax = plt.subplots(figsize=figsize)
    for var in variables:
        vals = [h["variables"].get(var, np.nan) for h in hist]
        ax.plot(iters, vals, "-o", markersize=2, linewidth=1.2, label=var)

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Value (SI)")
    ax.set_title(f"{system.name} -- Variable Evolution")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save}")
    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


# ============================================================
# Sweep plotting
# ============================================================

def plot_sweep(sweep_result, x=None, y=None, save=None, show=True, figsize=(10, 6)):
    """
    Plot sweep results.

    Parameters
    ----------
    sweep_result : SweepResult
        From system.sweep().
    x : str, optional
        X-axis variable (default: sweep parameter).
    y : str or list of str, optional
        Y-axis variable(s) (default: first 4 outputs).
    """
    plt = _get_plt()

    x = x or sweep_result._param
    if y is None:
        y = sweep_result._output_keys[:4]
    if isinstance(y, str):
        y = [y]

    x_vals = sweep_result[x]

    n = len(y)
    if n == 1:
        fig, axes = plt.subplots(1, 1, figsize=figsize)
        axes = [axes]
    else:
        cols = min(2, n)
        rows = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(figsize[0], figsize[1] * rows / 2))
        if n == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for i, var in enumerate(y):
        if i >= len(axes):
            break
        ax = axes[i]
        y_vals = sweep_result[var]

        # Get unit from first result
        unit = ""
        if sweep_result._results:
            from anvil.quantity import Quantity
            q = sweep_result._results[0].get(var)
            if isinstance(q, Quantity) and q.unit:
                unit = f" [{q.unit}]"

        ax.plot(x_vals, y_vals, "b-o", markersize=4, linewidth=1.5)
        ax.set_xlabel(x)
        ax.set_ylabel(f"{var}{unit}")
        ax.set_title(var)
        ax.grid(True, alpha=0.3)

    # Hide unused axes
    for j in range(len(y), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(f"{sweep_result._system_name} -- Sweep over {x}",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save}")
    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


# ============================================================
# System dependency graph
# ============================================================

def plot_system(system, save=None, show=True, figsize=(12, 8)):
    """
    Plot the dependency graph of a System.

    Shows quantities as rectangles, relations as rounded boxes,
    with arrows showing data flow.

    Uses matplotlib patches (no graphviz dependency).
    """
    plt = _get_plt()
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    import matplotlib.patches as mpatches

    # Ensure outputs are discovered
    try:
        system.validate()
    except Exception:
        pass

    # Collect nodes
    quantities = list(system._quantities.keys())
    relations = [(i, r) for i, r in enumerate(system._relations)]

    # Build edges: quantity -> relation (inputs), relation -> quantity (outputs)
    edges_in = []   # (qty_name, rel_idx)
    edges_out = []  # (rel_idx, qty_name)

    all_outputs = set()
    for i, rel in relations:
        for inp in rel._inputs:
            edges_in.append((inp, i))
        for out in rel._outputs:
            edges_out.append((i, out))
            all_outputs.add(out)

    # Layout: inputs on left, relations in middle, outputs on right
    input_names = [q for q in quantities if q not in all_outputs]
    output_names = sorted(all_outputs)

    # Compute positions
    positions = {}  # name_or_idx -> (x, y)

    # Inputs: x=0
    n_in = max(len(input_names), 1)
    for i, name in enumerate(input_names):
        positions[f"q_{name}"] = (0, -i * 1.5)

    # Relations: x=3
    n_rel = max(len(relations), 1)
    for i, (idx, rel) in enumerate(relations):
        positions[f"r_{idx}"] = (3, -i * 1.5)

    # Outputs: x=6
    for i, name in enumerate(output_names):
        positions[f"o_{name}"] = (6, -i * 1.2)

    fig, ax = plt.subplots(figsize=figsize)

    # Draw input boxes
    for name in input_names:
        x, y = positions[f"q_{name}"]
        q = system._quantities[name]
        unit = q.unit if q.unit else ""
        label = f"{name}\n{q.value:.4g} {unit}" if q._si_value is not None else name
        box = FancyBboxPatch((x - 0.8, y - 0.35), 1.6, 0.7,
                             boxstyle="round,pad=0.1", facecolor="#D5E8D4",
                             edgecolor="#82B366", linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center", fontsize=7, fontweight="bold")

    # Draw relation boxes
    for i, (idx, rel) in enumerate(relations):
        x, y = positions[f"r_{idx}"]
        box = FancyBboxPatch((x - 0.9, y - 0.35), 1.8, 0.7,
                             boxstyle="round,pad=0.15", facecolor="#DAE8FC",
                             edgecolor="#6C8EBF", linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, y, rel.name, ha="center", va="center", fontsize=7)

    # Draw output boxes
    for name in output_names:
        x, y = positions[f"o_{name}"]
        box = FancyBboxPatch((x - 0.8, y - 0.3), 1.6, 0.6,
                             boxstyle="round,pad=0.1", facecolor="#FFF2CC",
                             edgecolor="#D6B656", linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, y, name, ha="center", va="center", fontsize=7)

    # Draw edges: inputs -> relations
    for qty_name, rel_idx in edges_in:
        src_key = f"q_{qty_name}" if f"q_{qty_name}" in positions else None
        # Output of another relation feeding as input
        if src_key is None:
            for oi, (oidx, orel) in enumerate(relations):
                if qty_name in orel._outputs:
                    src_key = f"r_{oidx}"
                    break
        if src_key and f"r_{rel_idx}" in positions:
            sx, sy = positions[src_key]
            ex, ey = positions[f"r_{rel_idx}"]
            ax.annotate("", xy=(ex - 0.9, ey), xytext=(sx + 0.8, sy),
                        arrowprops=dict(arrowstyle="->", color="#666666",
                                        connectionstyle="arc3,rad=0.1", lw=1))

    # Draw edges: relations -> outputs
    for rel_idx, out_name in edges_out:
        if f"r_{rel_idx}" in positions and f"o_{out_name}" in positions:
            sx, sy = positions[f"r_{rel_idx}"]
            ex, ey = positions[f"o_{out_name}"]
            ax.annotate("", xy=(ex - 0.8, ey), xytext=(sx + 0.9, sy),
                        arrowprops=dict(arrowstyle="->", color="#666666",
                                        connectionstyle="arc3,rad=0.1", lw=1))

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor="#D5E8D4", edgecolor="#82B366", label="Inputs"),
        mpatches.Patch(facecolor="#DAE8FC", edgecolor="#6C8EBF", label="Relations"),
        mpatches.Patch(facecolor="#FFF2CC", edgecolor="#D6B656", label="Outputs"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9)

    ax.set_xlim(-1.5, 8)
    y_min = min(p[1] for p in positions.values()) - 1
    y_max = max(p[1] for p in positions.values()) + 1
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{system.name} -- Dependency Graph", fontsize=14, fontweight="bold")
    fig.tight_layout()

    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save}")
    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig
