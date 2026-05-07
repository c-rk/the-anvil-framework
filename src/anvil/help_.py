"""
anvil.lookup() -- quick reference for all Anvil tools.

Usage::

    import anvil
    anvil.lookup()               # list all categories
    anvil.lookup("cfd")          # CFDSolver + all BCs
    anvil.lookup("CFDSolver")    # solver inputs/run params/outputs
    anvil.lookup("bc")           # all boundary condition types
    anvil.lookup("mesh")         # Mesh constructors + file format
    anvil.lookup("viz")          # cfd_viz functions
    anvil.lookup("sweep")        # System.sweep parameters
    anvil.lookup("system")       # System / anvil.solve API
    anvil.lookup("relation")     # Relation / @anvil.relation
    anvil.lookup("watchdog")     # Watchdog usage
    anvil.lookup("project")      # Project (local registry)
"""

from __future__ import annotations

_W = 66   # column width

def _box(title, sections):
    W = _W
    bar  = "-" * W
    line = lambda s="": print(f"  {s}")
    line(bar)
    line(f"  {title}")
    line(bar)
    for header, rows in sections:
        if header:
            line(f"  {header}")
        for row in rows:
            line(f"    {row}")
        line()
    line(bar)


_ENTRIES = {

# -----------------------------------------------------------------
"CFDSolver": (
    "CFDSolver                                    [anvil.cfd]",
    [
        ("CONSTRUCTOR  CFDSolver(mesh, bcs, ...)", [
            "mesh         StructuredMesh2D  *required   domain mesh",
            "bcs          dict              *required   {patch_name: BC}",
            "gamma        float             1.4         ratio of sp. heats",
            "R_gas        float             287.058     gas constant [J/kg/K]",
            "flux_scheme  str               'roe'       'roe' | 'hllc'",
            "order        int               2           1=1st-order  2=MUSCL",
            "time_scheme  str               'rk4'       'rk4' | 'euler'",
            "cfl          float             0.3         CFL number",
            "transient    bool              False       False=local dt (steady)",
        ]),
        ("METHOD  solver.initialize(M, p, T, alpha_deg=0)", [
            "Fill domain with uniform freestream before calling run()",
        ]),
        ("METHOD  solver.run(...) -> CFDResult", [
            "max_iter     int    5000   max iterations",
            "tol          float  1e-4   convergence: res/res0 < tol",
            "verbose      bool   True   print residual each print_every iters",
            "print_every  int    100    stdout print interval",
            "save_every   int    0      PNG save interval (0=disabled)",
            "save_field   str   'p'    field to save: p|M|T|rho|u|v",
            "save_dir     str   '.'    directory for PNG snapshots",
            "save_vmin    float  None   fix colorbar min for snapshots",
            "save_vmax    float  None   fix colorbar max for snapshots",
            "restart_every int  0      save .npz restart every N iters",
        ]),
        ("OUTPUTS  CFDResult attributes", [
            ".p, .T, .M, .rho, .u, .v    ndarray (nx, ny)  primitive fields",
            ".converged                   bool              convergence flag",
            ".n_iter                      int               iterations run",
            ".history                     list[dict]        residual history",
            ".residuals                   list[float]       L2 residual list",
        ]),
        ("CFDResult methods", [
            ".summary()              print min/max of all fields",
            ".to_vtk(path)           ParaView .vtk output",
            ".to_tecplot(path)       Tecplot  .dat output",
            ".to_restart(path)       .npz checkpoint for restart",
            ".wall_pressure(patch)   mean pressure on named patch",
        ]),
        ("METHOD  solver.as_relation(...) -> Relation", [
            "inputs      list[str]   input names (M_inf, p_inf, T_inf ...)",
            "outputs     list[str]   M_max | p_wall | rho_max | T_max | CL | CD",
            "bc_factory  callable    fn(M,p,T,alpha)->dict  rebuild BCs per call",
            "run_kwargs  dict        forwarded to solver.run()",
            "",
            "Use: sys.use(solver.as_relation(...))",
            "     sweep = sys.sweep('M_inf', vals, parallel=4)",
        ]),
    ]
),

# -----------------------------------------------------------------
"bc": (
    "Boundary Conditions                          [anvil.cfd.bc]",
    [
        ("SupersonicInlet(M, p, T, alpha_deg=0, gamma=1.4, R_gas=287.058)", [
            "Fixed ghost = freestream. Use for M > 1 inlet.",
        ]),
        ("SupersonicOutlet()", [
            "Zero-gradient extrapolation. Use for M > 1 outlet.",
        ]),
        ("SubsonicInlet(M, p0, T0, alpha_deg=0, gamma=1.4, R_gas=287.058)", [
            "Fixed ghost from isentropic total->static. Simple, slow to converge.",
        ]),
        ("PressureInlet(p0, T0, alpha_deg=0, gamma=1.4, R_gas=287.058)", [
            "Riemann-invariant inlet. More accurate for subsonic flows.",
        ]),
        ("SubsonicOutlet / PressureOutlet(p_back, gamma=1.4)", [
            "Fix back pressure; extrapolate velocity. For subsonic outlet.",
        ]),
        ("VelocityInlet(u, v, T, p_ref=None, gamma=1.4, R_gas=287.058)", [
            "Fix velocity components and temperature at inlet.",
        ]),
        ("MassFlowInlet(mdot, T, area=1.0, alpha_deg=0, gamma, R_gas)", [
            "Specify mass flow rate at inlet.",
        ]),
        ("SlipWall()", [
            "Inviscid wall: reflects normal velocity. Use for walls/ramps.",
        ]),
        ("Symmetry()", [
            "Same as SlipWall. Use on symmetry planes.",
        ]),
        ("Farfield(M, p, T, alpha_deg=0, gamma=1.4, R_gas=287.058)", [
            "Riemann-invariant farfield. Handles sub/supersonic automatically.",
        ]),
        ("All BCs -- apply() signature (internal)", [
            "bc.apply(U_ghost, U_int, nx_out, ny_out, gamma, R_gas)",
            "  U_ghost, U_int : (N,4) arrays -- write ghost, read interior",
            "  nx_out, ny_out : (N,)  outward unit normals per face",
        ]),
    ]
),

# -----------------------------------------------------------------
"mesh": (
    "Mesh constructors                            [anvil.cfd.mesh]",
    [
        ("Mesh.wedge(half_angle_deg, chord, height, nx, ny, ...)", [
            "Body-fitted wedge mesh (flat lower wall ramp).",
        ]),
        ("Mesh.bump(length, height, nx, ny, bump_height, bump_x0, bump_sigma)", [
            "Channel with Gaussian bump on lower wall.",
        ]),
        ("Mesh.compression_ramp(length, height, ramp_x0, ramp_angle_deg, nx, ny)", [
            "Channel with smooth-tanh compression ramp on lower wall.",
        ]),
        ("Mesh.cartesian(x_span, y_span, nx, ny)", [
            "Uniform Cartesian grid.",
        ]),
        ("Mesh.from_arrays(X, Y, patches=None, title='')", [
            "X, Y : ndarray (nx+1, ny+1)  -- your node coordinates",
            "patches : dict of name->MeshPatch (optional)",
        ]),
        ("Mesh.from_file(path)", [
            "Load from .amesh file. Call Mesh.amesh_guide() for format docs.",
        ]),
        ("Mesh.amesh_guide(save_example=None)", [
            "Print .amesh file format and write an example file.",
        ]),
        ("mesh.to_file(path)", [
            "Save mesh to .amesh file (re-loadable with from_file).",
        ]),
        ("mesh.info()", [
            "Print nx, ny, node count, cell area ratio, patch names.",
        ]),
        ("mesh.plot(show=True, save_path=None, show_patches=True, ...)", [
            "Matplotlib visualization with colour-coded patch labels.",
        ]),
        ("MeshPatch(edge, start, end)", [
            "edge  : 'left'|'right'|'top'|'bottom' (or west|east|north|south)",
            "start : first cell index (0-based, inclusive)",
            "end   : last  cell index (exclusive)",
            "  left/right  -> j-cell range [0, NY)",
            "  top/bottom  -> i-cell range [0, NX)",
        ]),
    ]
),

# -----------------------------------------------------------------
"viz": (
    "CFD Visualization                            [anvil.cfd.viz]",
    [
        ("cfd_viz.contour(result, field='p', ...)", [
            "field        str    'p'    p|T|M|rho|u|v|cp|pt",
            "vmin, vmax   float  None   fix colorbar limits (for snapshots)",
            "levels       int    60     number of contour levels",
            "cmap         str    auto   matplotlib colormap name",
            "show_patches bool   True   overlay named boundary patches",
            "save_path    str    None   save PNG instead of showing",
            "title        str    None   override plot title",
        ]),
        ("cfd_viz.save_png(result, field, path, vmin=None, vmax=None)", [
            "Non-interactive contour save. Same args as contour().",
            "Use vmin/vmax to keep scale fixed across save_every frames.",
        ]),
        ("cfd_viz.multi_field(result, fields, vmin_map={}, save_path=None)", [
            "Panel plot of multiple fields. vmin_map={'p':(90e3,200e3),...}",
        ]),
        ("cfd_viz.convergence_png(history, path, title)", [
            "Save residual vs iteration plot to PNG.",
        ]),
        ("cfd_viz.mesh_plot(mesh, save_path=None, ...)", [
            "Convenience wrapper for mesh.plot().",
        ]),
        ("In solver.run() -- automatic snapshots", [
            "save_every=100   save PNG every 100 iters",
            "save_field='M'   field to plot",
            "save_dir='snaps' output directory",
            "save_vmin=0.0    fix colorbar min (optional)",
            "save_vmax=3.0    fix colorbar max (optional)",
        ]),
    ]
),

# -----------------------------------------------------------------
"system": (
    "System / anvil.solve                         [anvil.system]",
    [
        ("anvil.system(name) -> System", [
            "Create a new System.",
        ]),
        ("sys.add(key=val, ...)  or  sys.add('name', val)", [
            "Add known inputs/parameters.",
        ]),
        ("sys.use(relation_or_name)", [
            "Attach a Relation (or registered RSQ name) to the system.",
        ]),
        ("sys.solve(verbose=False) -> Result", [
            "Solve the system. Returns Result with all variables.",
            "result['var_name']  or  result.variables",
        ]),
        ("sys.sweep(param, values, parallel=1, skip_errors=False) -> SweepResult", [
            "Parametric sweep. parallel=N runs N solves concurrently (threads).",
            "sweep.summary(outputs=['x','y'])  -- print table",
            "sweep.to_dataframe()              -- pandas DataFrame",
        ]),
        ("sys.sensitivity(param, delta_frac=0.01) -> SensitivityResult", [
            "Finite-difference sensitivity analysis.",
        ]),
        ("anvil.solve(func, verbose=False, **kwargs) -> Result", [
            "One-shot solve without creating a System.",
            "anvil.solve(ideal_gas, T=300, P=101325, MW=0.029)",
        ]),
    ]
),

# -----------------------------------------------------------------
"relation": (
    "Relation / @anvil.relation                   [anvil.relation]",
    [
        ("@anvil.relation", [
            "Decorator to define and register a Relation.",
            "",
            "  @anvil.relation(domain='thermo', tags=['ideal'])",
            "  def ideal_gas(T, P, MW):",
            "      return {'rho': P * MW / (8.314 * T)}",
        ]),
        ("anvil.R.name(...)  or  anvil.R.domain.name(...)", [
            "Call a registered Relation directly (no System needed).",
            "anvil.R.oblique_shock(M1=2.0, theta_deg=10, gamma=1.4)",
        ]),
        ("anvil.push(func, domain='', tags=[], ...)", [
            "Register a function or Relation to the global registry.",
        ]),
        ("anvil.search(keyword)", [
            "Search RSQs, constants, fluids, materials by keyword.",
        ]),
        ("anvil.fetch(name_or_domain)", [
            "Load RSQs by name, domain, or tag into the namespace.",
        ]),
    ]
),

# -----------------------------------------------------------------
"sweep": (
    "sweep / parallel sweep                       [anvil.system]",
    [
        ("sys.sweep(param, values, parallel=1, skip_errors=False)", [
            "param        str       variable to sweep",
            "values       array     values to iterate over",
            "parallel     int       number of concurrent threads (1=serial)",
            "skip_errors  bool      if True, failed points return NaN",
        ]),
        ("SweepResult methods", [
            ".summary(outputs=['var1','var2'])   print table",
            ".to_dataframe()                    pandas DataFrame",
            ".plot('param', 'output')           matplotlib line plot",
        ]),
        ("CFD sweep via as_relation", [
            "rel = solver.as_relation(inputs=['M_inf','p_inf','T_inf'],",
            "                         outputs=['M_max','p_wall'],",
            "                         bc_factory=my_bc_fn,",
            "                         run_kwargs={'max_iter':1000})",
            "sys.use(rel)",
            "sweep = sys.sweep('M_inf', [1.5,2,2.5,3], parallel=4)",
        ]),
    ]
),

# -----------------------------------------------------------------
"watchdog": (
    "Watchdog / live monitoring                   [anvil.watchdog]",
    [
        ("Watchdog(system)", [
            "Attach to a System to monitor solve in real time.",
        ]),
        ("sys.solve(monitor=True, verbose=True, print_every=10)", [
            "monitor=True   stores iteration history in result",
            "verbose=True   prints each iteration to stdout",
            "print_every    how often to print (default: 1)",
        ]),
        ("result.history  -- list of dicts per iteration", [
            "  {'iteration': i, 'residual': r, 'wallclock': t, 'variables': {...}}",
        ]),
        ("anvil.viz.convergence(system)", [
            "Plot residual history after solve (requires monitor=True).",
        ]),
    ]
),

# -----------------------------------------------------------------
"project": (
    "Project (local registry)                     [anvil.project]",
    [
        ("anvil.project(name, path=None) -> Project", [
            "Create or open a project-local RSQ registry (SQLite).",
        ]),
        ("with anvil.project('my_study') as proj:", [
            "    anvil.push(my_func)      # goes to project, not global",
            "    anvil.R.isentropic_ratios(...)  # global RSQs still accessible",
            "    proj.R.my_func(...)      # project RSQs",
        ]),
        ("proj.list()           list all project RSQs", []),
        ("proj.promote('name')  move RSQ to global registry", []),
        ("proj.promote_all()    promote all RSQs to global", []),
    ]
),

}  # end _ENTRIES


_ALIASES = {
    "cfd":      ["CFDSolver", "bc", "mesh", "viz"],
    "solver":   ["CFDSolver"],
    "bc":       ["bc"],
    "bcs":      ["bc"],
    "mesh":     ["mesh"],
    "viz":      ["viz"],
    "system":   ["system"],
    "sweep":    ["sweep"],
    "relation": ["relation"],
    "rsq":      ["relation"],
    "watchdog": ["watchdog"],
    "monitor":  ["watchdog"],
    "project":  ["project"],
}


def lookup(name: str = None):
    """
    Print quick reference for Anvil tools.

    Parameters
    ----------
    name : str  category or specific name, e.g.
             'cfd', 'CFDSolver', 'bc', 'mesh', 'viz',
             'sweep', 'system', 'relation', 'watchdog', 'project'
           Omit to list all available categories.
    """
    if name is None:
        W = _W
        print("\n  " + "-" * W)
        print("  anvil.lookup(name)  --  quick reference")
        print("  " + "-" * W)
        print("  Categories:")
        cats = [
            ("'cfd'",      "CFDSolver + all BCs + Mesh + viz"),
            ("'CFDSolver'","solver constructor, run(), as_relation()"),
            ("'bc'",       "all boundary condition types"),
            ("'mesh'",     "Mesh constructors + .amesh file format"),
            ("'viz'",      "cfd_viz functions (contour, save_png, ...)"),
            ("'sweep'",    "System.sweep + parallel CFD sweep"),
            ("'system'",   "System, anvil.solve, Result"),
            ("'relation'", "@anvil.relation, anvil.R, push, search"),
            ("'watchdog'", "live monitoring, convergence history"),
            ("'project'",  "project-local RSQ registry"),
        ]
        for cat, desc in cats:
            print(f"    {cat:<16s}  {desc}")
        print("  " + "-" * W + "\n")
        return

    key = name.strip()
    targets = _ALIASES.get(key.lower(), [key])

    found = False
    for t in targets:
        entry = _ENTRIES.get(t)
        if entry is None:
            entry = _ENTRIES.get(t.upper()) or _ENTRIES.get(t.lower())
        if entry:
            title, sections = entry
            _box(title, sections)
            found = True

    if not found:
        print(f"  No entry for '{name}'. Try: anvil.lookup()  for categories.")
