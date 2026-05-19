import os
import sys

import numpy as np

# --- path setup ----------------------------------------------------------

import anvil
from anvil import (
    BTU,
    MJ,
    Adapter,
    GPa,
    J,
    K,
    MPa,
    N,
    Pa,
    Q,
    Quantity,
    Relation,
    System,
    W,
    atm,
    bar,
    cm,
    ft,
    g_mol,
    kg,
    kg_mol,
    kJ,
    km,
    kN,
    kPa,
    kW,
    lb,
    lbf,
    m,
    mm,
    mol,
    monitor,
    ms,
    s,
    solvers,
    viz,
)

OUT_DIR = os.path.dirname(__file__)  # save PNGs next to this file


anvil.registry.list()
