"""
Anvil Adapter: Cantera Thermochemistry
========================================

Wraps Cantera's equilibrium solver for combustion analysis.

INSTALLATION:
  conda install -c cantera cantera     (recommended)
  pip install cantera                   (Linux/macOS)
  https://cantera.org/install/          (Windows .msi)

Verify: python -c "import cantera; print(cantera.__version__)"
"""

from anvil import Adapter, Q
import numpy as np


def _cea_rocket_call(fuel="H2", oxidizer="O2", OF=6.0, Pc=10e6, T_fuel=300, T_ox=90):
    """Rocket combustion equilibrium via Cantera HP equilibration."""
    try:
        import cantera as ct
    except ImportError:
        raise ImportError(
            "Cantera is required for this adapter.\n"
            "  Install: conda install -c cantera cantera\n"
            "  Or:      pip install cantera\n"
            "  Docs:    https://cantera.org/install/")

    fuel_lower = fuel.lower()
    if fuel_lower in ("h2", "hydrogen"):
        mech, fuel_spec = "h2o2.yaml", "H2"
    elif fuel_lower in ("ch4", "methane"):
        mech, fuel_spec = "gri30.yaml", "CH4"
    elif fuel_lower in ("c2h5oh", "ethanol"):
        mech, fuel_spec = "gri30.yaml", "C2H5OH"
    elif fuel_lower in ("c3h8", "propane"):
        mech, fuel_spec = "gri30.yaml", "C3H8"
    else:
        mech, fuel_spec = "gri30.yaml", fuel

    ox_spec = oxidizer if ":" in oxidizer else "O2"
    gas = ct.Solution(mech)

    # Set mixture by equivalence ratio derived from O/F mass ratio
    stoich_ratio = gas.stoich_air_fuel_ratio(fuel_spec, ox_spec)
    phi = stoich_ratio / OF
    gas.set_equivalence_ratio(phi, fuel_spec, ox_spec)
    gas.TP = T_fuel, Pc

    # Adiabatic combustion: constant H, constant P
    gas.equilibrate("HP")

    Tc = gas.T
    MW = gas.mean_molecular_weight     # kg/kmol
    R_gas = ct.gas_constant / MW       # J/kg/K
    gamma = gas.cp / gas.cv

    # Characteristic velocity
    cstar = np.sqrt(gamma * R_gas * Tc) / (
        gamma * np.sqrt((2 / (gamma + 1))**((gamma + 1) / (gamma - 1)))
    )

    return {
        "Tc":      Q(Tc, "K"),
        "gamma_c": gamma,
        "R_gas_c": Q(R_gas, "J/kg/K"),
        "MW_c":    Q(MW / 1000, "kg/mol"),
        "rho_c":   Q(gas.density, "kg/m^3"),
        "cstar":   Q(cstar, "m/s"),
    }


cea_rocket = Adapter("cantera_cea_rocket",
    backend="python", call=_cea_rocket_call,
    inputs={
        "fuel":     {"desc": "Fuel species (H2, CH4, C2H5OH, C3H8)", "default": "H2"},
        "oxidizer": {"desc": "Oxidizer (O2, O2:1,N2:3.76 for air)", "default": "O2"},
        "OF":       {"desc": "Oxidizer/fuel mass ratio", "default": 6.0},
        "Pc":       {"unit": "Pa", "desc": "Chamber pressure", "default": 10e6},
        "T_fuel":   {"unit": "K", "desc": "Fuel inlet temperature", "default": 300},
        "T_ox":     {"unit": "K", "desc": "Oxidizer inlet temperature", "default": 90},
    },
    outputs={
        "Tc":      {"unit": "K",      "desc": "Chamber temperature"},
        "gamma_c": {"desc": "Product ratio of specific heats"},
        "R_gas_c": {"unit": "J/kg/K", "desc": "Product gas constant"},
        "MW_c":    {"unit": "kg/mol", "desc": "Product molecular weight"},
        "rho_c":   {"unit": "kg/m^3", "desc": "Chamber density"},
        "cstar":   {"unit": "m/s",    "desc": "Characteristic velocity"},
    },
    desc="Rocket combustion equilibrium (Cantera HP, like NASA CEA)",
    tags=["combustion", "propulsion", "cantera", "CEA"],
)


def _flame_temp_call(fuel="CH4", oxidizer="O2:1,N2:3.76", phi=1.0, T_init=300, P=101325):
    """Adiabatic flame temperature via Cantera HP equilibration."""
    try:
        import cantera as ct
    except ImportError:
        raise ImportError("Cantera required. Install: conda install -c cantera cantera")

    gas = ct.Solution("gri30.yaml")
    gas.set_equivalence_ratio(phi, fuel, oxidizer)
    gas.TP = T_init, P
    gas.equilibrate("HP")

    return {
        "T_ad":    Q(gas.T, "K"),
        "gamma":   gas.cp / gas.cv,
        "MW":      Q(gas.mean_molecular_weight / 1000, "kg/mol"),
        "rho":     Q(gas.density, "kg/m^3"),
    }


equilibrium_flame = Adapter("cantera_flame_temp",
    backend="python", call=_flame_temp_call,
    inputs={
        "fuel":     {"desc": "Fuel species", "default": "CH4"},
        "oxidizer": {"desc": "Oxidizer string", "default": "O2:1,N2:3.76"},
        "phi":      {"desc": "Equivalence ratio", "default": 1.0},
        "T_init":   {"unit": "K", "desc": "Initial temperature", "default": 300},
        "P":        {"unit": "Pa", "desc": "Pressure", "default": 101325},
    },
    outputs={
        "T_ad":  {"unit": "K", "desc": "Adiabatic flame temperature"},
        "gamma": {"desc": "Product gamma"},
        "MW":    {"unit": "kg/mol", "desc": "Product molecular weight"},
        "rho":   {"unit": "kg/m^3", "desc": "Product density"},
    },
    desc="Adiabatic flame temperature via Cantera",
    tags=["combustion", "flame", "cantera"],
)


def register():
    """Register all Cantera adapters in Anvil."""
    import anvil
    anvil.push(cea_rocket, domain="propulsion.combustion",
               tags=["cantera", "CEA", "rocket"])
    anvil.push(equilibrium_flame, domain="combustion",
               tags=["cantera", "flame"])
