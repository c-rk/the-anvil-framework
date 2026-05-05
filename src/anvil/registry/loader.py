"""
Load RSQ source code into live Python objects.

Each RSQ's source is a Python snippet that defines an `export` variable.
The loader executes it in a controlled namespace and extracts the result.
"""

import importlib


def load_rsq(record, store=None):
    """
    Load an RSQ record (from Store.get()) into a live object.

    Returns the exported object:
        - For type 'Q': a Quantity
        - For type 'R': a callable function wrapped in a Relation with outputs pre-set
        - For type 'S': a System (or a build function that returns one)
    """
    source = record["source"]
    rsq_type = record["type"]
    name = record["name"]

    # Build execution namespace with anvil imports available
    exec_ns = _build_namespace()

    # If this RSQ depends on others, load them first
    if record.get("depends") and store:
        for dep_name in record["depends"]:
            dep_record = store.get(dep_name)
            if dep_record:
                dep_obj = load_rsq(dep_record, store)
                exec_ns[dep_name] = dep_obj

    try:
        exec(source, exec_ns)
    except Exception as e:
        raise RuntimeError(f"Failed to load RSQ '{name}': {e}")

    # Extract the exported object
    if "export" not in exec_ns:
        if name in exec_ns and callable(exec_ns[name]):
            exec_ns["export"] = exec_ns[name]
        else:
            raise RuntimeError(f"RSQ '{name}' source must define an 'export' variable.")

    obj = exec_ns["export"]

    # For Relations: wrap as Relation with outputs pre-discovered from source
    if rsq_type == "R" and callable(obj) and not isinstance(obj, _get_relation_class()):
        from anvil.relation import Relation
        rel = Relation(obj, name=name)
        # Pre-discover outputs by parsing the source (since inspect.getsource fails for exec'd code)
        outputs = _extract_outputs_from_source(source)
        if outputs:
            rel._outputs = outputs
        return rel

    # For Systems: call the build function
    if rsq_type == "S" and callable(obj) and not hasattr(obj, "solve"):
        obj = obj()

    return obj


def _get_relation_class():
    """Lazy import to avoid circular imports."""
    from anvil.relation import Relation
    return Relation


def _extract_outputs_from_source(source):
    """Parse return dict keys from RSQ source code."""
    import ast
    try:
        tree = ast.parse(source)
        keys = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
        return sorted(keys) if keys else []
    except Exception:
        return []


def _build_namespace():
    """Build the execution namespace with standard anvil imports."""
    ns = {}
    try:
        from anvil.quantity import Quantity, Q
        from anvil.relation import Relation
        from anvil.system import System
        from anvil import solvers
        from anvil import units
        ns.update({
            "Q": Q, "Quantity": Quantity,
            "Relation": Relation,
            "System": System,
            "solvers": solvers,
            "units": units,
        })
    except ImportError:
        pass
    return ns


def source_from_function(func, rsq_type="R"):
    """
    Generate RSQ source code from a live Python function.

    Used when the user does anvil.push(my_function, ...).
    """
    import inspect
    import textwrap

    source = inspect.getsource(func)
    source = textwrap.dedent(source)

    # Strip decorator lines (@...) before the `def` keyword.
    # Python 3.12+ includes decorator source in co_firstlineno, so
    # inspect.getsource may return lines like "@anvil.relation(...)" which
    # would fail when exec'd without the original module in scope.
    lines = source.splitlines()
    stripped = []
    past_decorators = False
    for line in lines:
        stripped_line = line.strip()
        if not past_decorators:
            if stripped_line.startswith("def ") or stripped_line.startswith("async def "):
                past_decorators = True
                stripped.append(line)
            elif stripped_line.startswith("@"):
                continue  # skip decorator lines
            else:
                stripped.append(line)
        else:
            stripped.append(line)
    source = "\n".join(stripped)

    # Wrap in standard RSQ format
    lines = [
        "from anvil import Q, System, Relation",
        "from anvil import solvers",
        "",
        source,
        "",
        f"export = {func.__name__}",
    ]
    return "\n".join(lines)


def source_from_quantity(q, name):
    """Generate RSQ source code from a Quantity."""
    unit = q._unit_hint or ""
    val = q.si if not unit else q.value
    desc = q.desc or q.name or name
    return (
        f'from anvil import Q\n'
        f'export = Q({val}, "{unit}", name="{name}", desc="{desc}")\n'
    )


def source_from_system(system):
    """
    Generate a description of a System for storage.
    Note: full serialization of arbitrary Systems is complex.
    For now, stores a rebuild function.
    """
    # This is a simplified version -- full serialization would
    # need to capture all quantities and relation references
    lines = [
        "from anvil import Q, System",
        "from anvil import solvers",
        "",
        "def build():",
        f'    s = System("{system.name}")',
    ]
    for qname, q in system._quantities.items():
        unit = q._unit_hint or ""
        val = q.value
        desc = q.desc or ""
        if unit:
            lines.append(f'    s.add("{qname}", {val}, "{unit}", desc="{desc}")')
        else:
            lines.append(f'    s.add("{qname}", {val}, desc="{desc}")')

    for rel in system._relations:
        lines.append(f'    s.use("{rel.name}")')

    lines.append("    return s")
    lines.append("")
    lines.append("export = build")

    return "\n".join(lines)
