"""
Adapter layer: wrap external tools as Relations.

External tools (NASA CEA, Cantera, OpenFOAM, SU2, custom CLI programs)
are integrated through adapters. Each adapter declares:
    - inputs and their units
    - outputs and their units  
    - how to call the tool (Python function, CLI command, HTTP endpoint)

Usage:
    from anvil.adapter import Adapter

    # Python library adapter (e.g., Cantera, CoolProp)
    cea = Adapter("cea_rocket",
        backend="python",
        call=my_cea_wrapper,
        inputs={"fuel": {}, "oxidizer": {}, "OF": {}, "Pc": {"unit": "Pa"}},
        outputs={"Tc": {"unit": "K"}, "gamma": {}, "cstar": {"unit": "m/s"},
                 "Isp_vac": {"unit": "s"}},
        desc="NASA CEA rocket equilibrium performance",
    )

    # CLI adapter (e.g., SU2, custom Fortran codes)
    cfd = Adapter("su2_airfoil",
        backend="cli",
        command="SU2_CFD {config_file}",
        inputs={"mach": {}, "alpha_deg": {}, "Re": {}},
        outputs={"CL": {}, "CD": {}, "CM": {}},
        setup=my_config_writer,      # function that writes the config file
        parse=my_result_parser,       # function that reads the output
        desc="SU2 airfoil analysis",
    )

    # Use adapters exactly like any other Relation
    system.use(cea)
    system.use(cfd)
"""

from __future__ import annotations
import subprocess
import tempfile
import os
import inspect
from typing import Optional, Callable
from anvil.relation import Relation
from anvil.quantity import Quantity, Q
from anvil.units import db as _units_db


class Adapter(Relation):
    """
    Wrap an external tool as a Relation.

    Backends:
        "python"     -- call a Python function directly
        "cli"        -- run a command-line program
        "http"       -- call an HTTP endpoint (future)
        "shared_lib" -- call a shared library via ctypes (future)

    The adapter appears as a normal Relation to the System solver.
    """

    def __init__(self, name, backend="python", call=None, command=None,
                 inputs=None, outputs=None, setup=None, parse=None,
                 desc="", tags=None, timeout=60, cwd=None):
        """
        Parameters
        ----------
        name : str
            Adapter name.
        backend : str
            "python", "cli", "http", or "shared_lib".
        call : callable, optional
            For python backend: the function to call.
        command : str, optional
            For cli backend: command template with {input_name} placeholders.
        inputs : dict
            {name: {"unit": "Pa", "desc": "...", "default": ...}}
        outputs : dict
            {name: {"unit": "K", "desc": "..."}}
        setup : callable, optional
            For cli backend: function(inputs, workdir) that writes config files.
        parse : callable, optional
            For cli backend: function(workdir) -> dict of outputs.
        desc : str
            Description.
        tags : list
            Search tags.
        timeout : int
            Seconds before killing a CLI process.
        cwd : str
            Working directory for CLI commands.
        """
        self.name = name
        self.backend = backend
        self._call = call
        self._command = command
        self._input_spec = inputs or {}
        self._output_spec = outputs or {}
        self._setup = setup
        self._parse = parse
        self.desc = desc
        self.tags = tags or []
        self._timeout = timeout
        self._cwd = cwd

        # Build Relation-compatible interface
        self._inputs = list(self._input_spec.keys())
        self._outputs = list(self._output_spec.keys())
        self._defaults = {
            k: v["default"] for k, v in self._input_spec.items()
            if "default" in v
        }
        self._steps = []

        # Set up the callable
        if backend == "python":
            if call is None:
                raise ValueError("Python backend requires 'call' function.")
            self.func = self._wrap_python(call)
        elif backend == "cli":
            if command is None and setup is None:
                raise ValueError("CLI backend requires 'command' or 'setup'.")
            self.func = self._wrap_cli()
        else:
            raise ValueError(f"Backend '{backend}' not yet implemented. "
                             f"Available: 'python', 'cli'.")

    def _wrap_python(self, call):
        """Wrap a Python function with unit conversion on inputs/outputs."""
        input_spec = self._input_spec
        output_spec = self._output_spec

        def wrapped(**kwargs):
            # Convert inputs from SI to whatever unit the tool expects
            converted = {}
            for k, v in kwargs.items():
                if k in input_spec and "unit" in input_spec[k]:
                    tool_unit = input_spec[k]["unit"]
                    try:
                        tool_scale, _ = _units_db.lookup(tool_unit)
                        # v arrives as SI float; divide by tool unit's SI scale
                        converted[k] = v / tool_scale if tool_scale != 0 else v
                    except Exception:
                        converted[k] = v
                else:
                    converted[k] = v

            result = call(**converted)

            # Wrap outputs with units (tool returns in its declared unit → store as Q)
            wrapped_result = {}
            for k, v in result.items():
                if isinstance(v, Quantity):
                    wrapped_result[k] = v  # already a Q, use as-is
                elif k in output_spec and "unit" in output_spec[k]:
                    wrapped_result[k] = Q(v, output_spec[k]["unit"])
                else:
                    wrapped_result[k] = v

            return wrapped_result

        return wrapped

    def _wrap_cli(self):
        """Wrap a CLI tool: setup -> run -> parse."""
        command = self._command
        setup_fn = self._setup
        parse_fn = self._parse
        timeout = self._timeout
        cwd = self._cwd
        output_spec = self._output_spec

        def wrapped(**kwargs):
            # Create working directory
            workdir = cwd or tempfile.mkdtemp(prefix="anvil_")

            try:
                # Setup: write config files
                if setup_fn:
                    setup_fn(kwargs, workdir)

                # Run command
                if command:
                    cmd = command.format(**kwargs, workdir=workdir)
                    proc = subprocess.run(
                        cmd, shell=True, cwd=workdir,
                        capture_output=True, text=True,
                        timeout=timeout,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(
                            f"CLI adapter '{self.name}' failed (exit {proc.returncode}):\n"
                            f"  stdout: {proc.stdout[:200]}\n"
                            f"  stderr: {proc.stderr[:200]}"
                        )

                # Parse results
                if parse_fn:
                    result = parse_fn(workdir)
                else:
                    raise RuntimeError(f"CLI adapter '{self.name}' has no parse function.")

                # Wrap outputs with units
                wrapped_result = {}
                for k, v in result.items():
                    if k in output_spec and "unit" in output_spec[k]:
                        wrapped_result[k] = Q(v, output_spec[k]["unit"])
                    else:
                        wrapped_result[k] = v

                return wrapped_result

            finally:
                # Cleanup temp dir if we created it
                if cwd is None:
                    import shutil
                    shutil.rmtree(workdir, ignore_errors=True)

        return wrapped

    def info(self):
        lines = [f"Adapter: {self.name}  (backend: {self.backend})"]
        if self.desc:
            lines.append(f"  {self.desc}")
        if self._inputs:
            lines.append(f"  Inputs:")
            for k, spec in self._input_spec.items():
                unit = spec.get("unit", "")
                desc = spec.get("desc", "")
                default = spec.get("default", "")
                parts = [f"    {k}"]
                if unit: parts.append(f"[{unit}]")
                if default: parts.append(f"= {default}")
                if desc: parts.append(f"-- {desc}")
                lines.append(" ".join(parts))
        if self._outputs:
            lines.append(f"  Outputs:")
            for k, spec in self._output_spec.items():
                unit = spec.get("unit", "")
                desc = spec.get("desc", "")
                parts = [f"    {k}"]
                if unit: parts.append(f"[{unit}]")
                if desc: parts.append(f"-- {desc}")
                lines.append(" ".join(parts))
        if self.tags:
            lines.append(f"  Tags: {', '.join(self.tags)}")
        return "\n".join(lines)

    def __repr__(self):
        return f"Adapter('{self.name}', backend='{self.backend}')"
