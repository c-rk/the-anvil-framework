"""Anvil v0.4 tests -- all primitives, registry, adapters, monitor, seeds."""
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

@test("cross-ref force -> N, pressure -> Pa/psi")
def _():
    assert db.find_unit(Dim(L=1, M=1, T=-2), "SI")[0] == "N"
    assert db.find_unit(Dim(L=-1, M=1, T=-2), "SI")[0] == "Pa"
    assert db.find_unit(Dim(L=-1, M=1, T=-2), "Imperial")[0] == "psi"

@test("custom unit auto-creates and propagates")
def _():
    from anvil import Q
    a = Q(5, "blips") * Q(3, "s")
    assert "blips" in str(a._dim) and "T" in str(a._dim)

# ============================================================
print("\n=== Quantity ===")
from anvil import Q

@test("arithmetic -> correct units")
def _():
    assert (0.5 * Q(1.225, "kg/m^3") * Q(100, "m/s")**2).unit == "Pa"
    assert (Q(10, "kg") * Q(9.81, "m/s^2")).unit == "N"
    assert (Q(100, "N") * Q(5, "m")).unit == "J"
    assert (Q(1000, "J") / Q(2, "s")).unit == "W"

@test("conversions roundtrip")
def _():
    close(Q(101325, "Pa").to("kPa").value, 101.325)
    close(Q(101325, "Pa").to("atm").to("Pa").value, 101325, tol=0.01)
    close(Q(1000, "N").to("lbf").to("N").value, 1000, tol=0.1)

# ============================================================
print("\n=== System.set() / .copy() ===")
from anvil import System

@test("set keeps unit, Q overrides")
def _():
    s = System("t"); s.add("P", 6.9e6, "Pa")
    s.set(P=8e6); assert s._quantities["P"]._unit_hint == "Pa"
    s.set(P=Q(1000, "psi")); assert s._quantities["P"]._unit_hint == "psi"

@test("copy is independent")
def _():
    s = System("t"); s.add("x", 5.0)
    def fn(x): return {"y": x*2}
    s.use(fn); c = s.copy(); c.set(x=100)
    close(s.solve()["y"].si, 10); close(c.solve()["y"].si, 200)

@test("as_relation doesnt mutate original")
def _():
    def sq(x): return {"y": x**2}
    s = System("t"); s.add("x", 3); s.use(sq)
    close(s.solve()["y"].si, 9)
    o = System("o"); o.add("x", 10); o.use(s)
    close(o.solve()["y"].si, 100)
    close(s.solve()["y"].si, 9)

# ============================================================
print("\n=== System (core) ===")
from anvil import solvers

@test("forward + sweep + name mapping")
def _():
    def add(a, b): return {"c": a + b}
    s = System("t"); s.add("a", 3); s.add("b", 4); s.use(add)
    close(s.solve()["c"].si, 7)
    sr = s.sweep("a", [1,2,3]); np.testing.assert_allclose(sr["c"], [5,6,7])

    def generic(x): return {"y": x**2}
    s2 = System("t"); s2.add("val", 7.0); s2.use(generic, map={"x": "val"})
    close(s2.solve()["y"].si, 49)

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

@test("Result.to_dict and SweepResult.to_dict")
def _():
    def sq(x): return {"y": x**2}
    s = System("t"); s.add("x", 1); s.use(sq)
    d = s.solve().to_dict(); close(d["y"], 1)
    sd = s.sweep("x", [1,2,3]).to_dict()
    np.testing.assert_allclose(sd["y"], [1,4,9])

# ============================================================
print("\n=== Coupled solver ===")

@test("heat exchanger converges + energy balance")
def _():
    def hot(T_hot_in, T_cold_out, UA, Cp_hot, mdot_hot):
        Q_t = UA * ((T_hot_in - T_cold_out) * 0.5)
        return {"T_hot_out": T_hot_in - Q_t / (mdot_hot * Cp_hot), "Q_dot": Q_t}
    def cold(T_cold_in, Q_dot, Cp_cold, mdot_cold):
        return {"T_cold_out": T_cold_in + Q_dot / (mdot_cold * Cp_cold)}
    hx = System("hx")
    hx.add("T_hot_in", 500); hx.add("T_cold_in", 300); hx.add("UA", 1000)
    hx.add("Cp_hot", 1000); hx.add("Cp_cold", 4186)
    hx.add("mdot_hot", 0.5); hx.add("mdot_cold", 0.3)
    hx.add("T_cold_out", 350); hx.add("Q_dot", 50000)
    hx.use(hot); hx.use(cold)
    r = hx.solve(method="gauss_seidel", max_iter=200, rtol=1e-8, relaxation=0.5)
    Q_h = 0.5*1000*(500 - r["T_hot_out"].si)
    Q_c = 0.3*4186*(r["T_cold_out"].si - 300)
    close(Q_h, Q_c, tol=1.0)

@test("convergence monitoring")
def _():
    def f1(x, y): return {"z": (x+y)/2}
    def f2(z): return {"y": z*0.9}
    s = System("m"); s.add("x", 10); s.add("y", 1); s.use(f1); s.use(f2)
    s.solve(method="gauss_seidel", monitor=True, max_iter=100)
    h = s.history()
    assert len(h) > 0 and h[0]["residual"] > h[-1]["residual"]

# ============================================================
print("\n=== Adapter ===")
from anvil.adapter import Adapter

@test("python adapter + in system")
def _():
    def tool(P, T): return {"rho": P / (287*T)}
    adp = Adapter("gas_rho", backend="python", call=tool,
                   inputs={"P": {"unit": "Pa"}, "T": {"unit": "K"}},
                   outputs={"rho": {"unit": "kg/m^3"}})
    r = adp(P=101325, T=288.15)
    assert isinstance(r["rho"], Q)
    s = System("t"); s.add("P", 101325); s.add("T", 288.15); s.use(adp)
    close(s.solve()["rho"].si, 101325/(287*288.15), tol=0.01)

# ============================================================
print("\n=== Monitor: diagnostics ===")
from anvil.monitor import diagnose

@test("diagnose catches missing inputs")
def _():
    def need_xy(x, y): return {"z": x+y}
    s = System("t"); s.add("x", 5); s.use(need_xy)
    try: s.validate()
    except: pass
    msgs = diagnose(s)
    assert any("needs" in m or "not provided" in m for m in msgs)

@test("diagnose reports coupled variables")
def _():
    def f1(x, y): return {"z": x+y}
    def f2(z): return {"y": z*0.5}
    s = System("t"); s.add("x", 1); s.add("y", 1); s.use(f1); s.use(f2)
    msgs = diagnose(s)
    assert any("Coupled" in m or "coupled" in m.lower() for m in msgs)

@test("diagnose reports bounds violations")
def _():
    s = System("t"); s.add("T", 50000, "K", bounds=(200, 5000))
    msgs = diagnose(s)
    assert any("bounds" in m.lower() for m in msgs)

# ============================================================
print("\n=== Monitor: visualization (non-interactive) ===")
from anvil.monitor import plot_convergence, plot_variables, plot_sweep, plot_system

@test("plot_convergence saves file")
def _():
    def f1(x, y): return {"z": (x+y)/2}
    def f2(z): return {"y": z*0.9}
    s = System("conv_test"); s.add("x", 10); s.add("y", 1); s.use(f1); s.use(f2)
    s.solve(method="gauss_seidel", monitor=True, max_iter=100)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        fig = plot_convergence(s, save=path, show=False)
        assert fig is not None
        assert os.path.exists(path) and os.path.getsize(path) > 1000
    finally:
        os.unlink(path)

@test("plot_variables saves file")
def _():
    def f1(x, y): return {"z": (x+y)/2}
    def f2(z): return {"y": z*0.9}
    s = System("var_test"); s.add("x", 10); s.add("y", 1); s.use(f1); s.use(f2)
    s.solve(method="gauss_seidel", monitor=True, max_iter=100)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        fig = plot_variables(s, variables=["y", "z"], save=path, show=False)
        assert fig is not None
        assert os.path.exists(path) and os.path.getsize(path) > 1000
    finally:
        os.unlink(path)

@test("plot_sweep saves file")
def _():
    def sq(x): return {"y": x**2}
    s = System("sw"); s.add("x", 1); s.use(sq)
    sw = s.sweep("x", [1,2,3,4,5])
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        fig = plot_sweep(sw, y=["y"], save=path, show=False)
        assert fig is not None
        assert os.path.exists(path) and os.path.getsize(path) > 1000
    finally:
        os.unlink(path)

@test("plot_system saves file")
def _():
    def add(a, b): return {"c": a+b}
    def dbl(c): return {"d": c*2}
    s = System("graph_test"); s.add("a", 1); s.add("b", 2); s.use(add); s.use(dbl)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        fig = plot_system(s, save=path, show=False)
        assert fig is not None
        assert os.path.exists(path) and os.path.getsize(path) > 1000
    finally:
        os.unlink(path)

# ============================================================
print("\n=== Seed RSQs: new domains ===")
import anvil

@test("structures: cantilever beam")
def _():
    r = anvil.R.beam_deflection_cantilever(F_tip=1000, L_beam=2.0, E=200e9, I_moment=8.33e-6)
    assert "deflection" in r
    assert r["deflection"].si > 0  # should deflect downward

@test("structures: hoop stress")
def _():
    r = anvil.R.thin_wall_hoop_stress(P_internal=1e6, r_inner=0.5, t_wall=0.01)
    close(r["sigma_hoop"].si, 1e6 * 0.5 / 0.01)

@test("structures: Euler buckling")
def _():
    r = anvil.R.buckling_euler(E=200e9, I_moment=8.33e-6, L_eff=2.0)
    assert r["P_critical"].si > 0

@test("heat_transfer: conduction")
def _():
    r = anvil.R.conduction_1d(k=50, A_cross=0.01, dT=100, L_thickness=0.1)
    close(r["Q_cond"].si, 50 * 0.01 * 100 / 0.1)

@test("heat_transfer: convection")
def _():
    r = anvil.R.convection(h_conv=25, A_surf=2.0, T_surf=400, T_inf=300)
    close(r["Q_conv"].si, 25 * 2.0 * 100)

@test("heat_transfer: radiation")
def _():
    r = anvil.R.radiation(emissivity=0.9, A_surf=1.0, T_hot=500, T_cold=300)
    assert r["Q_rad"].si > 0

@test("orbital: hohmann transfer")
def _():
    mu_earth = 3.986e14
    r1 = 6371e3 + 200e3   # 200 km LEO
    r2 = 6371e3 + 35786e3  # GEO
    r = anvil.R.hohmann_transfer(mu=mu_earth, r1=r1, r2=r2)
    assert r["dv_total"].si > 3000  # about 3.9 km/s for LEO->GEO

@test("orbital: period")
def _():
    mu_earth = 3.986e14
    r = anvil.R.orbital_period(mu=mu_earth, a=42164e3)  # GEO
    close(r["T_orbital"].si, 86164, tol=200)  # ~24 hours

@test("propulsion: tsiolkovsky")
def _():
    r = anvil.R.tsiolkovsky(Isp=300, mass_ratio=5.0)
    assert r["delta_v"].si > 4000  # about 4.7 km/s

@test("thermo: sutherland viscosity")
def _():
    r = anvil.R.sutherland_viscosity(T=300)
    assert 1e-6 < r["mu"].si < 1e-4  # reasonable range for air

@test("thermo: reynolds number")
def _():
    r = anvil.R.reynolds_number(rho=1.225, V=50, L_char=1.0, mu=1.8e-5)
    assert r["Re"] > 1e6  # turbulent

# ============================================================
print("\n=== Registry store ===")
from anvil.registry.store import Store

@test("store CRUD")
def _():
    with tempfile.TemporaryDirectory() as td:
        st = Store(os.path.join(td, "test.db"))
        st.put("f", "R", "export='pub'", origin="public")
        st.put("f", "R", "export='loc'", origin="local")
        r = st.get("f"); assert "loc" in r["source"]  # local wins
        st.remove("f", "local"); r2 = st.get("f"); assert "pub" in r2["source"]
        st.close()

# ============================================================
print("\n=== Solvers ===")

@test("root finding + nonlinear + ODE + minimize")
def _():
    close(solvers.find_root(lambda x: x**2-4, bracket=(0,10)), 2.0, tol=1e-10)
    sol = solvers.solve_nonlinear(lambda x: np.array([x[0]**2+x[1]**2-4, x[0]-x[1]]), np.array([1.0,1.0]))
    close(sol[0], np.sqrt(2), tol=1e-6)
    r = solvers.minimize(lambda x: (x[0]-3)**2+(x[1]-4)**2, np.array([0.0,0.0]))
    assert r["success"]; close(r["x"][0], 3.0, tol=1e-4)
    assert solvers.solve_ode(lambda t,y: -y, (0,5), np.array([1.0]))["success"]

# ============================================================
print("\n=== anvil.check() ===")

@test("check relation")
def _():
    r = anvil.check("isentropic_ratios", verbose=False)
    assert r["ok"]
    assert "M" in r["inputs"]
    assert "T0_T" in r["outputs"]
    assert r["test_result"] is not None

@test("check system with tree")
def _():
    r = anvil.check("rocket_nozzle", verbose=False)
    assert r["ok"]
    assert r["type"] == "S"
    assert len(r["depends"]) == 8
    assert "nozzle_area_ratio" in r["tree"]
    assert r["test_result"] is not None

@test("check missing RSQ")
def _():
    r = anvil.check("does_not_exist_xyz", verbose=False)
    assert not r["ok"]
    assert any("NOT FOUND" in i for i in r["issues"])

@test("check quantity")
def _():
    r = anvil.check("g0", verbose=False)
    assert r["ok"]
    assert r["type"] == "Q"
    close(r["test_result"]["si"], 9.80665)

# ============================================================
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if errors:
    print(f"\nFailed:")
    for n, e in errors: print(f"  {n}: {e}")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
