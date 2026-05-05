"""
Anvil Registry — manage RSQs (Relations, Systems, Quantities).

Usage:
    from anvil import registry

    registry.list()                       # all installed RSQs
    registry.list(domain="aero")          # filter by domain
    registry.list(type="R")               # only Relations
    registry.info("isentropic_flow")      # full details
    registry.search("shock")              # fuzzy search
    registry.export("isentropic_flow")    # print source code
    registry.remove("old_tool")           # uninstall
"""

from anvil.registry.store import Store
from anvil.registry.namespace import Namespace
from anvil.registry.loader import (
    load_rsq, source_from_function, source_from_quantity, source_from_system
)


# Global store and namespaces (root namespaces are lazy-loaded)
_store = None
R = Namespace("R", _is_root=True)
S = Namespace("S", _is_root=True)
Q_ns = Namespace("Q", _is_root=True)


def _get_store():
    global _store
    if _store is None:
        _store = Store()
    return _store


def _rebuild_namespaces():
    """Reload all RSQs from the store into the live namespaces."""
    store = _get_store()
    R._clear()
    S._clear()
    Q_ns._clear()

    for record in store.get_all():
        try:
            obj = load_rsq(record, store)
        except Exception:
            continue

        name = record["name"]
        domain = record.get("domain", "")

        if record["type"] == "R":
            R._register(name, obj, domain)
        elif record["type"] == "S":
            S._register(name, obj, domain)
        elif record["type"] == "Q":
            Q_ns._register(name, obj, domain)


# === User-facing commands ===

def list(type=None, domain=None, origin=None, tag=None):
    """List installed RSQs."""
    store = _get_store()
    records = store.get_all(rsq_type=type, domain=domain, origin=origin, tag=tag)

    if not records:
        print("  No RSQs found matching filters.")
        return []

    by_type = {"R": [], "S": [], "Q": []}
    for r in records:
        by_type.get(r["type"], []).append(r)

    type_labels = {"R": "Relations", "S": "Systems", "Q": "Quantities"}
    for t in ["R", "S", "Q"]:
        items = by_type[t]
        if not items:
            continue
        print(f"\n  {type_labels[t]} ({len(items)}):")
        for r in items:
            domain_str = f"  [{r['domain']}]" if r["domain"] else ""
            origin_str = f"  ({r['origin']})" if r["origin"] != "local" else ""
            print(f"    {r['name']:30s}{domain_str}{origin_str}")
            if r["description"]:
                print(f"      {r['description'][:70]}")

    print(f"\n  Total: {len(records)} RSQs")
    return records


def info(name):
    """Show detailed info about an RSQ."""
    store = _get_store()
    record = store.get(name)
    if not record:
        print(f"  '{name}' not found. Try: anvil.registry.search('{name}')")
        return None

    hl = "-" * 50
    print(f"\n  {hl}")
    print(f"  {record['name']}  ({record['type']})")
    print(f"  {hl}")
    print(f"  Domain:      {record['domain'] or '(none)'}")
    print(f"  Version:     {record['version']}")
    print(f"  Origin:      {record['origin']}")
    print(f"  Author:      {record['author'] or '(none)'}")
    if record["description"]:
        print(f"  Description: {record['description']}")
    if record["tags"]:
        print(f"  Tags:        {', '.join(record['tags'])}")
    if record["depends"]:
        print(f"  Depends on:  {', '.join(record['depends'])}")

    meta = record["metadata"]
    if meta.get("inputs"):
        print(f"  Inputs:")
        for k, v in meta["inputs"].items():
            default = f" = {v['default']}" if v.get("default") is not None else ""
            print(f"    {k}{default} -- {v.get('desc', '')}")
    if meta.get("outputs"):
        print(f"  Outputs:")
        for k, v in meta["outputs"].items():
            print(f"    {k} -- {v.get('desc', '')}")

    tests = record["tests"]
    if tests:
        print(f"  Tests:       {len(tests)} test case(s)")

    print(f"  {hl}")
    return record


def search(keyword):
    """Fuzzy search across all RSQs."""
    store = _get_store()
    records = store.search(keyword)
    if not records:
        print(f"  No results for '{keyword}'.")
        return []

    for r in records:
        tag_str = f"  [{', '.join(r['tags'][:3])}]" if r["tags"] else ""
        print(f"  [{r['type']}] {r['name']:30s}{tag_str}")
        if r["description"]:
            print(f"       {r['description'][:60]}")

    print(f"\n  {len(records)} result(s)")
    return records


def export(name):
    """Print the source code of an RSQ."""
    store = _get_store()
    record = store.get(name)
    if not record:
        print(f"  '{name}' not found.")
        return

    hl = "-" * 50
    print(f"# RSQ: {record['name']} (v{record['version']}, {record['type']})")
    print(f"# Domain: {record['domain']}")
    print(f"# Origin: {record['origin']}")
    print(f"# Tags: {', '.join(record['tags'])}")
    print(f"# {hl}")
    print(record["source"])


def remove(name, origin=None):
    """Remove an RSQ from the local registry."""
    store = _get_store()
    record = store.get(name)
    if not record:
        print(f"  '{name}' not found.")
        return
    store.remove(name, origin)
    _rebuild_namespaces()
    print(f"  Removed '{name}'.")


def register(obj, name=None, rsq_type=None, domain="", version="0.0.1",
             description="", author="", tags=None, tests=None, depends=None):
    """Register a local RSQ."""
    from anvil.quantity import Quantity
    from anvil.relation import Relation
    from anvil.system import System

    store = _get_store()

    if isinstance(obj, Quantity):
        rsq_type = rsq_type or "Q"
        name = name or obj.name or "unnamed_quantity"
        source = source_from_quantity(obj, name)
        description = description or obj.desc
    elif isinstance(obj, System):
        rsq_type = rsq_type or "S"
        name = name or obj.name
        source = source_from_system(obj)
    elif isinstance(obj, Relation):
        rsq_type = rsq_type or "R"
        name = name or obj.name
        source = source_from_function(obj.func)
        description = description or obj.desc
    elif callable(obj):
        rsq_type = rsq_type or "R"
        name = name or obj.__name__
        source = source_from_function(obj)
        description = description or (obj.__doc__ or "").strip()
    else:
        raise TypeError(f"Cannot register {type(obj).__name__}. "
                        f"Expected function, Relation, System, or Quantity.")

    metadata = {}
    if rsq_type == "R" and callable(obj):
        import inspect
        sig = inspect.signature(obj if not isinstance(obj, Relation) else obj.func)
        inputs = {}
        for pname, param in sig.parameters.items():
            inp = {"desc": ""}
            if param.default is not inspect.Parameter.empty:
                inp["default"] = param.default
            inputs[pname] = inp
        metadata["inputs"] = inputs

    existing = store.get(name)
    if existing and existing.get("origin") not in ("builtin",):
        import warnings
        warnings.warn(
            f"RSQ '{name}' already exists (v{existing['version']}, "
            f"origin='{existing['origin']}'). Overwriting. "
            f"Use anvil.update() to signal intentional overwrite.",
            UserWarning, stacklevel=3,
        )

    store.put(
        name=name, rsq_type=rsq_type, source=source,
        domain=domain, version=version, description=description,
        author=author, metadata=metadata, tests=tests or {},
        tags=tags or [], depends=depends or [], origin="local",
    )

    _rebuild_namespaces()
    print(f"  Registered '{name}' ({rsq_type}) in domain '{domain or '(root)'}'.")


def update(obj, name=None, domain=None, version=None, description=None,
           author=None, tags=None):
    """
    Update/overwrite an existing RSQ in the registry.

    Only the fields you pass are changed; omitted fields keep their
    current values from the store. If the RSQ doesn't exist yet, it
    is created with sensible defaults.

    Usage:
        anvil.update(my_improved_func, name="ideal_gas")
        anvil.update(my_func, domain="thermo.new", tags=["updated"])
    """
    from anvil.quantity import Quantity
    from anvil.relation import Relation
    from anvil.system import System

    store = _get_store()
    existing = store.get(name or getattr(obj, "name", None) or
                         getattr(obj, "__name__", "unnamed"))

    # Merge with existing metadata
    base = existing or {}
    eff_name = name or base.get("name") or getattr(obj, "name", None) or \
               getattr(obj, "__name__", "unnamed")
    eff_domain = domain if domain is not None else base.get("domain", "")
    eff_version = version if version is not None else base.get("version", "0.0.1")
    eff_desc = description if description is not None else base.get("description", "")
    eff_author = author if author is not None else base.get("author", "")
    eff_tags = tags if tags is not None else base.get("tags", [])

    register(obj, name=eff_name, domain=eff_domain, version=eff_version,
             description=eff_desc, author=eff_author, tags=eff_tags)
    print(f"  Updated '{eff_name}'.")


def count(rsq_type=None):
    """Count installed RSQs."""
    return _get_store().count(rsq_type)
