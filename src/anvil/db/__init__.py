"""Physical constants as Quantities."""
from anvil.quantity import Q

class _Constants:
    c      = Q(299792458.0, "m/s", name="speed_of_light")
    h      = Q(6.62607015e-34, "J", name="planck_constant")
    k_B    = Q(1.380649e-23, "J/kg/K", name="boltzmann_constant")
    R      = Q(8.314462618, "J/mol/K", name="gas_constant")
    N_A    = Q(6.02214076e23, "", name="avogadro")
    g0     = Q(9.80665, "m/s^2", name="standard_gravity")
    sigma  = Q(5.670374419e-8, "W", name="stefan_boltzmann")
    atm    = Q(101325.0, "Pa", name="std_atmosphere")
    T_sl   = Q(288.15, "K", name="sea_level_temp")
    rho_sl = Q(1.225, "kg/m^3", name="sea_level_density")
    a_sl   = Q(340.294, "m/s", name="sea_level_speed_of_sound")
    gamma_air = Q(1.4, "", name="gamma_air")
    R_air  = Q(287.058, "J/kg/K", name="R_air")
    M_air  = Q(0.0289647, "kg/mol", name="molar_mass_air")
    cp_air = Q(1005.0, "J/kg/K", name="cp_air")
    pi     = Q(3.141592653589793, "", name="pi")

    def list(self):
        return [a for a in dir(self) if not a.startswith("_") and isinstance(getattr(self, a), Q)]

    def search(self, keyword):
        kw = keyword.lower()
        return [(a, getattr(self, a)) for a in self.list()
                if kw in a.lower() or kw in getattr(self, a).name.lower()]

const = _Constants()

# Fluid and material databases
from anvil.db.properties import fluids, materials
