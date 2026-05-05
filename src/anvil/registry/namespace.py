"""
Dot-accessible namespaces for RSQs.

Supports both flat and hierarchical access:
    anvil.R.isentropic_flow              # flat
    anvil.R.aero.isentropic_flow         # hierarchical (same object)

Namespaces are lazy-loaded: the first attribute access triggers
_rebuild_namespaces() if the namespace is still empty. This avoids
circular import issues during `import anvil`.
"""


class Namespace:
    """
    A dot-accessible namespace that supports both flat and hierarchical lookup.
    """

    def __init__(self, name="", _is_root=False):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_items", {})
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "_is_root", _is_root)
        object.__setattr__(self, "_initialized", False)

    def _register(self, name, obj, domain=""):
        """Register an object with flat name and optional domain hierarchy."""
        self._items[name] = obj

        if domain:
            parts = domain.split(".")
            ns = self
            for part in parts:
                if part not in ns._children:
                    ns._children[part] = Namespace(part)
                ns = ns._children[part]
            ns._items[name] = obj

        object.__setattr__(self, "_initialized", True)

    def _clear(self):
        """Clear all entries."""
        self._items.clear()
        self._children.clear()

    def _ensure_loaded(self):
        """Lazy load: trigger rebuild on first access if empty."""
        if not self._initialized and self._is_root:
            object.__setattr__(self, "_initialized", True)  # prevent recursion
            try:
                from anvil.registry import _rebuild_namespaces
                _rebuild_namespaces()
            except Exception as e:
                import warnings
                warnings.warn(f"Anvil registry rebuild failed: {e}", stacklevel=3)

    def __getattr__(self, key):
        # Lazy load on first access
        self._ensure_loaded()

        items = object.__getattribute__(self, "_items")
        if key in items:
            return items[key]

        children = object.__getattribute__(self, "_children")
        if key in children:
            return children[key]

        name = object.__getattribute__(self, "_name")
        available = sorted(list(items.keys()) + list(children.keys()))
        if available:
            suggestions = [a for a in available if key.lower() in a.lower()]
            hint = f" Did you mean: {', '.join(suggestions[:3])}?" if suggestions else ""
            raise AttributeError(
                f"'{key}' not found in {name or 'namespace'}.{hint}\n"
                f"  Use anvil.fetch('{key}') to download it, or "
                f"anvil.registry.search('{key}') to find related RSQs."
            )
        raise AttributeError(
            f"'{key}' not found. Registry is empty -- "
            f"use anvil.fetch([...]) to populate it."
        )

    def __dir__(self):
        """Support tab-completion in notebooks and REPLs."""
        self._ensure_loaded()
        return sorted(
            list(self._items.keys()) + list(self._children.keys())
        )

    def __repr__(self):
        self._ensure_loaded()
        name = object.__getattribute__(self, "_name")
        items = object.__getattribute__(self, "_items")
        children = object.__getattribute__(self, "_children")
        n_items = len(items)
        n_children = len(children)
        parts = []
        if n_items:
            parts.append(f"{n_items} entries")
        if n_children:
            parts.append(f"domains: {', '.join(sorted(children.keys()))}")
        detail = ", ".join(parts) if parts else "empty"
        return f"<{name or 'Namespace'}: {detail}>"

    def _list(self):
        """List all entries with their domains."""
        self._ensure_loaded()
        results = []
        for name, obj in sorted(self._items.items()):
            results.append(name)
        for domain, child in sorted(self._children.items()):
            for name in child._items:
                results.append(f"{domain}.{name}")
        return results
