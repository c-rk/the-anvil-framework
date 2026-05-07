"""
anvil.cfd — Native 2D structured finite volume CFD solver.

Solves the 2D Euler (inviscid) equations on structured body-fitted meshes.
Handles subsonic, transonic, and supersonic flows including shocks.

Quick start
-----------
    from anvil.cfd import CFDSolver, Mesh
    from anvil.cfd.bc import SupersonicInlet, SupersonicOutlet, SlipWall, Farfield

    # 1. Build mesh
    mesh = Mesh.wedge(half_angle_deg=10, chord=1.0, height=0.8, nx=80, ny=40)

    # 2. Specify boundary conditions
    M_inf, p_inf, T_inf = 2.0, 101325.0, 300.0
    bcs = {
        "west":  SupersonicInlet(M=M_inf, p=p_inf, T=T_inf),
        "east":  SupersonicOutlet(),
        "south": SlipWall(),
        "north": Farfield(M=M_inf, p=p_inf, T=T_inf),
    }

    # 3. Create solver
    solver = CFDSolver(mesh, bcs, gamma=1.4, flux_scheme="roe", order=2, cfl=0.5)

    # 4. Initialize uniform freestream
    solver.initialize(M=M_inf, p=p_inf, T=T_inf, alpha_deg=0.0)

    # 5. Run until convergence
    result = solver.run(max_iter=5000, tol=1e-6, monitor=True, print_every=100)

    # 6. Post-process
    result.summary()
    result.to_vtk("wedge.vtk")       # open in ParaView
    result.to_tecplot("wedge.dat")   # open in Tecplot

    # 7. Use inside Anvil System (scalar Q inputs/outputs)
    rel = solver.as_relation(inputs=["M_inf", "p_inf", "T_inf"],
                             outputs=["CL", "CD", "M_max", "p_wall"])
    anvil_system.use(rel)
    sweep = anvil_system.sweep("M_inf", [1.5, 2.0, 2.5, 3.0], parallel=4)

Architecture
------------
    mesh.py     StructuredMesh2D — node coords, cell centres, face normals
    flux.py     roe_flux_2d, hllc_flux_2d, muscl_reconstruct
    bc.py       BoundaryCondition subclasses (SupersonicInlet, SlipWall, ...)
    solver.py   CFDSolver (main loop), CFDResult (post-processing, I/O)
    io.py       write_vtk, write_tecplot, write_restart, load_restart

Extensibility
-------------
    Viscous: add viscous_flux_2d() in flux.py; call after inviscid in solver._residual()
    3D:      add k-index in mesh, w-velocity, and third face sweep in solver
    Real gas: replace ideal-gas EOS calls with custom EOS object
"""

from anvil.cfd.mesh   import StructuredMesh2D as Mesh, MeshPatch
from anvil.cfd.solver import CFDSolver, CFDResult
from anvil.cfd.bc import (
    BoundaryCondition,
    SupersonicInlet,
    SupersonicOutlet,
    SubsonicInlet,
    SubsonicOutlet,
    PressureInlet,
    PressureOutlet,
    VelocityInlet,
    MassFlowInlet,
    SlipWall,
    Symmetry,
    Farfield,
)
from anvil.cfd.io import write_vtk, write_tecplot, write_restart, load_restart
from anvil.cfd import viz

__all__ = [
    "Mesh", "MeshPatch", "CFDSolver", "CFDResult",
    "BoundaryCondition",
    "SupersonicInlet", "SupersonicOutlet",
    "SubsonicInlet", "SubsonicOutlet",
    "PressureInlet", "PressureOutlet",
    "VelocityInlet", "MassFlowInlet",
    "SlipWall", "Symmetry", "Farfield",
    "write_vtk", "write_tecplot", "write_restart", "load_restart",
    "viz",
]
