"""Quick regression test for bugs_29th.md fixes."""
import sys, os
import anvil
from anvil import Q, m, s, cm, kg, g, inch, in_
from anvil.units import Dim

print("Bug 1 - compound unit conversion:")
v = Q(10, 'm/s')
print("  m/s -> cm/s:", v.to('cm/s'))
md = Q(0.001, 'kg/s')
print("  kg/s -> g/s:", md.to('g/s'))
vol = Q(1e-6, 'm^3')
print("  m^3 -> cm^3:", vol.to('cm^3'))
vol2 = Q(5, 'cm**3')
print("  cm**3 works:", vol2, " -> m^3:", vol2.to('m**3'))

print()
print("Bug 1b - g/s as input unit:")
mdot = Q(1.5, 'g/s')
print("  Q(1.5, 'g/s'):", mdot, "  si:", float(mdot._si_value), "kg/s")
mdot2 = Q(1.5, 'cm/s')
print("  Q(1.5, 'cm/s'):", mdot2, "  si:", float(mdot2._si_value), "m/s")

print()
print("Bug 2 - compact dim notation:")
d1 = Dim.parse('[LMT-2]')
d2 = Dim(L=1, M=1, T=-2)
print("  [LMT-2]:", d1, "== force_dim?", d1 == d2)
d3 = Dim.parse('[L2MT-2]')
print("  [L2MT-2]:", d3, "== energy?", d3 == Dim(L=2, M=1, T=-2))
d4 = Dim.parse('[L][M][T-2]')
print("  [L][M][T-2]:", d4, "== [LMT-2]?", d1 == d4)

print()
print("Bug 3 - in as inches:")
print("  Q(5, 'in'):", Q(5, 'in'))
print("  Q(5, 'in').to('cm'):", Q(5, 'in').to('cm'))
print("  5 * inch:", 5 * inch)
print("  5 * in_:", 5 * in_)

print()
print("Bug 4 - explicit solver methods + unit propagation:")
sys1 = anvil.system('test')
sys1.add('T', 300, 'K')
sys1.add('P', 101325, 'Pa')
sys1.add('R_gas', 8.314, 'J/mol/K')
sys1.add('MW', 0.029, 'kg/mol')

def ideal_gas_rho(T, P, R_gas, MW):
    """Return density; all inputs are Quantities so dims propagate."""
    return {'rho': P * MW / (R_gas * T)}

sys1.use(ideal_gas_rho)
r = sys1.solve_forward()
rho = r['rho']
print("  rho value:", float(rho._si_value), "(expect ~1.178 kg/m^3)")
print("  rho dim:", rho._dim._exp, "(expect {'L':-3,'M':1})")
print("  rho unit:", rho.unit)

print()
print("Bug 5 - live monitoring (see residuals below):")
def f1(x): return {'y': 1.0 / (1.0 + x)}
def f2(y): return {'x': y**0.5}
sys2 = anvil.system('coupled')
sys2.add('x', 0.5)
sys2.add('y', 0.5)
sys2.use(f1)
sys2.use(f2)
r2 = sys2.solve(monitor=True, max_iter=15)
print("  converged x =", round(float(r2['x']._si_value), 6))

print()
print("All checks done.")
