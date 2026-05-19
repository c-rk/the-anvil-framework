"""
anvil.adapters -- built-in wrappers for external libraries.

Available adapters (import individually):

    from anvil.adapters.cantera_thermo     import cea_rocket, equilibrium_flame
    from anvil.adapters.nasa_cea_detonation import cea_detonation
    from anvil.adapters.poliastro_orbits    import poliastro_orbit, poliastro_hohmann, poliastro_propagate
    from anvil.adapters.pykep_trajectories  import pykep_lambert, pykep_propagate, pykep_planet_state

Optional dependencies:
    Cantera    -- conda install -c cantera cantera   (or pip install cantera)
    poliastro  -- pip install poliastro astropy
    pykep      -- pip install pykep

All adapters fall back to analytical or mock implementations when the
optional library is not installed (pykep_lambert is the exception).
"""
