"""Anvil v0.3 tests -- unit engine + registry + all primitives."""
import sys, os, traceback, tempfile
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

passed = failed = 0
errors = []

def test(name):
    def dec(fn):
        global passed, failed
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            traceback.print_exc()
            failed += 1
            errors.append((name, e))
    return dec

def close(a, b, tol=1e-6):
    if abs(a - b) > tol:
        raise AssertionError(f"{a} != {b} (tol={tol})")

# ============================================================
print("\n=== Dim ===")
from anvil.units import Dim, db

@test("multiply dims")
def _(): assert Dim(M=1) * Dim(L=1, T=-2) == Dim(L=1, M=1, T=-2)

@test("divide dims")
def _(): assert Dim(L=1) / Dim(T=1) == Dim(L=1, T=-1)

@test("power dims")
def _(): assert Dim(L=1) ** 2 == Dim(L=2)

@test("dimensionless from cancel")
def _(): assert (Dim(L=1) / Dim(L=1)).is_dimensionless

@test("parse dim string")
def _(): assert Dim.parse("[L-1][M][T-2]") == Dim(L=-1, M=1, T=-2)

@test("cross-ref force -> N")
def _(): assert db.find_unit(Dim(L=1, M=1, T=-2), "SI")[0] == "N"

@test("cross-ref pressure -> Pa/psi")
def _():
    assert db.find_unit(Dim(L=-1, M=1, T=-2), "SI")[0] == "Pa"
    assert db.find_unit(Dim(L=-1, M=1, T=-2), "Imperial")[0] == "psi"

@test("unknown dim -> None")
def _(): assert db.find_unit(Dim(L=3, M=2, T=-5), "SI") is None

@test("custom unit registration")
def _():
    s, d = db.lookup("widgets")
    assert d == Dim(widgets=1)

# ============================================================
print("\n=== Quantity mirror computation ===")
from anvil import Q

@test("Q stores SI, displays in user unit")
def _():
    q = Q(1, "kPa")
    close(q.si, 1000.0)
    close(q.value, 1.0)
    assert q.unit == "kPa"

@test("0.5 * rho * v^2 -> Pa")
def _():
    q = 0.5 * Q(1.225, "kg/m^3") * Q(100, "m/s")**2
    assert q.unit == "Pa"
    close(q.si, 6125, tol=1)

@test("mass * accel -> N")
def _():
    F = Q(10, "kg") * Q(9.81, "m/s^2")
    assert F.unit == "N"
    close(F.si, 98.1)

@test("force * distance -> J")
def _():
    E = Q(100, "N") * Q(5, "m")
    assert E.unit == "J"

@test("energy / time -> W")
def _():
    P = Q(1000, "J") / Q(2, "s")
    assert P.unit == "W"

@test("custom unit propagates")
def _():
    a = Q(5, "zorgs") * Q(3, "s")
    assert "zorgs" in str(a._dim) and "T" in str(a._dim)

@test("Pa -> kPa conversion")
def _(): close(Q(101325, "Pa").to("kPa").value, 101.325)

@test("roundtrip Pa -> atm -> Pa")
def _(): close(Q(101325, "Pa").to("atm").to("Pa").value, 101325, tol=0.01)

# ============================================================
print("\n=== System.set() ===")
from anvil import System

@test("set with bare number keeps unit")
def _():
    s = System("t")
    s.add("P0", 6.9e6, "Pa")
    s.set(P0=8e6)
    assert s._quantities["P0"]._unit_hint == "Pa"
    close(s._quantities["P0"].value, 8e6)

@test("set with Q overrides unit")
def _():
    s = System("t")
    s.add("P0", 6.9e6, "Pa")
    s.set(P0=Q(1000, "psi"))
    assert s._quantities["P0"]._unit_hint == "psi"
    close(s._quantities["P0"].value, 1000)

@test("set multiple at once")
def _():
    s = System("t")
    s.add("a", 1.0); s.add("b", 2.0)
    s.set(a=10, b=20)
    close(s._quantities["a"].si, 10)
    close(s._quantities["b"].si, 20)

@test("set unknown variable raises KeyError")
def _():
    s = System("t"); s.add("a", 1.0)
    try:
        s.set(xyz=5)
        raise AssertionError("should fail")
    except KeyError:
        pass

@test("set then solve")
def _():
    def double(x): return {"y": x * 2}
    s = System("t"); s.add("x", 5.0); s.use(double)
    r1 = s.solve(); close(r1["y"].si, 10.0)
    s.set(x=7)
    r2 = s.solve(); close(r2["y"].si, 14.0)

# ============================================================
print("\n=== System (core) ===")
from anvil import solvers

@test("forward system")
def _():
    def add(a, b): return {"c": a + b}
    s = System("t"); s.add("a", 3); s.add("b", 4); s.use(add)
    close(s.solve()["c"].si, 7)

@test("nozzle integration")
def _():
    def ar(A_e, A_t): return {"ar": A_e/A_t}
    def mach(ar, gamma):
        def f(M):
            t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)
            return (1/M)*t**((gamma+1)/(2*(gamma-1))) - ar
        return {"M": solvers.find_root(f, bracket=(1.001, 20))}
    s = System("n"); s.add("gamma", 1.4); s.add("A_e", 0.02); s.add("A_t", 0.01)
    s.use(ar); s.use(mach)
    close(s.solve()["M"].si, 2.197, tol=0.001)

@test("composition via as_relation")
def _():
    def sq(x): return {"y": x**2}
    inner = System("i"); inner.add("x", 5); inner.use(sq)
    outer = System("o"); outer.add("x", 7); outer.use(inner.as_relation(inputs=["x"], outputs=["y"]))
    close(outer.solve()["y"].si, 49)

@test("use(System) directly")
def _():
    def sq(x): return {"y": x**2}
    inner = System("i"); inner.add("x", 5); inner.use(sq)
    outer = System("o"); outer.add("x", 7); outer.use(inner)
    close(outer.solve()["y"].si, 49)

@test("sweep")
def _():
    def cube(x): return {"y": x**3}
    s = System("t"); s.add("x", 1); s.use(cube)
    sr = s.sweep("x", [1,2,3,4,5])
    np.testing.assert_allclose(sr["y"], [1,8,27,64,125])

# ============================================================
print("\n=== Registry store ===")
from anvil.registry.store import Store

@test("put and get")
def _():
    with tempfile.TemporaryDirectory() as td:
        st = Store(os.path.join(td, "test.db"))
        st.put("test_r", "R", "export = lambda x: {'y': x*2}",
               domain="math", tags=["basic"], version="1.0.0",
               description="doubles a number")
        r = st.get("test_r")
        st.close()
        assert r is not None
        assert r["name"] == "test_r"
        assert r["type"] == "R"
        assert r["domain"] == "math"
        assert "basic" in r["tags"]

@test("search")
def _():
    with tempfile.TemporaryDirectory() as td:
        st = Store(os.path.join(td, "test.db"))
        st.put("isentropic_flow", "R", "export = None", domain="aero",
               tags=["compressible"], description="isentropic ratios")
        st.put("normal_shock", "R", "export = None", domain="aero",
               tags=["compressible", "shock"], description="normal shock")
        results = st.search("shock")
        st.close()
        assert len(results) == 1
        assert results[0]["name"] == "normal_shock"

@test("local overrides public")
def _():
    with tempfile.TemporaryDirectory() as td:
        st = Store(os.path.join(td, "test.db"))
        st.put("my_func", "R", "export = 'public_version'", origin="public")
        st.put("my_func", "R", "export = 'local_version'", origin="local")
        r = st.get("my_func")
        st.close()
        assert "local_version" in r["source"]

@test("filter by type and domain")
def _():
    with tempfile.TemporaryDirectory() as td:
        st = Store(os.path.join(td, "test.db"))
        st.put("a", "R", "export=None", domain="aero")
        st.put("b", "S", "export=None", domain="aero")
        st.put("c", "R", "export=None", domain="structures")
        r_count = len(st.get_all(rsq_type="R"))
        d_count = len(st.get_all(domain="aero"))
        st.close()
        assert r_count == 2
        assert d_count == 2

@test("remove")
def _():
    with tempfile.TemporaryDirectory() as td:
        st = Store(os.path.join(td, "test.db"))
        st.put("temp", "R", "export=None")
        assert st.get("temp") is not None
        st.remove("temp")
        gone = st.get("temp") is None
        st.close()
        assert gone

# ============================================================
print("\n=== Registry namespace ===")
from anvil.registry.namespace import Namespace

@test("flat access")
def _():
    ns = Namespace("test")
    ns._register("isentropic", "obj_isen", domain="aero")
    assert ns.isentropic == "obj_isen"

@test("hierarchical access")
def _():
    ns = Namespace("test")
    ns._register("isentropic", "obj_isen", domain="aero")
    assert ns.aero.isentropic == "obj_isen"

@test("flat and hierarchical point to same object")
def _():
    ns = Namespace("test")
    obj = object()
    ns._register("shock", obj, domain="aero.compressible")
    assert ns.shock is obj
    assert ns.aero.compressible.shock is obj

@test("missing attribute gives helpful error")
def _():
    ns = Namespace("test")
    ns._register("isentropic", "x", domain="aero")
    try:
        ns.nonexistent
        raise AssertionError("should fail")
    except AttributeError as e:
        assert "fetch" in str(e)

@test("tab completion via __dir__")
def _():
    ns = Namespace("test")
    ns._register("a", 1); ns._register("b", 2, domain="math")
    d = dir(ns)
    assert "a" in d and "b" in d and "math" in d

# ============================================================
print("\n=== Registry loader ===")
from anvil.registry.loader import load_rsq

@test("load a Relation from source")
def _():
    record = {
        "name": "test_double",
        "type": "R",
        "source": "def test_double(x):\n    return {'y': x * 2}\nexport = test_double",
        "depends": [],
    }
    fn = load_rsq(record)
    assert fn(x=5) == {"y": 10}

@test("load a Quantity from source")
def _():
    record = {
        "name": "test_g",
        "type": "Q",
        "source": 'from anvil import Q\nexport = Q(9.81, "m/s^2", name="g")',
        "depends": [],
    }
    q = load_rsq(record)
    close(q.si, 9.81)

# ============================================================
print("\n=== Solvers ===")

@test("Brent")
def _(): close(solvers.find_root(lambda x: x**2-4, bracket=(0,10)), 2.0, tol=1e-10)

@test("Newton")
def _(): close(solvers.find_root(lambda x: x**2-4, x0=3, method="newton"), 2.0, tol=1e-10)

@test("ODE")
def _():
    r = solvers.solve_ode(lambda t,y: -y, (0,5), np.array([1.0]))
    assert r["success"]

# ============================================================
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if errors:
    print(f"\nFailed:")
    for n, e in errors: print(f"  {n}: {e}")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
