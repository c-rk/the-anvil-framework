"""
Fluid and material property databases.

Built-in lookup tables for common engineering fluids and structural materials.
No external dependencies -- these are curve fits and tabulated data from
standard references (NIST, ASM, MIL-HDBK-5).

Usage:
    from anvil.db import fluids, materials

    # Fluid properties at a given temperature
    water = fluids.get("water", T=350, P=101325)
    print(water["rho"], water["mu"], water["cp"])

    # Material properties
    al = materials.get("Al-6061-T6")
    print(al["E"], al["sigma_y"], al["rho"])

    # Search
    fluids.search("nitrogen")
    materials.search("steel")
"""

from anvil.quantity import Q
import numpy as np


# ============================================================
# Fluid property database
# ============================================================

_FLUID_DATA = {
    "air": {
        "desc": "Dry air at 1 atm",
        "T_range": (200, 2000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (287.058 * T), "kg/m^3"),
            "cp":   Q(1005.0, "J/kg/K"),
            "mu":   Q(1.716e-5 * (T / 273.15)**1.5 * (273.15 + 110.4) / (T + 110.4), "Pa*s"),
            "k":    Q(0.0241 * (T / 273.15)**0.81, "W/m/K"),
            "gamma": 1.4,
            "R_gas": Q(287.058, "J/kg/K"),
            "Pr":   0.71,
        },
    },
    "nitrogen": {
        "desc": "N2 at 1 atm",
        "T_range": (200, 2000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (296.8 * T), "kg/m^3"),
            "cp":   Q(1040.0, "J/kg/K"),
            "mu":   Q(1.663e-5 * (T / 273.15)**1.5 * (273.15 + 107) / (T + 107), "Pa*s"),
            "k":    Q(0.0242 * (T / 273.15)**0.81, "W/m/K"),
            "gamma": 1.4,
            "R_gas": Q(296.8, "J/kg/K"),
        },
    },
    "helium": {
        "desc": "He at 1 atm",
        "T_range": (50, 2000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (2077 * T), "kg/m^3"),
            "cp":   Q(5193.0, "J/kg/K"),
            "mu":   Q(1.96e-5 * (T / 300)**0.67, "Pa*s"),
            "k":    Q(0.152 * (T / 300)**0.67, "W/m/K"),
            "gamma": 1.667,
            "R_gas": Q(2077.0, "J/kg/K"),
        },
    },
    "hydrogen": {
        "desc": "H2 at 1 atm",
        "T_range": (200, 3000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (4124 * T), "kg/m^3"),
            "cp":   Q(14300.0, "J/kg/K"),
            "mu":   Q(8.76e-6 * (T / 293)**0.68, "Pa*s"),
            "k":    Q(0.182 * (T / 300)**0.72, "W/m/K"),
            "gamma": 1.41,
            "R_gas": Q(4124.0, "J/kg/K"),
        },
    },
    "water": {
        "desc": "Liquid water (approximate, 280-380 K)",
        "T_range": (280, 380),
        "props": lambda T, P=101325: {
            "rho":  Q(1000 - 0.0178 * (T - 277)**1.7, "kg/m^3"),
            "cp":   Q(4186.0, "J/kg/K"),
            "mu":   Q(1.002e-3 * np.exp(-0.0248 * (T - 293)), "Pa*s"),
            "k":    Q(0.597 + 0.0017 * (T - 293), "W/m/K"),
            "Pr":   lambda: 4186 * 1.002e-3 * np.exp(-0.0248 * (T - 293)) / (0.597 + 0.0017 * (T - 293)),
        },
    },
    "co2": {
        "desc": "CO2 at 1 atm",
        "T_range": (220, 1500),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (188.9 * T), "kg/m^3"),
            "cp":   Q(844 + 0.28 * (T - 300), "J/kg/K"),
            "mu":   Q(1.48e-5 * (T / 300)**0.77, "Pa*s"),
            "gamma": 1.289,
            "R_gas": Q(188.9, "J/kg/K"),
        },
    },
    "oxygen": {
        "desc": "O2 at 1 atm",
        "T_range": (70, 2000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (259.8 * T), "kg/m^3"),
            "cp":   Q(918.0 + 0.10 * (T - 300), "J/kg/K"),
            "mu":   Q(2.04e-5 * (T / 300.0)**0.69, "Pa*s"),
            "k":    Q(0.0263 * (T / 300.0)**0.84, "W/m/K"),
            "gamma": 1.40,
            "R_gas": Q(259.8, "J/kg/K"),
        },
    },
    "methane": {
        "desc": "CH4 at 1 atm",
        "T_range": (111, 1500),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (518.3 * T), "kg/m^3"),
            "cp":   Q(2220.0 + 0.8 * (T - 300), "J/kg/K"),
            "mu":   Q(1.10e-5 * (T / 300.0)**0.67, "Pa*s"),
            "k":    Q(0.0341 * (T / 300.0)**1.08, "W/m/K"),
            "gamma": 1.32,
            "R_gas": Q(518.3, "J/kg/K"),
        },
    },
    "propane": {
        "desc": "C3H8 at 1 atm",
        "T_range": (231, 1000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (188.6 * T), "kg/m^3"),
            "cp":   Q(1670.0 + 3.0 * (T - 300), "J/kg/K"),
            "mu":   Q(8.00e-6 * (T / 300.0)**0.72, "Pa*s"),
            "k":    Q(0.0180 * (T / 300.0)**1.05, "W/m/K"),
            "gamma": 1.13,
            "R_gas": Q(188.6, "J/kg/K"),
        },
    },
    "argon": {
        "desc": "Ar at 1 atm",
        "T_range": (84, 3000),
        "props": lambda T, P=101325: {
            "rho":  Q(P / (208.1 * T), "kg/m^3"),
            "cp":   Q(520.3, "J/kg/K"),
            "mu":   Q(2.27e-5 * (T / 300.0)**0.72, "Pa*s"),
            "k":    Q(0.0177 * (T / 300.0)**0.72, "W/m/K"),
            "gamma": 1.667,
            "R_gas": Q(208.1, "J/kg/K"),
        },
    },
}


class FluidDB:
    """Lookup fluid properties by name and conditions."""

    def get(self, name, T=300, P=101325):
        """Get fluid properties at temperature T (K) and pressure P (Pa)."""
        key = name.lower().replace("-", "").replace(" ", "")
        for k, data in _FLUID_DATA.items():
            if k == key or key in k:
                props = data["props"](T, P)
                # Resolve any lazy Pr
                resolved = {}
                for pk, pv in props.items():
                    if callable(pv):
                        resolved[pk] = pv()
                    else:
                        resolved[pk] = pv
                return resolved
        raise KeyError(
            f"Fluid '{name}' not found.\n"
            f"  Available: {', '.join(sorted(_FLUID_DATA.keys()))}\n"
            f"  Hint: fluids.search('{name}') to find similar."
        )

    def list(self):
        """List all available fluids."""
        results = []
        for name, data in sorted(_FLUID_DATA.items()):
            print(f"  {name:15s}  {data['desc']}")
            results.append(name)
        return results

    def search(self, keyword):
        """Search fluids by keyword."""
        kw = keyword.lower()
        results = []
        for name, data in _FLUID_DATA.items():
            if kw in name or kw in data["desc"].lower():
                results.append((name, data["desc"]))
                print(f"  {name:15s}  {data['desc']}")
        return results


# ============================================================
# Material property database
# ============================================================

_MATERIAL_DATA = {
    "Al-6061-T6": {
        "desc": "Aluminum 6061-T6 (general purpose aerospace)",
        "E": Q(68.9e9, "Pa"), "sigma_y": Q(276e6, "Pa"), "sigma_u": Q(310e6, "Pa"),
        "rho": Q(2700, "kg/m^3"), "nu_poisson": 0.33,
        "k": Q(167, "W/m/K"), "alpha": Q(23.6e-6, "K"),
        "T_max": Q(423, "K"),
    },
    "Al-7075-T6": {
        "desc": "Aluminum 7075-T6 (high-strength aerospace)",
        "E": Q(71.7e9, "Pa"), "sigma_y": Q(503e6, "Pa"), "sigma_u": Q(572e6, "Pa"),
        "rho": Q(2810, "kg/m^3"), "nu_poisson": 0.33,
        "k": Q(130, "W/m/K"), "alpha": Q(23.4e-6, "K"),
        "T_max": Q(423, "K"),
    },
    "Ti-6Al-4V": {
        "desc": "Titanium 6Al-4V (aerospace, high temp)",
        "E": Q(113.8e9, "Pa"), "sigma_y": Q(880e6, "Pa"), "sigma_u": Q(950e6, "Pa"),
        "rho": Q(4430, "kg/m^3"), "nu_poisson": 0.342,
        "k": Q(6.7, "W/m/K"), "alpha": Q(8.6e-6, "K"),
        "T_max": Q(673, "K"),
    },
    "Steel-304": {
        "desc": "Stainless steel 304 (corrosion resistant)",
        "E": Q(193e9, "Pa"), "sigma_y": Q(215e6, "Pa"), "sigma_u": Q(505e6, "Pa"),
        "rho": Q(8000, "kg/m^3"), "nu_poisson": 0.29,
        "k": Q(16.2, "W/m/K"), "alpha": Q(17.3e-6, "K"),
        "T_max": Q(1089, "K"),
    },
    "Steel-4340": {
        "desc": "AISI 4340 steel (high-strength structural)",
        "E": Q(205e9, "Pa"), "sigma_y": Q(470e6, "Pa"), "sigma_u": Q(745e6, "Pa"),
        "rho": Q(7850, "kg/m^3"), "nu_poisson": 0.29,
        "k": Q(44.5, "W/m/K"), "alpha": Q(12.3e-6, "K"),
        "T_max": Q(800, "K"),
    },
    "Inconel-718": {
        "desc": "Inconel 718 (turbine blades, high temp)",
        "E": Q(200e9, "Pa"), "sigma_y": Q(1035e6, "Pa"), "sigma_u": Q(1240e6, "Pa"),
        "rho": Q(8190, "kg/m^3"), "nu_poisson": 0.29,
        "k": Q(11.4, "W/m/K"), "alpha": Q(13e-6, "K"),
        "T_max": Q(973, "K"),
    },
    "CFRP": {
        "desc": "Carbon fiber reinforced polymer (quasi-isotropic layup)",
        "E": Q(70e9, "Pa"), "sigma_y": Q(600e6, "Pa"), "sigma_u": Q(900e6, "Pa"),
        "rho": Q(1600, "kg/m^3"), "nu_poisson": 0.3,
        "k": Q(5, "W/m/K"), "alpha": Q(2e-6, "K"),
        "T_max": Q(450, "K"),
    },
    "Copper-C101": {
        "desc": "Oxygen-free copper (thermal management, thrust chambers)",
        "E": Q(117e9, "Pa"), "sigma_y": Q(69e6, "Pa"), "sigma_u": Q(221e6, "Pa"),
        "rho": Q(8940, "kg/m^3"), "nu_poisson": 0.34,
        "k": Q(391, "W/m/K"), "alpha": Q(17e-6, "K"),
        "T_max": Q(473, "K"),
    },
}


class MaterialDB:
    """Lookup material mechanical and thermal properties."""

    def get(self, name):
        """Get material properties by exact or partial name."""
        # Exact match
        if name in _MATERIAL_DATA:
            return dict(_MATERIAL_DATA[name])

        # Partial match
        key = name.lower().replace(" ", "").replace("-", "")
        for k, data in _MATERIAL_DATA.items():
            if key in k.lower().replace("-", "") or key in data["desc"].lower():
                return dict(data)

        raise KeyError(
            f"Material '{name}' not found.\n"
            f"  Available: {', '.join(sorted(_MATERIAL_DATA.keys()))}\n"
            f"  Hint: materials.search('{name}') to find similar."
        )

    def list(self):
        """List all available materials."""
        results = []
        for name, data in sorted(_MATERIAL_DATA.items()):
            sy = data["sigma_y"].value / 1e6
            E = data["E"].value / 1e9
            rho = data["rho"].value
            print(f"  {name:15s}  E={E:.0f} GPa  sy={sy:.0f} MPa  rho={rho:.0f} kg/m3  |  {data['desc']}")
            results.append(name)
        return results

    def search(self, keyword):
        """Search materials by keyword."""
        kw = keyword.lower()
        results = []
        for name, data in _MATERIAL_DATA.items():
            if kw in name.lower() or kw in data["desc"].lower():
                results.append((name, data["desc"]))
                print(f"  {name:15s}  {data['desc']}")
        return results

    def compare(self, *names):
        """Compare materials side-by-side."""
        mats = []
        for n in names:
            m = self.get(n)
            m["_name"] = n
            mats.append(m)

        # Print comparison table
        props = ["E", "sigma_y", "sigma_u", "rho", "k", "T_max"]
        labels = ["E (GPa)", "Yield (MPa)", "UTS (MPa)", "Density", "k (W/mK)", "T_max (K)"]

        w = 16
        header = f"{'':20s}" + "".join(f"{m['_name']:>{w}s}" for m in mats)
        print(f"\n{header}")
        print(f"  {'':18s}" + "-" * (w * len(mats)))

        for prop, label in zip(props, labels):
            row = f"  {label:18s}"
            for m in mats:
                if prop in m:
                    v = m[prop]
                    if isinstance(v, Q):
                        if "GPa" in label:
                            row += f"{v.si/1e9:>{w}.1f}"
                        elif "MPa" in label:
                            row += f"{v.si/1e6:>{w}.0f}"
                        else:
                            row += f"{v.value:>{w}.1f}"
                    else:
                        row += f"{v:>{w}.3f}"
                else:
                    row += f"{'--':>{w}s}"
            print(row)
        print()


# Module-level instances
fluids = FluidDB()
materials = MaterialDB()
