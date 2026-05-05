"""
RSQ inspection and health-check.

Usage:
    import anvil
    anvil.check("rocket_nozzle")     # full inspection
    anvil.check("isentropic_ratios") # quick check on a Relation
"""

from __future__ import annotations


def check(name_or_obj, verbose=True):
    """
    Inspect an RSQ: verify it exists, is properly configured, and show its
    dependency tree, inputs, outputs, and a test run.

    Parameters
    ----------
    name_or_obj : str or Relation or System
        Registry name string, or a live object.
    verbose : bool
        Print the report (default True). Always returns the report dict.

    Returns
    -------
    dict with keys:
        "ok"          : bool  -- overall health
        "name"        : str
        "type"        : str   -- "R", "S", or "Q"
        "inputs"      : list
        "outputs"     : list
        "defaults"    : dict
        "depends"     : list  -- dependency names (for Systems)
        "tree"        : str   -- printable dependency tree
        "issues"      : list  -- problems found
        "test_result" : dict or None -- result of a test run (if possible)
    """
    from anvil.quantity import Quantity
    from anvil.relation import Relation
    from anvil.system import System
    from anvil.registry import _get_store
    from anvil.registry.loader import load_rsq
    from anvil.system import _discover_outputs

    report = {
        "ok": True,
        "name": "",
        "type": "",
        "domain": "",
        "description": "",
        "version": "",
        "inputs": [],
        "outputs": [],
        "defaults": {},
        "depends": [],
        "tree": "",
        "issues": [],
        "test_result": None,
    }

    issues = report["issues"]
    record = None
    obj = None

    # --- Resolve the object ---
    if isinstance(name_or_obj, str):
        store = _get_store()
        record = store.get(name_or_obj)
        if record is None:
            issues.append(f"NOT FOUND: '{name_or_obj}' is not in the registry.")
            report["ok"] = False
            report["name"] = name_or_obj
            if verbose:
                _print_report(report)
            return report

        report["name"] = record["name"]
        report["type"] = record["type"]
        report["domain"] = record.get("domain", "")
        report["description"] = record.get("description", "")
        report["version"] = record.get("version", "")
        report["depends"] = record.get("depends", [])

        try:
            obj = load_rsq(record, store)
        except Exception as e:
            issues.append(f"LOAD ERROR: {e}")
            report["ok"] = False

    elif isinstance(name_or_obj, System):
        obj = name_or_obj
        report["name"] = obj.name
        report["type"] = "S"
    elif isinstance(name_or_obj, Relation):
        obj = name_or_obj
        report["name"] = obj.name
        report["type"] = "R"
    elif isinstance(name_or_obj, Quantity):
        obj = name_or_obj
        report["name"] = obj.name or "(unnamed)"
        report["type"] = "Q"
    else:
        issues.append(f"Unknown type: {type(name_or_obj).__name__}")
        report["ok"] = False
        if verbose:
            _print_report(report)
        return report

    # --- Inspect based on type ---
    if isinstance(obj, System):
        _check_system(obj, report, record)
    elif isinstance(obj, Relation):
        _check_relation(obj, report)
    elif isinstance(obj, Quantity):
        _check_quantity(obj, report)

    if issues:
        report["ok"] = False

    if verbose:
        _print_report(report)

    return report


def _check_relation(rel, report):
    """Inspect a Relation."""
    from anvil.system import _discover_outputs

    report["inputs"] = list(rel._inputs)
    report["defaults"] = dict(rel._defaults)

    if not rel._outputs:
        # Try to discover
        try:
            _discover_outputs(rel, {}, [])
        except Exception:
            pass
    report["outputs"] = list(rel._outputs)

    if not report["inputs"]:
        report["issues"].append("WARNING: No inputs detected.")
    if not report["outputs"]:
        report["issues"].append("WARNING: No outputs detected. Function may not return a dict.")

    # Test run with defaults or dummy values
    try:
        kwargs = {}
        for inp in rel._inputs:
            if inp in rel._defaults:
                kwargs[inp] = rel._defaults[inp]
            else:
                kwargs[inp] = 1.0  # dummy
        result = rel.func(**kwargs)
        if isinstance(result, dict):
            report["test_result"] = {k: _simplify(v) for k, v in result.items()}
        else:
            report["test_result"] = result
    except Exception as e:
        report["issues"].append(f"TEST RUN FAILED: {e}")


def _check_system(sys, report, record=None):
    """Inspect a System."""
    from anvil.system import _discover_outputs

    # Inputs
    report["inputs"] = list(sys._quantities.keys())

    # Discover outputs from relations
    for rel in sys._relations:
        if not rel._outputs:
            try:
                _discover_outputs(rel, sys._quantities, sys._relations)
            except Exception:
                pass

    all_outputs = set()
    for rel in sys._relations:
        all_outputs.update(rel._outputs)
    report["outputs"] = sorted(all_outputs - set(sys._quantities.keys()))

    # Dependency tree
    tree_lines = [f"{sys.name} (System)"]
    tree_lines.append(f"  Inputs ({len(sys._quantities)}):")
    for k, q in sys._quantities.items():
        unit = q.unit if q.unit else ""
        val = f"{q.value}" if q._si_value is not None else "undefined"
        desc = f"  -- {q.desc}" if q.desc else ""
        tree_lines.append(f"    {k}: {val} {unit}{desc}")

    tree_lines.append(f"  Relations ({len(sys._relations)}):")
    for i, rel in enumerate(sys._relations):
        inp_str = ", ".join(rel._inputs[:5])
        out_str = ", ".join(rel._outputs[:5])
        tree_lines.append(f"    [{i+1}] {rel.name}")
        tree_lines.append(f"        in:  {inp_str}")
        tree_lines.append(f"        out: {out_str}")

    tree_lines.append(f"  Computed outputs ({len(report['outputs'])}):")
    for o in report["outputs"]:
        tree_lines.append(f"    {o}")

    # Dependencies (for registry systems)
    if report["depends"]:
        tree_lines.append(f"  Dependencies ({len(report['depends'])}):")
        store = None
        try:
            from anvil.registry import _get_store
            store = _get_store()
        except Exception:
            pass
        for dep in report["depends"]:
            status = "OK"
            if store:
                r = store.get(dep)
                if r is None:
                    status = "MISSING"
                    report["issues"].append(f"MISSING DEPENDENCY: '{dep}' not in registry.")
            tree_lines.append(f"    {dep} [{status}]")

    report["tree"] = "\n".join(tree_lines)

    # Validation check
    try:
        sys.validate()
    except Exception as e:
        report["issues"].append(f"VALIDATION: {e}")

    # Cycle detection
    if sys._has_cycles:
        all_out = set()
        all_in = set()
        for r in sys._relations:
            all_out.update(r._outputs)
            all_in.update(r._inputs)
        coupled = sorted(all_out & all_in)
        tree_lines.append(f"  Coupled variables: {', '.join(coupled)}")
        tree_lines.append(f"  Solver: gauss_seidel (iterative)")
        report["tree"] = "\n".join(tree_lines)

    # Test solve
    try:
        result = sys.copy().solve()
        report["test_result"] = {k: _simplify(result[k]) for k in list(result.keys())[:10]}
    except Exception as e:
        report["issues"].append(f"TEST SOLVE FAILED: {e}")


def _check_quantity(q, report):
    """Inspect a Quantity."""
    from anvil.quantity import Quantity
    report["inputs"] = []
    report["outputs"] = [report["name"]]
    if q._si_value is not None:
        report["test_result"] = {"value": float(q.value), "si": float(q.si),
                                  "unit": q.unit, "dim": str(q._dim)}
    else:
        report["issues"].append("WARNING: Quantity has no value.")


def _simplify(v):
    """Convert a value to a simple printable form."""
    from anvil.quantity import Quantity
    if isinstance(v, Quantity):
        return f"{v.value:.6g} {v.unit}" if v._si_value is not None else "undefined"
    try:
        return float(v)
    except Exception:
        return str(v)


def _print_report(report):
    """Pretty-print the check report."""
    ok_str = "PASS" if report["ok"] else "FAIL"
    badge = f"[{ok_str}]"

    print(f"\n{'=' * 60}")
    print(f"  anvil.check('{report['name']}')  {badge}")
    print(f"{'=' * 60}")

    if report["type"]:
        type_names = {"R": "Relation", "S": "System", "Q": "Quantity"}
        print(f"  Type:        {type_names.get(report['type'], report['type'])}")
    if report["domain"]:
        print(f"  Domain:      {report['domain']}")
    if report["description"]:
        print(f"  Description: {report['description']}")
    if report["version"]:
        print(f"  Version:     {report['version']}")

    if report["inputs"]:
        print(f"  Inputs:      {', '.join(report['inputs'][:10])}")
        if len(report["inputs"]) > 10:
            print(f"               ... and {len(report['inputs'])-10} more")
    if report["outputs"]:
        print(f"  Outputs:     {', '.join(report['outputs'][:10])}")
    if report["defaults"]:
        defs = ", ".join(f"{k}={v}" for k, v in list(report["defaults"].items())[:5])
        print(f"  Defaults:    {defs}")
    if report["depends"]:
        print(f"  Depends on:  {', '.join(report['depends'])}")

    if report["tree"]:
        print(f"\n  --- Dependency Tree ---")
        for line in report["tree"].split("\n"):
            print(f"  {line}")

    if report["test_result"]:
        print(f"\n  --- Test Run ---")
        tr = report["test_result"]
        if isinstance(tr, dict):
            for k, v in list(tr.items())[:10]:
                print(f"    {k}: {v}")
        else:
            print(f"    result: {tr}")

    if report["issues"]:
        print(f"\n  --- Issues ({len(report['issues'])}) ---")
        for issue in report["issues"]:
            print(f"    {issue}")
    else:
        print(f"\n  No issues found.")

    print(f"{'=' * 60}")
