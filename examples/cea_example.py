import os
import sys

import numpy as np


import anvil
from anvil.adapters.nasa_cea_detonation import cea_detonation
from anvil import Q, System

det = System("h2o2_detonation")
det.add("fuel_moles", 1.0, desc="Moles of H2")
det.add("ox_moles", 0.5, desc="Moles of O2")
det.add("T1", 300, "K", desc="Initial temperature")
det.add("P1", 1, "atm", desc="Initial pressure")


def h2o2_det(fuel_moles, ox_moles, T1, P1):
    """Wrapper: Anvil passes SI values (K, Pa) which the adapter handles."""
    return cea_detonation(
        fuel="H2", oxidizer="O2", fuel_moles=fuel_moles, ox_moles=ox_moles, T1=T1, P1=P1
    )


det.use(h2o2_det)

result = det.solve()
result.summary(
    keys=[
        "fuel_moles",
        "ox_moles",
        "T1",
        "P1",
        "D_CJ",
        "T_CJ",
        "P_CJ",
        "P_ratio",
        "gamma_CJ",
        "MW_CJ",
        "a_CJ",
    ]
)
