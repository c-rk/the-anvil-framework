"""
Anvil: From equations to engineering tools.

    import anvil
    from anvil import K, Pa, m, s, kg, N, J, W

    # Unit-stub syntax (Unitful.jl inspired)
    T = 300 * K           # Quantity(300, "K")
    P = 101325 * Pa       # Quantity(101325, "Pa")
    v = 340 * (m/s)       # Quantity(340, "m/s")
    g = 9.81 * m/s**2     # Quantity(9.81, "m/s^2")

    # One-shot solve (no System object needed)
    result = anvil.solve(ideal_gas, T=300*K, P=101325*Pa, MW=0.029*kg/mol)

    # Decorator to define and auto-register a Relation
    @anvil.relation(domain="thermo")
    def ideal_gas(T, P, MW):
        return {"rho": P * MW / (8.314 * T)}

    # Build a System explicitly
    sys = anvil.system("nozzle")
    sys.add(T0=3500*K, P0=6.9*MPa, gamma=1.25, R_gas=320*J/kg/K)
    sys.use(ideal_gas)
    sys.solve(verbose=True).summary()

    # Use built-in RSQs
    anvil.R.isentropic_ratios(M=2, gamma=1.4)

    # Load a pre-built System, override, solve
    nozzle = anvil.S.rocket_nozzle.copy()
    nozzle.set(P0=8e6)
    nozzle.solve().summary()

    # Visualize
    from anvil import viz
    viz.convergence(system)
    viz.sweep_plot(sweep_result)
    viz.dependency_graph(system)
"""

__version__ = "1.2.0"

# Core primitives
from anvil.quantity import Quantity, Q
from anvil.units import Dim
from anvil.relation import Relation
from anvil.system import System, Result, SweepResult, SensitivityResult, OptimizeResult, ValidationError
from anvil.adapter import Adapter
from anvil.watchdog import Watchdog
from anvil.inspect import check
from anvil import units, solvers, viz, decomp
from anvil import cfd
from anvil.project import Project, get_active_project
from anvil.help_ import lookup

# Databases
from anvil.db import fluids, materials

# Registry namespaces
from anvil import registry
R = registry.R
S = registry.S
QDB = registry.Q_ns

# Unit stubs — import individual units for 300 * K syntax
from anvil.units import (
    UnitStub,
    # Base SI
    K, Pa, m, s, kg, mol, A, N, J, W, rad, deg,
    # Length prefixes
    km, cm, mm, um,
    # Mass
    g, tonne,
    # Time
    ms, us, hr,
    # Pressure
    kPa, MPa, GPa, bar, atm, psi,
    # Force / Energy / Power
    kN, kJ, MJ, kW, BTU,
    # Imperial
    ft, inch, in_, lb, lbf,
    # Molar
    kmol, g_mol, kg_mol,
)


# ============================================================
# New API helpers
# ============================================================

def system(name, desc=""):
    """Create a new System.

    Equivalent to System(name, desc) but reads more naturally:
        sys = anvil.system("heat_exchanger")
    """
    return System(name, desc)


def relation(func=None, *, domain="", tags=None, desc="", register=True, name=None):
    """
    Decorator to define a Relation and optionally register it.

    Usage:
        @anvil.relation(domain="thermo", tags=["ideal_gas"])
        def ideal_gas(T, P, MW):
            return {"rho": P * MW / (8.314 * T)}

        # Without parentheses (no options):
        @anvil.relation
        def speed_of_sound(gamma, R_gas, T):
            return {"a": (gamma * R_gas * T) ** 0.5}
    """
    def decorator(f):
        rel = Relation(
            f,
            name=name or f.__name__,
            tags=tags or [],
            desc=desc or (f.__doc__ or "").strip(),
        )
        if register:
            try:
                push(rel, domain=domain, tags=tags or [])
            except Exception:
                pass  # registration is best-effort; relation still works
        return rel

    if func is not None:
        # Called as @anvil.relation (no parentheses)
        return decorator(func)
    return decorator


def solve(func_or_name, verbose=False, **kwargs):
    """
    One-shot solve: no System object needed.

    Creates a temporary System, adds all kwargs as inputs,
    attaches func_or_name as the single Relation, solves, returns Result.

    Usage:
        result = anvil.solve(ideal_gas, T=300*K, P=101325*Pa, MW=0.029*kg/mol)
        print(result["rho"])

        # Works with registry names too:
        result = anvil.solve("isentropic_ratios", M=2.0, gamma=1.4)
    """
    func_name = getattr(func_or_name, "name", None) or \
                getattr(func_or_name, "__name__", None) or \
                str(func_or_name)
    sys = System(f"_solve_{func_name}")
    for k, v in kwargs.items():
        sys._add_single(k, v)
    sys.use(func_or_name)
    return sys.solve(verbose=verbose)


def set_units(system_name):
    """Set display unit system: 'SI' or 'Imperial'."""
    units.set_system(system_name)


def fetch(names, key=None, url=None):
    """Fetch RSQs from the registry by name, domain, or tag."""
    if isinstance(names, str):
        names = [names]
    store = registry._get_store()
    loaded = 0
    for name in names:
        if store.get(name): loaded += 1; continue
        dr = store.get_all(domain=name)
        if dr: loaded += len(dr); continue
        tr = store.get_all(tag=name)
        if tr: loaded += len(tr); continue
        print(f"  '{name}' not found in local registry.")
    registry._rebuild_namespaces()
    if loaded:
        print(f"  Loaded {loaded} RSQ(s).")


def push(obj, name=None, domain="", version="0.0.1", description="",
         author="", tags=None, tests=None, depends=None, overwrite=False):
    """
    Register an RSQ.

    If a project context is active (via `with anvil.project(...) as p:`),
    the RSQ is registered to the project store instead of the global registry.

    Parameters
    ----------
    overwrite : bool
        If True, silently update an existing RSQ with the same name.
    """
    active = get_active_project()
    if active is not None:
        active.push(obj, name=name, domain=domain, version=version,
                    description=description, author=author,
                    tags=tags, tests=tests, depends=depends)
        return
    registry.register(obj, name=name, domain=domain, version=version,
                      description=description, author=author,
                      tags=tags, tests=tests, depends=depends)
    registry._rebuild_namespaces()


def project(name, path=None):
    """
    Create or open a project-local RSQ registry.

    Returns a Project object. Use as a context manager to automatically route
    anvil.push() to the project store:

        with anvil.project("my_study", path="./work") as proj:
            anvil.push(my_func)          # goes to project, not global
            anvil.R.isentropic_ratios    # global RSQs still accessible
            proj.R.my_func(...)          # project RSQs

        proj.promote("my_func")          # move to global when ready

    Without context manager:
        proj = anvil.project("my_study")
        proj.push(my_func)
        proj.list()
    """
    return Project(name, path)


def update(obj, name=None, domain=None, version=None, description=None,
           author=None, tags=None):
    """
    Update/overwrite an existing RSQ in the registry.

    If the RSQ doesn't exist, it is created.
    Same as push() but semantically signals intent to overwrite.

    Usage:
        anvil.update(my_improved_func, name="ideal_gas", domain="thermo")
    """
    registry.update(obj, name=name, domain=domain, version=version,
                    description=description, author=author, tags=tags)
    registry._rebuild_namespaces()


def search(keyword, tags=None):
    """Search across RSQs, constants, fluids, and materials."""
    from anvil.db import const as _c
    from anvil.db import fluids as _f, materials as _m
    results = registry.search(keyword)
    consts = _c.search(keyword)
    if consts:
        print(f"\n  Built-in constants:")
        for name, q in consts:
            print(f"    {name}: {q}")
    fl = _f.search(keyword)
    if fl:
        print(f"\n  Fluids found: {len(fl)}")
    ml = _m.search(keyword)
    if ml:
        print(f"\n  Materials found: {len(ml)}")
    return results


# Auto-seed the registry on first import
try:
    from anvil.seed import seed as _seed
    _seed()
except Exception:
    pass
