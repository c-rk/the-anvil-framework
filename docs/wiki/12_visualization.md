# Visualization

All visualization functions are in `anvil.viz`. They require `matplotlib`. Import is deferred — Anvil loads without matplotlib; only `viz.*` calls trigger the import.

```python
from anvil import viz
# or
import anvil
anvil.viz.convergence(system)
```

**Install matplotlib:** `pip install matplotlib`

---

## `viz.convergence(system, ax=None, show=True)`

Plot convergence residual vs iteration from a monitored solve.

```python
result = system.solve_gauss_seidel(monitor=True)
viz.convergence(system)
```

**Requirements:** System must have been solved with `monitor=True`. Data comes from `system.history()`.

**Plot:** Semi-log y-axis. Blue `o-` line. Green dashed line at `rtol=1e-6` (default convergence threshold).

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `system` | required | System with solve history |
| `ax` | None | Existing matplotlib Axes to draw on |
| `show` | True | Call `plt.show()` if True |

**Returns:** The Axes object (for further customization).

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
viz.convergence(system1, ax=axes[0], show=False)
viz.convergence(system2, ax=axes[1], show=False)
plt.tight_layout()
plt.show()
```

If `system.history()` returns an empty list (no `monitor=True` solve), prints:
```
  No monitoring data. Use system.solve(monitor=True).
```

**Convergence example output (from ex02_heat_exchanger.py):**

The HX system converges in 33 iterations with residual dropping from 2.0 to 6.9×10⁻¹¹. The convergence curve is exponentially decaying — typical for linear Gauss-Seidel on this system.

---

## `viz.variable_trace(system, variables, ax=None, show=True)`

Plot how specific variable values evolved across iterations.

```python
result = system.solve_gauss_seidel(monitor=True)
viz.variable_trace(system, ["T_hot_out", "T_cold_out"])
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `system` | required | System with solve history |
| `variables` | required | List of variable name strings |
| `ax` | None | Existing Axes |
| `show` | True | Call `plt.show()` |

**Plot:** Line plot of each variable's SI value vs iteration. Multiple lines on same axes with legend. Useful for seeing if a variable oscillates, converges monotonically, or diverges before convergence.

**Typical use:** Debugging Gauss-Seidel convergence. If a variable oscillates, try lower `relaxation`.

---

## `viz.sweep_plot(sweep_result, y=None, x_label=None, ax=None, show=True)`

Plot sweep results as line plots.

```python
sweep = sys.sweep("P0", np.linspace(5e6, 20e6, 30))
viz.sweep_plot(sweep, y=["thrust", "Isp", "mdot"])
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sweep_result` | required | `SweepResult` from `sys.sweep()` |
| `y` | None | Output names to plot; None = first 4 outputs |
| `x_label` | None | X-axis label; None = parameter name |
| `ax` | None | Axes (ignored if multiple outputs — creates figure internally) |
| `show` | True | Call `plt.show()` |

**Layout:**
- 1 output → single axes
- 2 outputs → 1×2 grid
- 3-4 outputs → 2×2 grid (last panel hidden if 3)
- N outputs → ceil(N/2) × 2 grid

Each subplot has:
- Title: output name
- X-label: parameter name
- Y-label: `"output_name [unit]"` (unit from first result)
- Figure title: `"system_name -- Sweep over param"`

```python
# Save instead of showing
fig = viz.sweep_plot(sweep, y=["thrust", "Isp"], show=False)
fig.savefig("sweep.png", dpi=150, bbox_inches="tight")
```

---

## `viz.dependency_graph(system, show=True, save=None)`

Plot the system's dependency graph: inputs → relations → outputs.

```python
sys.validate()   # must be validated first for edge detection
viz.dependency_graph(sys)
# or
viz.dependency_graph(sys, show=False, save="graph.png")
```

**Layout:**
- Left column: input quantities (green boxes)
- Middle column: relations (orange rounded boxes)
- Right column: computed outputs (blue boxes)
- Grey arrows: inputs → relations
- Blue arrows: relations → outputs

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `system` | required | System (will auto-validate if not done) |
| `show` | True | Call `plt.show()` |
| `save` | None | Filepath to save PNG (300 DPI) |

**Returns:** The Figure object.

**Known limitations:**
- Layout is purely positional (3 columns), not a proper graph layout algorithm. For systems with many relations, nodes may overlap.
- For large systems (>20 relations), output node positions compress and labels become unreadable at default figure size. Scale `figsize` manually using matplotlib after the call.
- Cycles are not visually distinguishable from acyclic connections.

**Example — rocket nozzle dependency graph:**

Input column (7 nodes): P0, T0, gamma, R_gas, A_throat, A_exit, P_amb

Relations column (8 nodes): nozzle_area_ratio → area_mach_supersonic → isentropic_ratios → exit_conditions → exit_velocity + choked_mass_flow → rocket_thrust → specific_impulse

Output column (12 nodes): area_ratio, M_exit, T0_T, P0_P, rho0_rho, T_exit, P_exit, a_exit, V_exit, mdot, thrust, Isp

---

## Saving Figures

All functions return an object (Axes or Figure) that can be used for further customization:

```python
import matplotlib.pyplot as plt

# Convergence
ax = viz.convergence(sys, show=False)
ax.set_title("Custom Title")
ax.set_ylim([1e-12, 1e1])
plt.savefig("convergence.png", dpi=150)

# Sweep
fig = viz.sweep_plot(sweep, y=["thrust", "Isp"], show=False)
plt.suptitle("Parametric Study — P0 variation", y=1.02)
fig.savefig("sweep_study.png", dpi=200, bbox_inches="tight")

# Dependency graph
fig = viz.dependency_graph(sys, show=False, save="system_graph.png")
```

---

## Jupyter Integration

In Jupyter notebooks, `show=True` (default) calls `plt.show()` inline. If you're working in Jupyter and want to embed plots in the notebook:

```python
import matplotlib
matplotlib.use("inline")   # or use %matplotlib inline magic
```

Then call `viz.*` with `show=True` (default) — figures display inline automatically.

For notebooks: the `SweepResult._repr_html_()`, `SensitivityResult._repr_html_()`, `Result._repr_html_()`, and `Q._repr_html_()` methods provide rich table/chart displays without matplotlib.
