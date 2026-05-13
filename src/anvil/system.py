"""
System: wire Quantities and Relations into a solvable problem.

Internally, the solver workspace uses raw SI floats for speed and
compatibility with SciPy. On output, values are packaged back as
Quantities with auto-detected units from the active unit system.
"""

from __future__ import annotations
import copy
import time
import inspect
import ast
import textwrap
import warnings as _warnings_mod
import numpy as np
from typing import Optional
from anvil.quantity import Quantity, Q
from anvil.relation import Relation
from anvil.units import Dim
from anvil import units as _u


class ValidationError(Exception):
    pass


class Result:
    """Solve results with auto-formatting and data export."""

    def __init__(self, data, system_name="", inputs=None):
        self._data = data
        self._system_name = system_name
        self._inputs = inputs or set()

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def to_dict(self, si=False):
        """Export as plain dict. si=True gives SI floats, otherwise display values."""
        out = {}
        for k, q in self._data.items():
            if isinstance(q, Quantity):
                out[k] = float(q._si_value) if si else float(q.value)
            else:
                out[k] = q
        return out

    def to_csv(self, path, si=False):
        """Export results to a CSV file."""
        d = self.to_dict(si=si)
        with open(path, "w") as f:
            f.write("variable,value,unit\n")
            for k, v in d.items():
                q = self._data[k]
                unit = q.unit if isinstance(q, Quantity) else ""
                f.write(f"{k},{v},{unit}\n")

    def to_json(self, path=None, si=False):
        """Export results to JSON. Returns string if path is None."""
        import json
        d = self.to_dict(si=si)
        out = {}
        for k, v in d.items():
            q = self._data[k]
            unit = q.unit if isinstance(q, Quantity) else ""
            out[k] = {"value": v, "unit": unit}
        s = json.dumps(out, indent=2)
        if path:
            with open(path, "w") as f:
                f.write(s)
        return s

    def summary(self, keys=None):
        show = keys or list(self._data.keys())
        print(f"\n{'-' * 56}")
        if self._system_name:
            print(f"  {self._system_name} -- results")
        print(f"{'-' * 56}")

        input_keys = [k for k in show if k in self._inputs and k in self._data]
        output_keys = [k for k in show if k not in self._inputs and k in self._data]

        if input_keys:
            for name in input_keys:
                self._print_qty(name)
        if input_keys and output_keys:
            print(f"  {'':24s}  ---")
        if output_keys:
            for name in output_keys:
                self._print_qty(name)

        print(f"{'-' * 56}")

    def _print_qty(self, name):
        q = self._data[name]
        if isinstance(q, Quantity):
            unit = q.unit
            val = q.value
            if val is None:
                print(f"  {name:24s}  undefined")
            elif isinstance(val, np.ndarray) and val.ndim > 0:
                print(f"  {name:24s}  array{val.shape} {unit}")
            else:
                v = float(val)
                ustr = f" {unit}" if unit else ""
                if v == 0:
                    print(f"  {name:24s}  0{ustr}")
                elif abs(v) >= 1e6 or (abs(v) < 0.01 and abs(v) > 0):
                    print(f"  {name:24s}  {v:.4e}{ustr}")
                elif abs(v) >= 100:
                    print(f"  {name:24s}  {v:.2f}{ustr}")
                elif abs(v) >= 1:
                    print(f"  {name:24s}  {v:.4f}{ustr}")
                else:
                    print(f"  {name:24s}  {v:.6f}{ustr}")
        elif isinstance(q, dict):
            print(f"  {name:24s}  {{...}} ({len(q)} entries)")
        else:
            print(f"  {name:24s}  {q}")

    def _repr_html_(self):
        rows = []
        for k, q in self._data.items():
            is_input = k in self._inputs
            bg = "#f8f8f8" if is_input else "#ffffff"
            role = "input" if is_input else "output"
            if isinstance(q, Quantity):
                val = q.value
                unit = q.unit
                if val is None:
                    vstr = "—"
                elif isinstance(val, np.ndarray):
                    vstr = f"array{val.shape}"
                else:
                    v = float(val)
                    vstr = (f"{v:.4e}" if abs(v) >= 1e6 or (0 < abs(v) < 0.01)
                            else f"{v:.4f}" if abs(v) >= 1 else f"{v:.6f}")
            elif isinstance(q, dict):
                vstr, unit = f"{{...}} ({len(q)} entries)", ""
            else:
                vstr, unit = str(q), ""
            rows.append(
                f'<tr style="background:{bg}">'
                f'<td style="padding:4px 10px;color:#555;font-size:.85em">{role}</td>'
                f'<td style="padding:4px 10px;font-weight:bold">{k}</td>'
                f'<td style="padding:4px 10px;text-align:right;font-family:monospace">{vstr}</td>'
                f'<td style="padding:4px 10px;color:#666">{unit}</td>'
                f'</tr>'
            )
        title = self._system_name or "Result"
        return (
            f'<div style="font-family:sans-serif">'
            f'<div style="font-weight:bold;margin-bottom:6px">{title}</div>'
            f'<table style="border-collapse:collapse;font-size:.9em">'
            f'<thead><tr style="border-bottom:2px solid #ddd">'
            f'<th style="padding:4px 10px;text-align:left;color:#888">role</th>'
            f'<th style="padding:4px 10px;text-align:left">variable</th>'
            f'<th style="padding:4px 10px;text-align:right">value</th>'
            f'<th style="padding:4px 10px;text-align:left">unit</th>'
            f'</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div>'
        )


class SweepResult:
    """Parametric sweep results with auto-formatting."""

    def __init__(self, param, values, results, system_name="", param_unit=""):
        self._param = param
        self._values = values
        self._results = results
        self._system_name = system_name
        self._param_unit = param_unit
        self._output_keys = []
        valid = [r for r in results if r is not None]
        if valid:
            self._output_keys = [k for k in valid[0].keys() if k != param]

    def __getitem__(self, key):
        if key == self._param:
            return np.array([float(v) for v in self._values])
        return np.array([
            float(r[key]._si_value) if (r is not None and isinstance(r[key], Quantity))
            else (float(r[key]) if r is not None else np.nan)
            for r in self._results
        ])

    def to_dict(self, si=False):
        """Export sweep as dict of arrays."""
        out = {self._param: np.array([float(v) for v in self._values])}
        for key in self._output_keys:
            vals = []
            for r in self._results:
                if r is None:
                    vals.append(np.nan)
                elif key in r:
                    q = r[key]
                    vals.append(float(q._si_value) if (si and isinstance(q, Quantity)) else
                                float(q.value) if isinstance(q, Quantity) else float(q))
                else:
                    vals.append(np.nan)
            out[key] = np.array(vals)
        return out

    def to_csv(self, path, si=False, outputs=None):
        """Export sweep to CSV."""
        d = self.to_dict(si=si)
        cols = [self._param] + (outputs or self._output_keys)
        with open(path, "w") as f:
            f.write(",".join(cols) + "\n")
            for i in range(len(self._values)):
                row = []
                for c in cols:
                    if c in d:
                        row.append(str(d[c][i]) if i < len(d[c]) else "")
                    else:
                        row.append("")
                f.write(",".join(row) + "\n")

    def to_json(self, path=None, si=False):
        """Export sweep to JSON. Returns string if path is None."""
        import json
        d = self.to_dict(si=si)
        out = {k: v.tolist() if hasattr(v, 'tolist') else list(v) for k, v in d.items()}
        s = json.dumps(out, indent=2)
        if path:
            with open(path, "w") as f:
                f.write(s)
        return s

    def summary(self, outputs=None):
        show = outputs or self._output_keys[:6]
        w = 14

        print(f"\n{'-' * 70}")
        if self._system_name:
            print(f"  {self._system_name} -- sweep over {self._param}")
        print(f"{'-' * 70}")

        headers = [self._param] + list(show)
        units_row = [self._param_unit]
        valid = [r for r in self._results if r is not None]
        for key in show:
            if valid and key in valid[0]:
                q = valid[0][key]
                units_row.append(q.unit if isinstance(q, Quantity) and q.unit else "")
            else:
                units_row.append("")

        print("  " + "".join(f"{h:>{w}s}" for h in headers))
        if any(units_row):
            print("  " + "".join(
                f"{'[' + u + ']' if u else '':>{w}s}" for u in units_row
            ))
        print("  " + "-" * (w * len(headers)))

        for i, r in enumerate(self._results):
            if r is None:
                row = f"  {float(self._values[i]):>{w}.4g}"
                row += "".join(f"{'(failed)':>{w}s}" for _ in show)
            else:
                row = f"  {float(self._values[i]):>{w}.4g}"
                for key in show:
                    if key in r:
                        q = r[key]
                        v = float(q.value) if isinstance(q, Quantity) else float(q)
                        row += f"{v:>{w}.4g}"
            print(row)
        print(f"{'-' * 70}")

    def _repr_html_(self):
        show = self._output_keys[:8]
        cols = [self._param] + list(show)
        valid = [r for r in self._results if r is not None]

        # Get units row
        units = {self._param: self._param_unit or ""}
        for key in show:
            if valid and key in valid[0]:
                q = valid[0][key]
                units[key] = q.unit if isinstance(q, Quantity) and q.unit else ""

        def fmt(v):
            if v != v:  # nan
                return "—"
            v = float(v)
            return (f"{v:.4e}" if abs(v) >= 1e5 or (0 < abs(v) < 0.01)
                    else f"{v:.4g}")

        hdr = "".join(
            f'<th style="padding:4px 10px;text-align:right">{c}</th>' for c in cols
        )
        unit_row = "".join(
            f'<td style="padding:2px 10px;text-align:right;color:#888;font-size:.8em">'
            f'[{units.get(c,"")}]</td>' if units.get(c) else
            f'<td></td>' for c in cols
        )
        data_rows = []
        for i, r in enumerate(self._results):
            v0 = fmt(float(self._values[i]))
            row = f'<td style="padding:3px 10px;text-align:right;font-weight:bold">{v0}</td>'
            for key in show:
                if r is None:
                    row += '<td style="padding:3px 10px;text-align:right;color:#aaa">failed</td>'
                elif key in r:
                    q = r[key]
                    val = float(q._si_value) if isinstance(q, Quantity) else float(q)
                    row += f'<td style="padding:3px 10px;text-align:right">{fmt(val)}</td>'
                else:
                    row += '<td></td>'
            data_rows.append(f'<tr>{row}</tr>')

        title = (f"{self._system_name} — sweep over {self._param}"
                 if self._system_name else f"Sweep over {self._param}")
        return (
            f'<div style="font-family:sans-serif">'
            f'<div style="font-weight:bold;margin-bottom:6px">{title}</div>'
            f'<table style="border-collapse:collapse;font-size:.9em">'
            f'<thead>'
            f'<tr style="border-bottom:1px solid #ddd">{hdr}</tr>'
            f'<tr style="border-bottom:2px solid #ddd">{unit_row}</tr>'
            f'</thead>'
            f'<tbody>{"".join(data_rows)}</tbody>'
            f'</table></div>'
        )


class SensitivityResult:
    """Normalized sensitivity: how much each output changes per unit change in each input."""

    def __init__(self, data, system_name=""):
        self._data = data
        self._system_name = system_name

    def __getitem__(self, output_name):
        return self._data[output_name]

    def to_dict(self):
        return dict(self._data)

    def top(self, output, n=5):
        if output not in self._data:
            return []
        return sorted(self._data[output].items(), key=lambda x: abs(x[1]), reverse=True)[:n]

    def summary(self, outputs=None):
        targets = outputs or list(self._data.keys())
        print(f"\n{'=' * 60}")
        if self._system_name:
            print(f"  {self._system_name} -- Sensitivity Analysis")
        print(f"{'=' * 60}")
        print(f"  (normalized: 1.0 = 1% input change -> 1% output change)")
        for out in targets:
            if out not in self._data:
                continue
            ranked = sorted(self._data[out].items(), key=lambda x: abs(x[1]), reverse=True)
            print(f"\n  {out}:")
            for inp, sens in ranked:
                if abs(sens) < 1e-10:
                    continue
                bar = '#' * min(int(abs(sens) * 20), 40)
                sign = '+' if sens > 0 else '-'
                print(f"    {inp:20s}  {sign}{abs(sens):.4f}  {bar}")
        print(f"{'=' * 60}")

    def _repr_html_(self):
        outputs = list(self._data.keys())
        inputs = sorted(self._data.keys())
        rows = []
        for out in outputs:
            if out not in self._data:
                continue
            ranked = sorted(self._data[out].items(), key=lambda x: abs(x[1]), reverse=True)
            # One row per (output, input) pair
            for i, (inp, sens) in enumerate(ranked):
                if abs(sens) < 1e-10:
                    continue
                bar_w = min(int(abs(sens) * 60), 120)
                color = "#2E75B6" if sens > 0 else "#C0392B"
                out_cell = (f'<td rowspan="{len(ranked)}" style="padding:4px 10px;'
                            f'vertical-align:top;font-weight:bold">{out}</td>' if i == 0 else "")
                rows.append(
                    f'<tr>'
                    f'{out_cell}'
                    f'<td style="padding:4px 10px">{inp}</td>'
                    f'<td style="padding:4px 10px;text-align:right;font-family:monospace">'
                    f'{"+" if sens > 0 else ""}{sens:.4f}</td>'
                    f'<td style="padding:4px 10px">'
                    f'<div style="background:{color};height:10px;width:{bar_w}px;'
                    f'border-radius:2px;opacity:0.7"></div></td>'
                    f'</tr>'
                )
        title = f"{self._system_name} — Sensitivity" if self._system_name else "Sensitivity"
        return (
            f'<div style="font-family:sans-serif">'
            f'<div style="font-weight:bold;margin-bottom:6px">{title}</div>'
            f'<div style="color:#666;font-size:.85em;margin-bottom:8px">'
            f'Normalized: 1.0 = 1% input → 1% output</div>'
            f'<table style="border-collapse:collapse;font-size:.9em">'
            f'<thead><tr style="border-bottom:2px solid #ddd">'
            f'<th style="padding:4px 10px;text-align:left">output</th>'
            f'<th style="padding:4px 10px;text-align:left">input</th>'
            f'<th style="padding:4px 10px;text-align:right">sensitivity</th>'
            f'<th style="padding:4px 10px">bar</th>'
            f'</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div>'
        )


class OptimizeResult:
    """Result from System.optimize()."""

    def __init__(self, best_result, best_x, best_fun, design_var_names,
                 success, message, nit, nfev, system_name=""):
        self._result = best_result
        self.x = best_x           # {var_name: value in declared display units}
        self.fun = best_fun       # objective value at optimum
        self.success = success
        self.message = message
        self.nit = nit
        self.nfev = nfev
        self._system_name = system_name
        self._design_var_names = design_var_names

    def __getitem__(self, key):
        if self._result is None:
            raise KeyError(f"No successful solve in optimization; cannot get '{key}'")
        return self._result[key]

    def __contains__(self, key):
        return self._result is not None and key in self._result

    def summary(self):
        print(f"\n{'=' * 56}")
        if self._system_name:
            print(f"  {self._system_name} -- optimization")
        status = "CONVERGED" if self.success else "NOT CONVERGED"
        print(f"  Status   : {status}  ({self.message})")
        print(f"  Evals    : {self.nfev}   Iterations: {self.nit}")
        print(f"  Objective: {self.fun:.6g}")
        print(f"{'=' * 56}")
        print(f"  Design variables at optimum:")
        for name, val in self.x.items():
            print(f"    {name:22s}  {val:.6g}")
        if self._result is not None:
            print()
            self._result.summary()

    def _repr_html_(self):
        status_color = "#2a7a2a" if self.success else "#cc3333"
        status_text = "&#10003; Converged" if self.success else "&#10007; Not converged"
        rows = [
            f'<tr><td colspan="2" style="padding:4px 10px;color:{status_color};'
            f'font-weight:bold">{status_text} &mdash; {self.nfev} evaluations, '
            f'{self.nit} iterations</td></tr>',
            f'<tr style="background:#eef6ee">'
            f'<td style="padding:4px 10px;color:#555;font-size:.85em">objective</td>'
            f'<td style="padding:4px 10px;text-align:right;font-family:monospace;'
            f'font-weight:bold">{self.fun:.6g}</td></tr>',
        ]
        for name, val in self.x.items():
            rows.append(
                f'<tr><td style="padding:4px 10px;color:#555;font-size:.85em">'
                f'design: <b>{name}</b></td>'
                f'<td style="padding:4px 10px;text-align:right;font-family:monospace">'
                f'{val:.6g}</td></tr>'
            )
        title = (f"{self._system_name} &mdash; Optimization"
                 if self._system_name else "Optimization Result")
        return (
            f'<div style="font-family:sans-serif">'
            f'<div style="font-weight:bold;margin-bottom:6px">{title}</div>'
            f'<table style="border-collapse:collapse;font-size:.9em">'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div>'
        )


class System:
    """
    A solvable engineering problem.

    Solvers:
        "forward"       -- Single pass (no coupled loops)
        "gauss_seidel"  -- Fixed-point iteration with relaxation
        "newton"        -- Newton-Raphson on coupled residual
    """

    def __init__(self, name, desc=""):
        self.name = name
        self.desc = desc
        self._quantities = {}
        self._relations = []
        self._validated = False
        self._exec_order = None
        self._has_cycles = False
        self._history = []
        self._output_meta = {}
        self._dof_warned = False  # suppress repeat DOF warnings within same session

    def copy(self):
        """
        Deep copy this System. Safe for independent .set() and .solve().

        Usage:
            nozzle = anvil.S.rocket_nozzle
            my_nozzle = nozzle.copy()
            my_nozzle.set(P0=10e6)
        """
        new = System(self.name, self.desc)
        for k, q in self._quantities.items():
            new_q = Quantity._raw(q._si_value, q._dim, name=q.name,
                                   unit_hint=q._unit_hint)
            new_q.role = q.role
            new_q.desc = q.desc
            new_q.bounds = q.bounds
            new._quantities[k] = new_q
        new._relations = list(self._relations)
        new._validated = False
        new._dof_warned = self._dof_warned
        return new

    def add(self, name=None, value=None, unit="", *, desc="", bounds=None, role="", **quantities):
        """
        Add Quantities to the system.

        Classic style:
            sys.add("T", 300, "K")
            sys.add("T", Q(300, "K"))

        New kwargs style (name inferred from keyword):
            sys.add(T=300*K, P=101325*Pa)
            sys.add(T=Q(300, "K"), P=Q(101325, "Pa"))
        """
        if name is not None:
            return self._add_single(name, value, unit, desc=desc, bounds=bounds, role=role)
        elif quantities:
            for k, v in quantities.items():
                if isinstance(v, Quantity):
                    if not v.name:
                        v.name = k
                    self._quantities[k] = v
                elif v is not None:
                    self._quantities[k] = Quantity(v, "", name=k)
                else:
                    self._quantities[k] = Quantity(None, "", name=k)
            self._validated = False
            return self
        return self

    def _add_single(self, name, value=None, unit="", *, desc="", bounds=None, role=""):
        """Internal: add one named quantity."""
        if isinstance(value, Quantity):
            q = value
            if not q.name:
                q.name = name
        elif value is not None:
            q = Quantity(value, unit, name=name, desc=desc, bounds=bounds, role=role)
        else:
            q = Quantity(None, unit, name=name, desc=desc, bounds=bounds, role=role)
        self._quantities[name] = q
        self._validated = False
        return self

    def set(self, **kwargs):
        """
        Override quantity values without re-declaring units.

        Bare number: keeps existing unit and metadata.
        Q() object: overrides value, unit, and everything.

        Usage:
            system.set(P0=8e6)                # keeps Pa
            system.set(P0=Q(1000, "psi"))      # switches to psi
            system.set(P0=8e6, T0=3200)        # multiple at once
        """
        for name, value in kwargs.items():
            if name not in self._quantities:
                raise KeyError(
                    f"'{name}' not in system. Use .add() for new quantities. "
                    f"Available: {', '.join(self._quantities.keys())}"
                )
            existing = self._quantities[name]
            if isinstance(value, Quantity):
                value.name = value.name or name
                value.role = value.role or existing.role
                value.desc = value.desc or existing.desc
                self._quantities[name] = value
            else:
                scale = 1.0
                if existing._unit_hint and existing._unit_hint in _u.db._forward:
                    scale = _u.db._forward[existing._unit_hint][0]
                self._quantities[name] = Quantity._raw(
                    float(value) * scale, existing._dim,
                    name=name, unit_hint=existing._unit_hint,
                )
                self._quantities[name].role = existing.role
                self._quantities[name].desc = existing.desc
                self._quantities[name].bounds = existing.bounds
        self._validated = False
        return self

    def _inherit_defaults(self, other_system):
        """Import another System's quantities as defaults (only new ones)."""
        for name, q in other_system._quantities.items():
            if name not in self._quantities:
                new_q = Quantity._raw(q._si_value, q._dim, name=name,
                                       unit_hint=q._unit_hint)
                new_q.role = q.role
                new_q.desc = q.desc
                new_q.bounds = q.bounds
                self._quantities[name] = new_q
        self._validated = False

    def use(self, func_or_relation, map=None, **kw):
        """
        Add a computation to the system.

        Accepts:
            - A plain Python function
            - A Relation object
            - A System object (auto-wrapped, inherits defaults)
            - A string name (looked up from the registry)

        Optional:
            map={"func_param": "workspace_name"}
                Renames inputs so a generic Relation fits the system's naming.
        """
        if isinstance(func_or_relation, str):
            from anvil.registry import _get_store
            from anvil.registry.loader import load_rsq
            store = _get_store()
            record = store.get(func_or_relation)
            if record is None:
                raise KeyError(
                    f"'{func_or_relation}' not found in registry.\n"
                    f"  Use anvil.fetch('{func_or_relation}') to download it,\n"
                    f"  or anvil.registry.search('{func_or_relation}') to find similar RSQs."
                )
            obj = load_rsq(record, store)
            if isinstance(obj, System):
                self._inherit_defaults(obj)
                rel = obj.as_relation()
            elif isinstance(obj, Relation):
                rel = obj
            elif callable(obj):
                rel = Relation(obj, **kw)
            else:
                raise TypeError(f"Registry entry '{func_or_relation}' is not callable.")
        elif isinstance(func_or_relation, System):
            self._inherit_defaults(func_or_relation)
            rel = func_or_relation.as_relation()
        elif isinstance(func_or_relation, Relation):
            rel = func_or_relation
        elif callable(func_or_relation):
            rel = Relation(func_or_relation, **kw)
        else:
            raise TypeError(f"Expected function, Relation, System, or string name -- "
                            f"got {type(func_or_relation).__name__}")

        if map:
            rel = self._apply_map(rel, map)

        self._relations.append(rel)
        self._validated = False
        return self

    def _apply_map(self, rel, name_map):
        """Wrap a Relation with renamed inputs."""
        original_func = rel.func
        reverse_map = {v: k for k, v in name_map.items()}

        new_inputs = []
        for inp in rel._inputs:
            new_inputs.append(name_map.get(inp, inp))

        def mapped_func(**kwargs):
            func_kwargs = {}
            for k, v in kwargs.items():
                func_kwargs[reverse_map.get(k, k)] = v
            return original_func(**func_kwargs)

        new_rel = Relation(name=f"{rel.name}[mapped]")
        new_rel.func = mapped_func
        new_rel._inputs = new_inputs
        new_rel._outputs = list(rel._outputs)
        new_rel._defaults = dict(rel._defaults)
        new_rel.tags = list(rel.tags)
        new_rel.desc = rel.desc
        return new_rel

    # === Validation ===

    def validate(self):
        errors, warnings = [], []
        available = {k: "user" for k in self._quantities}

        # NaN/Inf check on inputs
        for k, q in self._quantities.items():
            if q._si_value is not None:
                si = q._si_value
                if isinstance(si, np.ndarray):
                    if not np.all(np.isfinite(si)):
                        errors.append(f"'{k}' contains NaN or Inf.")
                elif not np.isfinite(float(si)):
                    errors.append(f"'{k}' is NaN or Inf (value: {si}).")

        for rel in self._relations:
            if not rel._outputs:
                _discover_outputs(rel, self._quantities, self._relations)
            for out in rel._outputs:
                if out in available and available[out] != "user":
                    errors.append(f"'{out}' produced by both '{available[out]}' and '{rel.name}'.")
                available[out] = rel.name

        for rel in self._relations:
            for inp in rel._inputs:
                if inp not in available and inp not in rel._defaults:
                    errors.append(f"'{rel.name}' needs '{inp}' -- not provided.")

        for k, q in self._quantities.items():
            if q.bounds and q._si_value is not None and not q.in_bounds():
                warnings.append(f"'{k}' outside bounds {q.bounds}.")

        if errors:
            raise ValidationError("Validation failed:\n" + "\n".join(f"  * {e}" for e in errors))

        # === DOF analysis (warnings only — never blocks execution) ===
        # Suppress after first validation so sweep/iterative solvers aren't noisy.
        if not self._dof_warned:
            all_rel_outputs = set()
            all_rel_inputs = set()
            for rel in self._relations:
                all_rel_outputs.update(rel._outputs)
                all_rel_inputs.update(rel._inputs)

            # Declared variables that a relation will overwrite — silent in forward pass,
            # intentional in iterative (initial guess). Warn so the user knows.
            overwritten = [k for k in self._quantities if k in all_rel_outputs]
            if overwritten:
                msg = (f"  WARNING: variable(s) declared via .add() are also produced by a "
                       f"relation — declared value will be overwritten after solve: {overwritten}\n"
                       f"    (This is intentional for iterative initial guesses; for forward "
                       f"systems it may indicate a naming mismatch.)")
                print(msg)
                warnings.append(f"Overwritten declared variables: {overwritten}")

            # Declared variables used by no relation at all (not an input, not an output)
            isolated = [k for k in self._quantities
                        if k not in all_rel_inputs and k not in all_rel_outputs]
            if isolated and self._relations:
                msg = (f"  WARNING: variable(s) declared via .add() are not used by any "
                       f"relation: {isolated}\n"
                       f"    (Possible typo or unused parameter.)")
                print(msg)
                warnings.append(f"Unused declared variables: {isolated}")

            self._dof_warned = True

        self._build_exec_order()
        self._validated = True
        return warnings

    def _build_exec_order(self):
        n = len(self._relations)
        if n == 0:
            self._exec_order, self._has_cycles = [], False
            return

        out_map = {}
        for i, r in enumerate(self._relations):
            for o in r._outputs:
                out_map[o] = i

        deps = {i: set() for i in range(n)}
        for i, r in enumerate(self._relations):
            for inp in r._inputs:
                if inp in out_map and out_map[inp] != i:
                    deps[i].add(out_map[inp])

        in_deg = {i: len(deps[i]) for i in range(n)}
        queue = [i for i in range(n) if in_deg[i] == 0]
        order = []
        while queue:
            nd = queue.pop(0)
            order.append(nd)
            for i in range(n):
                if nd in deps[i]:
                    in_deg[i] -= 1
                    if in_deg[i] == 0:
                        queue.append(i)

        self._exec_order = order if len(order) == n else list(range(n))
        self._has_cycles = len(order) != n

    # === Solving ===

    def solve(self, method=None, max_iter=100, rtol=1e-6, atol=1e-10,
              relaxation=1.0, monitor=False, verbose=False):
        if not self._validated:
            self.validate()
        if method is None:
            method = "gauss_seidel" if self._has_cycles else "forward"

        ws = {}
        for k, q in self._quantities.items():
            if q._si_value is not None:
                ws[k] = float(q._si_value)

        self._output_meta = {}
        self._history = []
        t0 = time.monotonic()

        if method == "forward":
            self._forward(ws)
        elif method == "gauss_seidel":
            self._iterate(ws, max_iter, rtol, relaxation, monitor, verbose, t0)
        elif method == "newton":
            self._newton(ws, max_iter, rtol, verbose)
        else:
            raise ValueError(f"Unknown solver: '{method}'")

        data = {}
        for key, val in ws.items():
            if isinstance(val, (dict, list)):
                data[key] = val  # complex output types stored as-is
            elif key in self._quantities:
                q = self._quantities[key]
                data[key] = Quantity._raw(val, q._dim, name=key, unit_hint=q._unit_hint)
            elif key in self._output_meta:
                dim, du = self._output_meta[key]
                data[key] = Quantity._raw(val, dim, name=key, unit_hint=du)
            else:
                data[key] = Quantity._raw(val, Dim.dimensionless(), name=key)

        return Result(data, self.name, inputs=set(self._quantities.keys()))

    def _forward(self, ws):
        for idx in self._exec_order:
            rel = self._relations[idx]

            # Build two kwarg sets: one with Quantities (for unit propagation),
            # one with raw floats (fallback when function can't handle Quantities)
            qty_kwargs = {}
            float_kwargs = {}
            for inp in rel._inputs:
                if inp in ws:
                    v = ws[inp]
                    if isinstance(v, (dict, list)):
                        qty_kwargs[inp] = v
                        float_kwargs[inp] = v
                    else:
                        fv = float(v)
                        float_kwargs[inp] = fv
                        # Attach known dimension so arithmetic propagates units
                        if inp in self._quantities:
                            q = self._quantities[inp]
                            qty_kwargs[inp] = Quantity._raw(fv, q._dim, unit_hint=q._unit_hint)
                        elif inp in self._output_meta:
                            dim, hint = self._output_meta[inp]
                            qty_kwargs[inp] = Quantity._raw(fv, dim, unit_hint=hint)
                        else:
                            qty_kwargs[inp] = fv  # no dim known; pass as float
                elif inp in rel._defaults:
                    qty_kwargs[inp] = rel._defaults[inp]
                    float_kwargs[inp] = rel._defaults[inp]

            # Try Quantity-aware call for unit propagation; fall back to floats
            # Cache per-relation whether Qty call succeeds to skip overhead next iter
            if getattr(rel, '_qty_compatible', None) is not False:
                try:
                    result = rel.func(**qty_kwargs)
                    rel._qty_compatible = True
                except Exception:
                    rel._qty_compatible = False
                    result = rel.func(**float_kwargs)
            else:
                result = rel.func(**float_kwargs)

            if isinstance(result, dict):
                for k, v in result.items():
                    if isinstance(v, Quantity):
                        ws[k] = float(v._si_value)
                        self._output_meta[k] = (v._dim, v._unit_hint)
                    elif isinstance(v, (dict, list)):
                        ws[k] = v
                    else:
                        ws[k] = float(v)
            elif len(rel._outputs) == 1:
                # Single-value convenience: relation has exactly one known output,
                # returned as a bare scalar rather than a dict.
                v = result
                if isinstance(v, Quantity):
                    ws[rel._outputs[0]] = float(v._si_value)
                    self._output_meta[rel._outputs[0]] = (v._dim, v._unit_hint)
                elif isinstance(v, (dict, list)):
                    ws[rel._outputs[0]] = v
                else:
                    ws[rel._outputs[0]] = float(v)
            else:
                # result is not a dict and not a single-output scalar
                raise RuntimeError(
                    f"Relation '{rel.name}' returned {type(result).__name__!r} "
                    f"instead of a dict. Relations must return a dict mapping "
                    f"output names to values.\n"
                    f"  Example: return {{\"thrust\": Q(F, \"N\")}}\n"
                    f"  Got: {result!r:.100}"
                )

    def _iterate(self, ws, max_iter, rtol, relaxation, monitor, verbose, t0):
        for iteration in range(max_iter):
            prev = dict(ws)
            self._forward(ws)

            if relaxation < 1.0:
                for k in ws:
                    if k in prev and not isinstance(ws[k], (dict, list)):
                        ws[k] = relaxation * ws[k] + (1 - relaxation) * prev[k]

            max_change = 0.0
            for k in ws:
                if k in prev:
                    v_now, v_prev = ws[k], prev[k]
                    if isinstance(v_now, (dict, list)) or isinstance(v_prev, (dict, list)):
                        continue
                    if not np.isfinite(v_now):
                        raise RuntimeError(f"NaN/Inf in '{k}' at iteration {iteration}.")
                    if v_prev != 0:
                        change = abs(v_now - v_prev) / (abs(v_prev) + 1e-30)
                        max_change = max(max_change, change)

            if monitor:
                elapsed = time.monotonic() - t0
                self._history.append({
                    "iteration": iteration, "residual": max_change,
                    "wallclock": elapsed, "variables": dict(ws),
                })
                print(f"  iter {iteration:4d}  |  residual = {max_change:.4e}"
                      f"  |  t = {elapsed:.3f}s")
            elif verbose:
                print(f"  iter {iteration:4d}  |  residual = {max_change:.4e}")
            if max_change < rtol:
                if monitor or verbose:
                    print(f"  converged in {iteration + 1} iterations")
                return

        raise RuntimeError(f"Not converged after {max_iter} iters (residual: {max_change:.2e}).")

    def _newton(self, ws, max_iter, rtol, verbose):
        from anvil.solvers import solve_nonlinear

        all_out, all_in = set(), set()
        for r in self._relations:
            all_out.update(r._outputs)
            all_in.update(r._inputs)
        coupled = sorted(all_out & all_in)

        if not coupled:
            self._forward(ws)
            return

        nit = [0]

        def residual(x):
            for i, v in enumerate(coupled):
                ws[v] = x[i]
            self._forward(ws)
            r = np.array([ws[v] - x[i] for i, v in enumerate(coupled)])
            nit[0] += 1
            if verbose and (nit[0] == 1 or nit[0] % 10 == 0):
                print(f"  NR iter {nit[0]:4d}  |  residual = {np.linalg.norm(r):.4e}")
            return r

        x0 = np.array([ws.get(v, 1.0) for v in coupled])
        x_sol = solve_nonlinear(residual, x0, tol=rtol, maxiter=max_iter)
        if verbose:
            print(f"  NR converged in {nit[0]} evaluations")
        for i, v in enumerate(coupled):
            ws[v] = x_sol[i]
        self._forward(ws)

    # === Composition ===

    def as_relation(self, inputs=None, outputs=None, name=None):
        """Wrap this System as a Relation for use in larger Systems."""
        if not self._validated:
            try:
                self.validate()
            except Exception:
                pass

        sys_copy = self.copy()
        inp = inputs or [k for k in sys_copy._quantities]
        out = outputs or []
        if not out:
            all_out = set()
            for r in sys_copy._relations:
                all_out.update(r._outputs)
            out = sorted(all_out - set(sys_copy._quantities.keys()))
            if not out:
                out = sorted(all_out)

        def _fn(**kwargs):
            for k, v in kwargs.items():
                if k in sys_copy._quantities:
                    q = sys_copy._quantities[k]
                    sys_copy._quantities[k] = Quantity._raw(
                        v, q._dim, name=k, unit_hint=q._unit_hint)
                    sys_copy._quantities[k].role = q.role
            sys_copy._validated = False
            result = sys_copy.solve()
            out_dict = {}
            for k in out:
                if k in result:
                    r = result[k]
                    if isinstance(r, Quantity):
                        out_dict[k] = r
                    elif isinstance(r, (dict, list)):
                        out_dict[k] = r
                    else:
                        out_dict[k] = float(r)
            return out_dict

        rel = Relation(name=name or self.name)
        rel.func = _fn
        rel._inputs = inp
        rel._outputs = out
        return rel

    # === Explicit solver convenience methods ===

    def solve_forward(self, **kw):
        """Single-pass forward solve. Use for acyclic systems."""
        return self.solve(method="forward", **kw)

    def solve_gauss_seidel(self, relaxation=1.0, max_iter=100, rtol=1e-6,
                           monitor=False, verbose=False, **kw):
        """Gauss-Seidel fixed-point iteration. Use for weakly coupled systems."""
        return self.solve(method="gauss_seidel", relaxation=relaxation,
                          max_iter=max_iter, rtol=rtol,
                          monitor=monitor, verbose=verbose, **kw)

    def solve_newton(self, max_iter=100, rtol=1e-6, verbose=False, **kw):
        """Newton-Raphson on coupled residual. Use for strongly coupled systems."""
        return self.solve(method="newton", max_iter=max_iter,
                          rtol=rtol, verbose=verbose, **kw)

    # === Sweep ===

    def sweep(self, param_name, values, skip_errors=False, parallel=1,
              warm_start=False, **solve_kwargs):
        """
        Sweep a parameter over a range of values.

        Parameters
        ----------
        param_name : str
            Name of the quantity to vary.
        values : array-like
            Values in the same unit originally declared.
        skip_errors : bool
            If True, failed points are recorded as None instead of raising.
        parallel : int
            Number of parallel workers (>1 enables concurrent evaluation).
            Uses thread-based concurrency — best for numpy/scipy workloads.
            For pure-Python heavy loops, set parallel=1.
        warm_start : bool
            If True, carry computed outputs from the previous successful solve
            as initial values for the next point. Useful for iterative systems
            (gauss_seidel / newton) sweeping over a slowly varying parameter —
            reduces iteration count per point. Incompatible with parallel > 1.
        **solve_kwargs
            Passed to solve() (method, relaxation, max_iter, verbose, ...).
        """
        values = np.asarray(values, dtype=np.float64)
        if param_name not in self._quantities:
            available = ', '.join(self._quantities.keys())
            raise KeyError(
                f"Cannot sweep '{param_name}' -- not in system.\n"
                f"  Available inputs: {available}\n"
                f"  Hint: use system.add('{param_name}', value) first."
            )
        if warm_start and parallel > 1:
            raise ValueError(
                "warm_start=True is incompatible with parallel > 1 "
                "(solve order is undefined in parallel mode)."
            )

        orig = self._quantities[param_name]
        if orig._unit_hint and orig._unit_hint in _u.db._forward:
            scale = _u.db._forward[orig._unit_hint][0]
        else:
            scale = 1.0

        param_unit = orig._unit_hint or ""

        if parallel > 1:
            return self._sweep_parallel(
                param_name, values, orig, scale, param_unit,
                skip_errors, parallel, solve_kwargs
            )

        results = []
        values_used = []
        for i, v in enumerate(values):
            self._quantities[param_name] = Quantity._raw(
                float(v) * scale, orig._dim, name=param_name,
                unit_hint=orig._unit_hint)
            self._validated = False
            try:
                result = self.solve(**solve_kwargs)
                results.append(result)
                values_used.append(v)
                if warm_start:
                    # Carry solved values forward as initial guess for next point.
                    # Only update declared quantities (the ones iterated on in GS/Newton).
                    for k, q_res in result._data.items():
                        if k in self._quantities and k != param_name:
                            if isinstance(q_res, Quantity) and q_res._si_value is not None:
                                self._quantities[k]._si_value = q_res._si_value
            except RuntimeError as e:
                if skip_errors:
                    _warnings_mod.warn(
                        f"Sweep point {param_name}={v:.4g} failed: {e}", stacklevel=2
                    )
                    results.append(None)
                    values_used.append(v)
                else:
                    self._quantities[param_name] = orig
                    self._validated = False
                    raise RuntimeError(
                        f"Sweep failed at {param_name} = {v} (point {i+1}/{len(values)}).\n"
                        f"  {e}\n"
                        f"  Tip: pass skip_errors=True to collect partial results, or "
                        f"adjust solver settings: sweep('{param_name}', values, "
                        f"method='gauss_seidel', relaxation=0.5, max_iter=200)"
                    ) from e

        self._quantities[param_name] = orig
        self._validated = False
        return SweepResult(param_name, values_used, results, self.name, param_unit=param_unit)

    def _sweep_parallel(self, param_name, values, orig, scale, param_unit,
                        skip_errors, n_workers, solve_kwargs):
        """Run sweep concurrently using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def solve_one(v):
            sys_copy = self.copy()
            sys_copy._quantities[param_name] = Quantity._raw(
                float(v) * scale, orig._dim, name=param_name,
                unit_hint=orig._unit_hint)
            sys_copy._validated = False
            return sys_copy.solve(**solve_kwargs)

        results_map = {}  # v_index -> result | None | exception
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = {pool.submit(solve_one, float(v)): i
                       for i, v in enumerate(values)}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results_map[idx] = fut.result()
                except Exception as e:
                    if skip_errors:
                        _warnings_mod.warn(
                            f"Sweep point {param_name}={values[idx]:.4g} failed: {e}",
                            stacklevel=3
                        )
                        results_map[idx] = None
                    else:
                        raise RuntimeError(
                            f"Sweep failed at {param_name} = {values[idx]:.4g}.\n  {e}"
                        ) from e

        ordered_results = [results_map[i] for i in range(len(values))]
        return SweepResult(param_name, list(values), ordered_results,
                           self.name, param_unit=param_unit)

    # === Sensitivity analysis ===

    def sensitivity(self, outputs=None, step=0.01):
        """
        Compute sensitivity of outputs to each input.

        Uses central finite differences: d(output)/d(input) * (input/output).
        Returns a dict: {output_name: {input_name: sensitivity_value}}.
        Sensitivity > 1 means output changes faster than input (amplified).

        Parameters
        ----------
        outputs : list of str, optional
            Which outputs to analyze. Default: all computed outputs.
        step : float
            Fractional perturbation (default 1%).
        """
        baseline = self.copy().solve()

        all_outs = set()
        for r in self._relations:
            all_outs.update(r._outputs)
        computed = sorted(all_outs - set(self._quantities.keys()))
        targets = outputs or computed

        base_vals = {k: float(baseline[k]._si_value) if isinstance(baseline[k], Quantity)
                     else float(baseline[k]) for k in targets
                     if k in baseline and isinstance(baseline[k], Quantity)}

        sensitivities = {out: {} for out in targets}

        for inp_name, q in self._quantities.items():
            if q._si_value is None or q._si_value == 0:
                continue

            val = float(q._si_value)
            delta = abs(val) * step
            if delta == 0:
                continue

            sys_plus = self.copy()
            sys_plus._quantities[inp_name] = Quantity._raw(
                val + delta, q._dim, name=inp_name, unit_hint=q._unit_hint)
            try:
                r_plus = sys_plus.solve()
            except Exception:
                continue

            sys_minus = self.copy()
            sys_minus._quantities[inp_name] = Quantity._raw(
                val - delta, q._dim, name=inp_name, unit_hint=q._unit_hint)
            try:
                r_minus = sys_minus.solve()
            except Exception:
                continue

            for out in targets:
                if out not in r_plus or out not in r_minus:
                    continue
                if not isinstance(r_plus[out], Quantity):
                    continue
                v_plus = float(r_plus[out]._si_value)
                v_minus = float(r_minus[out]._si_value)
                base = base_vals.get(out, 0)
                if base != 0:
                    dout = (v_plus - v_minus) / (2 * delta)
                    sensitivities[out][inp_name] = dout * val / base
                else:
                    sensitivities[out][inp_name] = 0.0

        return SensitivityResult(sensitivities, self.name)

    # === Optimization ===

    def optimize(self, objective, design_vars, minimize=True,
                 method="differential_evolution", seed=None,
                 tol=1e-6, maxiter=1000, verbose=False, **solver_kwargs):
        """
        Optimize a system output by varying design variables.

        Parameters
        ----------
        objective : str
            Name of the output Quantity to optimize (must appear in solve result).
        design_vars : dict
            {var_name: (lo, hi)} — bounds in the declared unit of each variable.
            Variable must already exist in the system via .add().
        minimize : bool
            True (default) = minimize; False = maximize.
        method : str
            Global (no gradient):
                "differential_evolution" (default) — robust, good for ≤20 vars
                "dual_annealing"                   — fast for noisy landscapes
                "shgo"                             — tight bounds, constrained problems
                "basinhopping"                     — smooth multi-modal
            Gradient-based (faster, needs smooth objective):
                "L-BFGS-B", "SLSQP", "Nelder-Mead"
        tol : float
            Convergence tolerance.
        maxiter : int
            Maximum optimizer iterations.
        verbose : bool
            Print progress every 25 evaluations.
        **solver_kwargs
            Passed to System.solve() for every evaluation
            (e.g. method="gauss_seidel", relaxation=0.7, max_iter=200).

        Returns
        -------
        OptimizeResult
            .x        — dict of design variable values at optimum (display units)
            .fun      — objective value at optimum
            .success  — bool
            .nfev     — total system solves performed
            [key]     — subscript access to any Result quantity at optimum

        Examples
        --------
        Maximize nozzle thrust by tuning exit area and chamber pressure:

            opt = nozzle.optimize(
                objective="thrust",
                design_vars={"Ae": (0.01, 0.20), "P0": (3e6, 10e6)},
                minimize=False,
                method="differential_evolution",
                maxiter=500,
                verbose=True,
            )
            opt.summary()
            print(opt["Isp"])   # any other result quantity at optimum
        """
        from anvil.solvers import minimize_global, minimize as _minimize_grad

        dv_names = list(design_vars.keys())
        scales = []
        si_bounds = []

        for name in dv_names:
            if name not in self._quantities:
                raise KeyError(
                    f"Design variable '{name}' not in system. "
                    f"Add it with .add('{name}', value, unit) first."
                )
            lo, hi = design_vars[name][0], design_vars[name][1]
            q = self._quantities[name]
            scale = 1.0
            if q._unit_hint and q._unit_hint in _u.db._forward:
                scale = _u.db._forward[q._unit_hint][0]
            scales.append((scale, q))
            si_bounds.append((float(lo) * scale, float(hi) * scale))

        sign = 1.0 if minimize else -1.0
        best = {"val": np.inf, "result": None}
        nfev = [0]

        def objective_fn(x_si):
            nfev[0] += 1
            sys_copy = self.copy()
            for i, name in enumerate(dv_names):
                scale, q = scales[i]
                sys_copy._quantities[name] = Quantity._raw(
                    float(x_si[i]), q._dim, name=name, unit_hint=q._unit_hint)
            sys_copy._validated = False
            try:
                result = sys_copy.solve(**solver_kwargs)
            except Exception as e:
                if verbose:
                    print(f"  [eval {nfev[0]}] solve failed: {e}")
                return 1e30

            if objective not in result:
                raise KeyError(
                    f"Objective '{objective}' not in solve result. "
                    f"Available: {list(result.keys())}"
                )
            obj_q = result[objective]
            obj_val = (float(obj_q._si_value) if isinstance(obj_q, Quantity)
                       else float(obj_q))
            signed_val = sign * obj_val

            if signed_val < best["val"]:
                best["val"] = signed_val
                best["result"] = result

            if verbose and nfev[0] % 25 == 0:
                print(f"  [eval {nfev[0]:4d}]  {objective} = {obj_val:.6g}")

            return signed_val

        global_methods = {"differential_evolution", "dual_annealing",
                          "shgo", "basinhopping"}
        if method in global_methods:
            opt = minimize_global(
                objective_fn, si_bounds, method=method,
                seed=seed, maxiter=maxiter, tol=tol, workers=1,
                verbose=verbose,
            )
        else:
            x0 = np.array([0.5 * (lo + hi) for lo, hi in si_bounds])
            opt = _minimize_grad(objective_fn, x0, method=method,
                                 bounds=si_bounds, tol=tol, maxiter=maxiter)

        best_x = {}
        for i, name in enumerate(dv_names):
            scale, _ = scales[i]
            best_x[name] = opt["x"][i] / scale

        return OptimizeResult(
            best_result=best["result"],
            best_x=best_x,
            best_fun=best["val"] * sign,
            design_var_names=dv_names,
            success=opt["success"],
            message=opt["message"],
            nit=opt.get("nit", 0),
            nfev=nfev[0],
            system_name=self.name,
        )

    # === Monitoring ===

    def history(self):
        """Get convergence history from last solve (requires monitor=True)."""
        return list(self._history)

    def __repr__(self):
        return f"System('{self.name}', {len(self._quantities)} vars, {len(self._relations)} relations)"

    def info(self):
        lines = [f"\nSystem: {self.name}", "  Inputs:"]
        for k, q in self._quantities.items():
            lines.append(f"    {k:20s}  {q}")
        lines.append("  Relations:")
        for r in self._relations:
            lines.append(f"    {r.name}")
        return "\n".join(lines)


# === Module-level helper ===

def _discover_outputs(rel, quantities, all_relations):
    """Discover output keys via AST inspection or runtime probing."""
    try:
        source = textwrap.dedent(inspect.getsource(rel.func))
        tree = ast.parse(source)
        keys = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
        if keys:
            rel._outputs = sorted(keys)
            return
    except Exception:
        pass

    kwargs = {}
    for inp in rel._inputs:
        if inp in quantities and quantities[inp]._si_value is not None:
            kwargs[inp] = float(quantities[inp]._si_value)
        elif inp in rel._defaults:
            kwargs[inp] = rel._defaults[inp]
        else:
            kwargs[inp] = 1.0
    try:
        result = rel.func(**kwargs)
        if isinstance(result, dict):
            rel._outputs = list(result.keys())
    except Exception:
        pass
