import sys, os
import anvil
from anvil.seed import seed; seed(force=True)
from anvil.registry import _rebuild_namespaces; _rebuild_namespaces()

# Known values (NACA TN 1135 / Anderson tables)
tests = [
    (2.0, 10, 1.4, 39.31, 1.6397, 1.7073),  # (M1, theta, gamma, beta_ref, M2_ref, p2p1_ref)
    (3.0, 20, 1.4, 37.76, 1.9994, 3.0050),
    (4.0, 15, 1.4, 27.07, 2.9290, 3.6973),  # beta=27.07 verified from theta-beta-M
]
print("Oblique shock validation:")
print(f"{'M1':>5} {'theta':>7} {'beta_calc':>10} {'beta_ref':>10} {'M2_calc':>9} {'M2_ref':>8} {'p2/p1':>7}")
all_ok = True
for M1, theta, gamma, beta_ref, M2_ref, p2p1_ref in tests:
    r = anvil.R.oblique_shock(M1=M1, theta_deg=theta, gamma=gamma)
    beta_err = abs(r['beta_deg'] - beta_ref)
    m2_err   = abs(r['M2']      - M2_ref)
    ok = r['attached'] and beta_err < 0.5 and m2_err < 0.05
    status = "OK" if ok else "FAIL"
    all_ok = all_ok and ok
    print(f"{M1:>5.1f} {theta:>7.1f} {r['beta_deg']:>10.4f} {beta_ref:>10.4f} "
          f"{r['M2']:>9.4f} {M2_ref:>8.4f} {r['p2_p1']:>7.4f}  {status}")

r_det = anvil.R.oblique_shock(M1=1.5, theta_deg=30, gamma=1.4)
print(f"Detached check (M=1.5, theta=30): attached={r_det['attached']} (expect False)")
all_ok = all_ok and not r_det['attached']

print()
print("ALL PASS" if all_ok else "SOME FAILURES")
