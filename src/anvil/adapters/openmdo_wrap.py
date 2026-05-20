"""
Anvil Adapter: OpenMDAO Multidisciplinary Design Analysis
=========================================================

Wraps any OpenMDAO Problem as an Anvil Relation. Enables MDO problems built
in OpenMDAO to be called from Anvil Systems, swept over parameter spaces,
and composed with other Anvil RSQs.

ADAPTERS PROVIDED:
    make_openmdo_adapter(prob, input_vars, output_vars, ...)
        Factory: wraps an existing OpenMDAO Problem as an Adapter.

    openmdo_sellar   -- Demo: Sellar multi-disciplinary problem (Sellar 1996)
    openmdo_beam     -- Demo: Simple structural beam optimization

INSTALLATION:
    pip install openmdao

VERIFY:
    python -c "import openmdao; print(openmdao.__version__)"

DESIGN:
    OpenMDAO Problem objects are stateful — the adapter sets indep_vars,
    calls prob.run_model() or prob.run_driver(), then reads outputs.
    Thread safety: each call creates a fresh copy of the Problem via a
    factory function (recommended) or re-uses the single instance (not
    thread-safe for parallel sweeps).

MOCK MODE:
    Each demo adapter has an analytical mock for testing without OpenMDAO.

USAGE:
    from anvil.adapters.openmdo_wrap import make_openmdo_adapter, openmdo_sellar

    # Use the demo Sellar adapter
    r = openmdo_sellar(x1=1.0, z1=5.0, z2=2.0)
    print(r["f"], r["g1"], r["g2"])

    # Wrap your own OpenMDAO problem
    def build_prob():
        import openmdao.api as om
        prob = om.Problem()
        # ... set up components, connections ...
        prob.setup()
        return prob

    my_adapter = make_openmdo_adapter(
        prob_factory=build_prob,
        input_vars={"x": {"unit": "1", "desc": "Design variable"},
                    "y": {"unit": "m", "desc": "Geometry variable"}},
        output_vars={"f_obj": {"unit": "1", "desc": "Objective"},
                     "g_con": {"unit": "1", "desc": "Constraint"}},
        name="my_mdo_problem",
        desc="My MDO problem via OpenMDAO",
    )
    sys.use(my_adapter)

    register()
"""

from anvil import Adapter, Q
import math


# ── Generic factory ───────────────────────────────────────────────────────────

def make_openmdo_adapter(prob_factory, input_vars, output_vars,
                         name="openmdo_problem",
                         desc="OpenMDAO problem wrapped as Anvil Relation",
                         tags=None,
                         run_driver=False,
                         prob_path_prefix=""):
    """
    Factory: create an Anvil Adapter from any OpenMDAO Problem.

    Parameters
    ----------
    prob_factory : callable → openmdao.api.Problem
        Called once per adapter invocation to get a fresh Problem instance.
        Should call prob.setup() before returning.
    input_vars : dict
        {var_name: {"unit": "...", "desc": "...", "default": ...}}
        Names must match OpenMDAO IndepVarComp or component input names.
    output_vars : dict
        {var_name: {"unit": "...", "desc": "..."}}
        Names must match OpenMDAO output variable names.
    run_driver : bool
        If True, call prob.run_driver() (runs optimizer).
        If False, call prob.run_model() (single analysis pass).
    prob_path_prefix : str
        OpenMDAO variable path prefix (e.g. "comp." if all vars are in "comp").
    """
    tags = tags or ["openmdao", "MDO"]

    def _call(**kwargs):
        try:
            import openmdao.api as om
        except ImportError:
            raise ImportError(
                "OpenMDAO not installed. pip install openmdao\n"
                "This adapter has no mock fallback — install OpenMDAO to use it."
            )
        prob = prob_factory()
        # Set inputs
        for var_name, spec in input_vars.items():
            val = kwargs.get(var_name, spec.get("default", 0.0))
            if isinstance(val, Q):
                unit = spec.get("unit", "")
                val = float(val.to(unit).value) if unit and unit != "1" else float(val.si)
            else:
                val = float(val)
            path = prob_path_prefix + var_name
            try:
                prob.set_val(path, val)
            except KeyError:
                prob.set_val(var_name, val)   # try without prefix

        # Run
        if run_driver:
            prob.run_driver()
        else:
            prob.run_model()

        # Read outputs
        result = {}
        for var_name, spec in output_vars.items():
            path = prob_path_prefix + var_name
            try:
                v = prob.get_val(path)
            except KeyError:
                v = prob.get_val(var_name)
            v = float(v) if hasattr(v, "__len__") and len(v) == 1 else v
            unit = spec.get("unit", "")
            if unit and unit != "1":
                result[var_name] = Q(float(v), unit)
            else:
                result[var_name] = float(v) if not hasattr(v, "__len__") else v
        result["source"] = "openmdao"
        return result

    return Adapter(
        name, backend="python", call=_call,
        inputs=input_vars, outputs={**output_vars, "source": {"desc": "openmdao"}},
        desc=desc, tags=tags,
    )


# ── Demo: Sellar problem ──────────────────────────────────────────────────────

def _sellar_call(x1, z1, z2):
    """
    Sellar (1996) coupled MDO problem.
    Two coupled disciplines (D1, D2), objective f and two constraints g1/g2.
    Exact analytical solution available — used as mock.
    """
    for k, v in dict(x1=x1, z1=z1, z2=z2).items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    x1=float(x1); z1=float(z1); z2=float(z2)

    try:
        import openmdao.api as om
        import openmdao.test_suite.components.sellar as sellar

        prob = om.Problem()
        model = prob.model
        model.add_subsystem("d1", sellar.SellarDis1withDerivatives(),
                            promotes=["x1", "z", "y1", "y2"])
        model.add_subsystem("d2", sellar.SellarDis2withDerivatives(),
                            promotes=["z", "y1", "y2"])
        model.add_subsystem("obj", sellar.SellarObj(),
                            promotes=["x1", "z", "y1", "y2", "obj"])
        model.add_subsystem("con1", sellar.SellarCon1(),
                            promotes=["y1", "con1"])
        model.add_subsystem("con2", sellar.SellarCon2(),
                            promotes=["y2", "con2"])
        prob.setup()
        prob.set_val("x1", x1)
        prob.set_val("z", [z1, z2])
        prob.run_model()
        f   = float(prob.get_val("obj"))
        g1  = float(prob.get_val("con1"))
        g2  = float(prob.get_val("con2"))
        y1  = float(prob.get_val("y1"))
        y2  = float(prob.get_val("y2"))
        return {"f": f, "g1": g1, "g2": g2, "y1": y1, "y2": y2,
                "source": "openmdao"}
    except (ImportError, Exception):
        pass

    # Analytical mock (Sellar equations)
    # D1: y1 = z1^2 + z2 + x1 - 0.2*y2   (iterate)
    # D2: y2 = sqrt(y1) + z1 + z2
    y2 = 3.0; y1 = 1.0
    for _ in range(50):
        y1_new = z1**2 + z2 + x1 - 0.2 * y2
        y2_new = max(y1_new, 1e-8)**0.5 + z1 + z2
        if abs(y1_new - y1) + abs(y2_new - y2) < 1e-10:
            y1, y2 = y1_new, y2_new
            break
        y1, y2 = y1_new, y2_new

    f  = x1**2 + z2 + y1 + math.exp(-y2)
    g1 = 3.16 - y1
    g2 = y2 - 24.0
    return {"f": f, "g1": g1, "g2": g2, "y1": y1, "y2": y2, "source": "mock"}


openmdo_sellar = Adapter(
    "openmdo_sellar",
    backend="python",
    call=_sellar_call,
    inputs={
        "x1": {"unit": "1", "desc": "Local design variable"},
        "z1": {"unit": "1", "desc": "Shared design variable 1 (global)"},
        "z2": {"unit": "1", "desc": "Shared design variable 2 (global)"},
    },
    outputs={
        "f":  {"unit": "1", "desc": "Objective function (minimize)"},
        "g1": {"unit": "1", "desc": "Constraint 1 (≤ 0 for feasibility)"},
        "g2": {"unit": "1", "desc": "Constraint 2 (≤ 0 for feasibility)"},
        "y1": {"unit": "1", "desc": "Coupling variable from discipline 1"},
        "y2": {"unit": "1", "desc": "Coupling variable from discipline 2"},
        "source": {"desc": "openmdao or mock"},
    },
    desc="Sellar coupled MDO benchmark problem via OpenMDAO",
    tags=["openmdao", "MDO", "Sellar", "coupled", "benchmark"],
)


# ── Demo: cantilever beam structural ─────────────────────────────────────────

def _beam_call(F_tip, L_beam, E, b, h):
    """
    Simple cantilever beam via OpenMDAO or analytical fallback.
    Inputs: tip force, length, Young's modulus, cross-section b×h.
    """
    for k, v in {"F_tip": F_tip, "L_beam": L_beam, "E": E, "b": b, "h": h}.items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    F=float(F_tip); L=float(L_beam); E_=float(E); b_=float(b); h_=float(h)

    try:
        import openmdao.api as om

        class Beam(om.ExplicitComponent):
            def setup(self):
                self.add_input("F",  val=1.0)
                self.add_input("L",  val=1.0)
                self.add_input("E",  val=70e9)
                self.add_input("b",  val=0.05)
                self.add_input("h",  val=0.1)
                self.add_output("deflection",  val=0.0)
                self.add_output("max_stress",  val=0.0)
                self.add_output("I_moment",    val=0.0)
                self.declare_partials("*", "*", method="fd")

            def compute(self, inputs, outputs):
                F_ = inputs["F"]; L_ = inputs["L"]; E_ = inputs["E"]
                b_ = inputs["b"]; h_ = inputs["h"]
                I   = b_ * h_**3 / 12.0
                outputs["deflection"] = F_ * L_**3 / (3 * E_ * I)
                outputs["max_stress"] = F_ * L_ * (h_/2) / I
                outputs["I_moment"]   = I

        prob = om.Problem()
        prob.model.add_subsystem("beam", Beam(), promotes=["*"])
        prob.setup()
        prob.set_val("F", F); prob.set_val("L", L)
        prob.set_val("E", E_); prob.set_val("b", b_); prob.set_val("h", h_)
        prob.run_model()
        defl  = float(prob.get_val("deflection"))
        sigma = float(prob.get_val("max_stress"))
        I_val = float(prob.get_val("I_moment"))
        return {"deflection": Q(defl, "m"), "max_stress": Q(sigma, "Pa"),
                "I_moment": Q(I_val, "m^4"), "source": "openmdao"}
    except (ImportError, Exception):
        pass

    # Analytical
    I      = b_ * h_**3 / 12.0
    defl   = F * L**3 / (3 * E_ * I)
    sigma  = F * L * (h_/2) / I
    return {"deflection": Q(defl, "m"), "max_stress": Q(sigma, "Pa"),
            "I_moment": Q(I, "m^4"), "source": "mock"}


openmdo_beam = Adapter(
    "openmdo_beam",
    backend="python",
    call=_beam_call,
    inputs={
        "F_tip":  {"unit": "N",  "desc": "Tip load"},
        "L_beam": {"unit": "m",  "desc": "Beam length"},
        "E":      {"unit": "Pa", "desc": "Young's modulus"},
        "b":      {"unit": "m",  "desc": "Cross-section width"},
        "h":      {"unit": "m",  "desc": "Cross-section height"},
    },
    outputs={
        "deflection": {"unit": "m",   "desc": "Tip deflection"},
        "max_stress": {"unit": "Pa",  "desc": "Maximum bending stress (root)"},
        "I_moment":   {"unit": "m^4", "desc": "Second moment of area"},
        "source":     {"desc": "openmdao or mock"},
    },
    desc="Cantilever beam structural analysis via OpenMDAO ExplicitComponent",
    tags=["openmdao", "structures", "beam", "FEA", "stress"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    for adapter in (openmdo_sellar, openmdo_beam):
        anvil.push(adapter, domain="mdo.openmdao",
                   description=adapter.desc, tags=adapter.tags)
    print("Registered: openmdo_sellar, openmdo_beam  [domain: mdo.openmdao]")
