"""
Adapters have moved to anvil.adapters (installed with the package).

Old (broken):
    import sys
    sys.path.insert(0, "adapters")
    from cantera_thermo import cea_rocket

New (correct after pip install -e .):
    from anvil.adapters.cantera_thermo import cea_rocket

Install:
    pip install -e .                  # core + built-in adapters
    pip install -e ".[poliastro]"     # + poliastro/astropy
    pip install -e ".[pykep]"         # + pykep
    pip install -e ".[adapters]"      # all adapter deps
"""

