"""
Project-local RSQ registry.

Lets you work on RSQs in an isolated project store (separate SQLite DB),
access the global registry in read-only mode, and promote RSQs to global
when they're ready.

Usage
-----
    import anvil

    # One-shot: get a Project object
    proj = anvil.project("heat_exchanger_study", path="./my_project")

    # Register RSQs to the project
    proj.push(my_relation, domain="hx")

    # Access project RSQs
    proj.R.my_relation(...)
    proj.list()

    # Access global RSQs too
    anvil.R.isentropic_ratios(...)  # unaffected

    # Promote to global when done
    proj.promote("my_relation")

    # Context manager: routes anvil.push() to project automatically
    with anvil.project("heat_exchanger_study") as proj:
        @anvil.relation(domain="hx")
        def wall_resistance(L, k, A):
            return {"R_wall": L / (k * A)}
        # wall_resistance is registered to project, not global
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from anvil.registry.store import Store
from anvil.registry.namespace import Namespace
from anvil.registry.loader import load_rsq


class Project:
    """
    An isolated RSQ workspace with its own store.

    Reads from project store first, falls back to global store.
    Writes always go to project store.
    """

    def __init__(self, name: str, path: Optional[str] = None):
        self.name = name
        if path is None:
            path = os.getcwd()
        db_dir = Path(path) / ".anvil"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / f"project_{name}.db"

        self._store = Store(db_path)
        self._path = Path(path)

        # Namespaces for project RSQs
        self.R = Namespace("R")
        self.S = Namespace("S")
        self.Q = Namespace("Q")
        self._refresh_namespaces()

        print(f"  Project '{name}' opened  ({db_path})")

    def _refresh_namespaces(self):
        self.R._clear()
        self.S._clear()
        self.Q._clear()
        for record in self._store.get_all():
            try:
                obj = load_rsq(record, self._store)
            except Exception:
                continue
            n = record["name"]
            d = record.get("domain", "")
            if record["type"] == "R":
                self.R._register(n, obj, d)
            elif record["type"] == "S":
                self.S._register(n, obj, d)
            elif record["type"] == "Q":
                self.Q._register(n, obj, d)

    def push(self, obj, name=None, domain="", version="0.0.1",
             description="", author="", tags=None, tests=None, depends=None):
        """Register an RSQ to this project."""
        from anvil.quantity import Quantity as _Q
        from anvil.relation import Relation as _R
        from anvil.system import System as _S
        from anvil.registry.loader import (
            source_from_function, source_from_quantity, source_from_system
        )
        import inspect

        if isinstance(obj, _Q):
            rsq_type, n = "Q", name or obj.name or "unnamed_quantity"
            source = source_from_quantity(obj, n)
            description = description or obj.desc
        elif isinstance(obj, _S):
            rsq_type, n = "S", name or obj.name
            source = source_from_system(obj)
        elif isinstance(obj, _R):
            rsq_type, n = "R", name or obj.name
            source = source_from_function(obj.func)
            description = description or obj.desc
        elif callable(obj):
            rsq_type, n = "R", name or obj.__name__
            source = source_from_function(obj)
            description = description or (obj.__doc__ or "").strip()
        else:
            raise TypeError(f"Cannot register {type(obj).__name__}.")

        metadata = {}
        if rsq_type == "R" and callable(obj):
            fn = obj.func if isinstance(obj, _R) else obj
            sig = inspect.signature(fn)
            metadata["inputs"] = {
                pname: {"desc": "", **({"default": param.default}
                         if param.default is not inspect.Parameter.empty else {})}
                for pname, param in sig.parameters.items()
            }

        self._store.put(
            name=n, rsq_type=rsq_type, source=source, domain=domain,
            version=version, description=description, author=author,
            metadata=metadata, tests=tests or {}, tags=tags or [],
            depends=depends or [], origin="project",
        )
        self._refresh_namespaces()
        print(f"  [{self.name}] Registered '{n}' ({rsq_type})"
              f" in domain '{domain or '(root)'}'.")

    def list(self, domain=None, rsq_type=None):
        """List RSQs in this project."""
        records = self._store.get_all(rsq_type=rsq_type, domain=domain)
        if not records:
            print(f"  Project '{self.name}' is empty.")
            return []
        by_type = {"R": [], "S": [], "Q": []}
        for r in records:
            by_type.get(r["type"], []).append(r)
        labels = {"R": "Relations", "S": "Systems", "Q": "Quantities"}
        print(f"\n  Project: {self.name}  ({self._path})")
        for t in ["R", "S", "Q"]:
            items = by_type[t]
            if not items:
                continue
            print(f"\n  {labels[t]} ({len(items)}):")
            for r in items:
                d = f"  [{r['domain']}]" if r["domain"] else ""
                print(f"    {r['name']:30s}{d}")
                if r["description"]:
                    print(f"      {r['description'][:70]}")
        print(f"\n  Total: {len(records)} RSQs")
        return records

    def search(self, keyword):
        """Search project RSQs."""
        records = self._store.search(keyword)
        if not records:
            print(f"  No results for '{keyword}' in project '{self.name}'.")
            return []
        for r in records:
            tags = f"  [{', '.join(r['tags'][:3])}]" if r["tags"] else ""
            print(f"  [{r['type']}] {r['name']:30s}{tags}")
        print(f"\n  {len(records)} result(s)")
        return records

    def remove(self, name):
        """Remove an RSQ from this project."""
        self._store.remove(name)
        self._refresh_namespaces()
        print(f"  [{self.name}] Removed '{name}'.")

    def promote(self, name, overwrite=False):
        """
        Promote a project RSQ to the global registry.

        Parameters
        ----------
        name : str
            RSQ name to promote.
        overwrite : bool
            If True, overwrite existing global RSQ with same name.
        """
        from anvil import registry as _reg
        record = self._store.get(name)
        if not record:
            raise KeyError(f"'{name}' not found in project '{self.name}'.")

        global_store = _reg._get_store()
        existing = global_store.get(name)
        if existing and not overwrite:
            raise ValueError(
                f"'{name}' already exists in global registry "
                f"(v{existing['version']}). Pass overwrite=True to replace."
            )

        global_store.put(
            name=record["name"], rsq_type=record["type"],
            source=record["source"], domain=record["domain"],
            version=record["version"], description=record["description"],
            author=record["author"], metadata=record["metadata"],
            tests=record["tests"], tags=record["tags"],
            depends=record["depends"], origin="local",
        )
        _reg._rebuild_namespaces()
        print(f"  '{name}' promoted from project '{self.name}' to global registry.")

    def promote_all(self, overwrite=False):
        """Promote all project RSQs to the global registry."""
        records = self._store.get_all()
        for r in records:
            self.promote(r["name"], overwrite=overwrite)

    # === Context manager ===

    def __enter__(self):
        _set_active_project(self)
        return self

    def __exit__(self, *_):
        _set_active_project(None)

    def __repr__(self):
        n = self._store.count()
        return f"<Project '{self.name}': {n} RSQs at {self._path}>"


# ============================================================
# Active project context (routes anvil.push to project store)
# ============================================================

_active_project: Optional[Project] = None


def _set_active_project(proj):
    global _active_project
    _active_project = proj


def get_active_project() -> Optional[Project]:
    return _active_project
