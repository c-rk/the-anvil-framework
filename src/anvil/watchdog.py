"""
Monitoring watchdog for System solves.

Provides:
    - Pre-solve validation (completeness, unit consistency, bounds)
    - Runtime diagnostics (NaN/Inf detection with context)
    - Convergence rate estimation
    - Variable history tracking

Usage:
    result = system.solve(monitor=True)
    system.watchdog.report()               # print diagnostics
    system.watchdog.convergence_rate()      # estimated rate
    system.watchdog.stalled_variables()     # variables not converging
"""

from __future__ import annotations
import numpy as np
from typing import Optional


class Watchdog:
    """
    Monitors a System solve in real-time.

    Attached to a System. Collects data during iteration and provides
    post-solve diagnostics.
    """

    def __init__(self, system_name=""):
        self.system_name = system_name
        self._history = []           # list of snapshots per iteration
        self._nan_events = []        # (iteration, variable, context)
        self._converged = False
        self._iterations = 0
        self._final_residual = None
        self._method = ""
        self._wallclock = 0.0

    def reset(self):
        """Clear all monitoring data."""
        self._history.clear()
        self._nan_events.clear()
        self._converged = False
        self._iterations = 0
        self._final_residual = None
        self._wallclock = 0.0

    def record(self, iteration, workspace, residual, wallclock):
        """Record a snapshot of the solve state."""
        self._history.append({
            "iteration": iteration,
            "residual": residual,
            "wallclock": wallclock,
            "variables": dict(workspace),
        })
        self._iterations = iteration + 1
        self._final_residual = residual

    def check_nan(self, iteration, workspace):
        """
        Check for NaN/Inf in workspace. Returns (variable_name, value) or None.
        """
        for k, v in workspace.items():
            if not np.isfinite(v):
                # Capture context: what were the other variables?
                context = {kk: vv for kk, vv in workspace.items() if kk != k}
                self._nan_events.append({
                    "iteration": iteration,
                    "variable": k,
                    "value": v,
                    "context": context,
                })
                return k, v
        return None

    def mark_converged(self, converged, method, wallclock):
        self._converged = converged
        self._method = method
        self._wallclock = wallclock

    # === Post-solve diagnostics ===

    @property
    def history(self):
        return list(self._history)

    @property
    def residuals(self):
        """Array of residual values per iteration."""
        return np.array([h["residual"] for h in self._history])

    def variable_history(self, name):
        """Get the history of a specific variable across iterations."""
        vals = []
        for h in self._history:
            if name in h["variables"]:
                vals.append(h["variables"][name])
            else:
                vals.append(np.nan)
        return np.array(vals)

    def convergence_rate(self):
        """
        Estimate the convergence rate (ratio of successive residuals).
        Returns array of rates. Values < 1 mean converging.
        """
        res = self.residuals
        if len(res) < 2:
            return np.array([])
        rates = np.where(res[:-1] != 0, res[1:] / res[:-1], np.nan)
        return rates

    def stalled_variables(self, threshold=0.01):
        """
        Find variables that aren't changing between iterations.
        Returns list of (variable_name, final_change).
        """
        if len(self._history) < 2:
            return []
        last = self._history[-1]["variables"]
        prev = self._history[-2]["variables"]
        stalled = []
        for k in last:
            if k in prev:
                change = abs(last[k] - prev[k]) / (abs(prev[k]) + 1e-30)
                if change < threshold and change > 0:
                    stalled.append((k, change))
        return sorted(stalled, key=lambda x: x[1])

    def report(self):
        """Print a diagnostic report of the last solve."""
        print(f"\n{'=' * 56}")
        print(f"  Watchdog Report: {self.system_name}")
        print(f"{'=' * 56}")
        print(f"  Method:       {self._method}")
        print(f"  Iterations:   {self._iterations}")
        print(f"  Converged:    {self._converged}")
        if self._final_residual is not None:
            print(f"  Final resid:  {self._final_residual:.2e}")
        print(f"  Wall clock:   {self._wallclock:.4f} s")

        if self._nan_events:
            print(f"\n  NaN/Inf Events ({len(self._nan_events)}):")
            for ev in self._nan_events:
                print(f"    iter {ev['iteration']}: {ev['variable']} = {ev['value']}")

        rates = self.convergence_rate()
        if len(rates) > 2:
            avg_rate = np.nanmean(rates[-5:])  # average of last 5
            print(f"\n  Convergence rate (last 5 avg): {avg_rate:.4f}")
            if avg_rate > 1.0:
                print(f"    WARNING: diverging (rate > 1)")
            elif avg_rate > 0.95:
                print(f"    WARNING: slow convergence")

        stalled = self.stalled_variables()
        if stalled:
            print(f"\n  Stalled variables:")
            for name, change in stalled[:5]:
                print(f"    {name}: change = {change:.2e}")

        print(f"{'=' * 56}")
