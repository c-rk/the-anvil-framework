"""
Relation: a computation block with auto-detected inputs and outputs.

Three ways to create:

1. Just write a function (System.use() wraps it automatically):
    def isentropic(M, gamma=1.4):
        T_ratio = 1 + ((gamma - 1) / 2) * M**2
        P_ratio = T_ratio ** (gamma / (gamma - 1))
        return {"T_ratio": T_ratio, "P_ratio": P_ratio}

    system.use(isentropic)

2. Wrap explicitly for metadata:
    isen = Relation(isentropic, tags=["compressible", "aero"])

3. Group multiple functions into one block:
    nozzle_physics = Relation.block("nozzle_flow",
        steps=[area_ratio_fn, mach_from_area_fn, isentropic_fn],
        tags=["compressible", "nozzle"],
    )

Functions must:
    - Accept inputs as keyword arguments
    - Return a dict mapping output names to values
"""

from __future__ import annotations
import inspect
from typing import Optional, Callable
from dataclasses import dataclass, field

_REGISTRY = {}


@dataclass
class Relation:
    """
    A computation block: inputs → computation → outputs.

    Parameters
    ----------
    func : callable or None
        The computation function. Must accept kwargs, return dict.
    name : str
        Display name.
    tags : list of str
        Search tags for discoverability.
    desc : str
        Description.
    """
    func: Optional[Callable] = None
    name: str = ""
    tags: list = field(default_factory=list)
    desc: str = ""
    _inputs: list = field(default_factory=list)
    _outputs: list = field(default_factory=list)
    _defaults: dict = field(default_factory=dict)
    _steps: list = field(default_factory=list)

    def __init__(self, func=None, *, name="", tags=None, desc=""):
        if func is not None:
            self.func = func
            self.name = name or func.__name__
            self.desc = desc or (func.__doc__ or "").strip()
            self._analyze_function(func)
        else:
            self.func = None
            self.name = name
            self.desc = desc
            self._inputs = []
            self._outputs = []
            self._defaults = {}

        self.tags = tags or []
        self._steps = []
        self._qty_compatible = None  # None=unknown, True=yes, False=no

        # Register
        if self.name:
            _REGISTRY[self.name] = self

    def _analyze_function(self, func):
        """Extract inputs and defaults from function signature."""
        sig = inspect.signature(func)
        self._inputs = []
        self._defaults = {}
        for pname, param in sig.parameters.items():
            self._inputs.append(pname)
            if param.default is not inspect.Parameter.empty:
                self._defaults[pname] = param.default

        # Outputs are discovered on first call (from dict keys)
        self._outputs = []

    @classmethod
    def block(cls, name, steps, tags=None, desc=""):
        """
        Create a Relation from multiple functions executed in sequence.

        Each step function takes **kwargs from the shared workspace and
        returns a dict of outputs that get merged into the workspace.
        """
        rel = cls(name=name, tags=tags, desc=desc)
        rel._steps = list(steps)

        # Collect inputs and outputs from all steps
        all_outputs = set()
        all_inputs = set()
        for fn in steps:
            sig = inspect.signature(fn)
            for pname, param in sig.parameters.items():
                if pname not in all_outputs:
                    all_inputs.add(pname)
                if param.default is not inspect.Parameter.empty:
                    rel._defaults[pname] = param.default
            # Inspect source for output keys
            try:
                import ast, textwrap
                source = textwrap.dedent(inspect.getsource(fn))
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                all_outputs.add(k.value)
            except Exception:
                pass

        rel._inputs = sorted(all_inputs - all_outputs)
        rel._outputs = sorted(all_outputs)

        def _block_func(**kwargs):
            workspace = dict(kwargs)
            for step_fn in steps:
                sig = inspect.signature(step_fn)
                step_kwargs = {}
                for pname in sig.parameters:
                    if pname in workspace:
                        v = workspace[pname]
                        # Extract raw float from Quantity for solver compatibility
                        if hasattr(v, '_si_value'):
                            step_kwargs[pname] = float(v._si_value)
                        else:
                            step_kwargs[pname] = v
                    elif pname in rel._defaults:
                        step_kwargs[pname] = rel._defaults[pname]
                result = step_fn(**step_kwargs)
                if isinstance(result, dict):
                    workspace.update(result)
            # Return only outputs, extracting SI floats from any Quantities
            out = {}
            for k, v in workspace.items():
                if hasattr(v, '_si_value'):
                    out[k] = float(v._si_value)
                else:
                    out[k] = v
            return out

        rel.func = _block_func
        return rel

    @classmethod
    def from_function(cls, func):
        """Wrap a plain function as a Relation."""
        return cls(func)

    @property
    def inputs(self):
        return list(self._inputs)

    @property
    def outputs(self):
        return list(self._outputs)

    def __call__(self, **kwargs):
        """Call the underlying function."""
        # Fill defaults
        for k, v in self._defaults.items():
            if k not in kwargs:
                kwargs[k] = v

        result = self.func(**kwargs)

        # Discover outputs on first call
        if isinstance(result, dict) and not self._outputs:
            self._outputs = list(result.keys())

        return result

    def __repr__(self):
        return f"Relation('{self.name}')"

    def info(self):
        lines = [f"Relation: {self.name}"]
        if self._inputs:
            lines.append(f"  Inputs:  {', '.join(self._inputs)}")
        if self._outputs:
            lines.append(f"  Outputs: {', '.join(self._outputs)}")
        if self.tags:
            lines.append(f"  Tags:    {', '.join(self.tags)}")
        if self.desc:
            lines.append(f"  {self.desc}")
        return "\n".join(lines)


def get_registry():
    return dict(_REGISTRY)


def search_relations(keyword, tags=None):
    keyword = keyword.lower()
    results = []
    for rel in _REGISTRY.values():
        searchable = " ".join([
            rel.name, " ".join(rel._inputs), " ".join(rel._outputs),
            " ".join(rel.tags), rel.desc,
        ]).lower()
        if keyword and keyword not in searchable:
            continue
        if tags and not all(t in rel.tags for t in tags):
            continue
        results.append(rel)
    return results
