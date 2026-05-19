"""
Example 19: Abel Transform and Inversion
=========================================

Demonstrates:
    - abel_forward(): simulate a camera projection from a known radial source
    - abel_onion(): invert via onion peeling
    - abel_three_point(): invert via Dasch three-point operator
    - Round-trip validation against analytic solutions
    - abel_center(): find axis of symmetry in a 2D image
    - abel_image(): apply Abel inversion row-by-row to a full image
    - abel_forward_image(): forward project a radial image (validation)
    - viz.abel_compare(): side-by-side projection vs radial

Engineering context:
    Plasma emission spectroscopy, combustion diagnostics, and ion imaging
    all produce 2D projections of a cylindrically symmetric 3D source.
    Abel inversion recovers the true radial emission profile from the
    line-of-sight integrated camera image.
"""

import sys, os
import numpy as np

import anvil
import anvil.decomp as decomp

print("=" * 60)
print("  Example 19: Abel Transform and Inversion")
print("=" * 60)


# ---------------------------------------------------------------
# Part 1: 1D validation -- Gaussian ring (analytic solution known)
# ---------------------------------------------------------------
print("\n[1] Forward Abel: Gaussian radial distribution -> projection")
print("    f(r) = exp(-r^2/sigma^2),  F(y) = sigma*sqrt(pi)*exp(-y^2/sigma^2)")

N = 300
dr = 0.05
r = np.arange(N) * dr
sigma = 3.0   # radial width in physical units

fr_true = np.exp(-(r / sigma) ** 2)
Fy_analytic = sigma * np.sqrt(np.pi) * np.exp(-(r / sigma) ** 2)

Fy_numerical = decomp.abel_forward(fr_true, dr=dr)

err_fwd = np.linalg.norm(Fy_numerical - Fy_analytic) / np.linalg.norm(Fy_analytic)
print(f"  Forward transform error vs analytic: {err_fwd:.2e}")

# ---------------------------------------------------------------
# Part 2: Inversion -- recover f(r) from F(y)
# ---------------------------------------------------------------
print("\n[2] Abel inversion: projection -> radial distribution")

fr_onion = decomp.abel_onion(Fy_numerical, dr=dr)
fr_3pt   = decomp.abel_three_point(Fy_numerical, dr=dr)

# Trim edge (last pixel often inaccurate due to boundary)
check = slice(1, N - 5)
err_onion = np.linalg.norm(fr_onion[check] - fr_true[check]) / np.linalg.norm(fr_true[check])
err_3pt   = np.linalg.norm(fr_3pt[check]   - fr_true[check]) / np.linalg.norm(fr_true[check])

print(f"  Onion peeling  error vs ground truth: {err_onion:.4f}")
print(f"  Three-point    error vs ground truth: {err_3pt:.4f}")
print(f"  Peak (onion)  : f[0] = {fr_onion[0]:.4f}  (true: {fr_true[0]:.4f})")
print(f"  Peak (3-point): f[0] = {fr_3pt[0]:.4f}  (true: {fr_true[0]:.4f})")

# ---------------------------------------------------------------
# Part 3: Hollow sphere / bright ring (harder test)
# ---------------------------------------------------------------
print("\n[3] Harder test: hollow sphere (bright ring)")
print("    f(r) = ring at r=R with Gaussian width")

R = 8.0
width = 1.0
fr_ring = np.exp(-((r - R) / width) ** 2)
fr_ring[r > R + 4 * width] = 0.0

Fy_ring = decomp.abel_forward(fr_ring, dr=dr)

fr_ring_onion = decomp.abel_onion(Fy_ring, dr=dr)
fr_ring_3pt   = decomp.abel_three_point(Fy_ring, dr=dr)

# Peak position recovery
r_peak_true  = r[np.argmax(fr_ring)]
r_peak_onion = r[np.argmax(fr_ring_onion)]
r_peak_3pt   = r[np.argmax(fr_ring_3pt)]
print(f"  True ring center  : r = {r_peak_true:.3f}")
print(f"  Onion peak        : r = {r_peak_onion:.3f}  (err {abs(r_peak_onion-r_peak_true)/r_peak_true*100:.1f}%)")
print(f"  Three-point peak  : r = {r_peak_3pt:.3f}  (err {abs(r_peak_3pt-r_peak_true)/r_peak_true*100:.1f}%)")

# ---------------------------------------------------------------
# Part 4: Noise robustness
# ---------------------------------------------------------------
print("\n[4] Noise robustness (SNR ~ 50 added to projection)")

rng = np.random.default_rng(99)
noise_level = Fy_ring.max() / 50.0
Fy_noisy = Fy_ring + noise_level * rng.standard_normal(N)

fr_noisy_onion = decomp.abel_onion(Fy_noisy, dr=dr)
fr_noisy_3pt   = decomp.abel_three_point(Fy_noisy, dr=dr)

r_peak_on = r[np.argmax(fr_noisy_onion)]
r_peak_tp = r[np.argmax(fr_noisy_3pt)]
print(f"  True peak: {r_peak_true:.3f}")
print(f"  Noisy onion peak : {r_peak_on:.3f}  (err {abs(r_peak_on-r_peak_true)/r_peak_true*100:.1f}%)")
print(f"  Noisy 3-pt  peak : {r_peak_tp:.3f}  (err {abs(r_peak_tp-r_peak_true)/r_peak_true*100:.1f}%)")
print("  (Three-point typically less noisy than onion peeling at center)")

# ---------------------------------------------------------------
# Part 5: 2D image -- simulated plasma emission
# ---------------------------------------------------------------
print("\n[5] 2D image: simulated plasma emission (cylindrical symmetry)")

n_rows, n_cols = 120, 201
cx = n_cols // 2   # center column

x = np.arange(n_cols) - cx
y_ax = np.arange(n_rows) - n_rows // 2

X, Y = np.meshgrid(x, y_ax)
R_img = np.abs(X).astype(float)   # radial distance from axis (2D, using Abel convention)

# Each row: hollow emission ring profile (varying intensity along axis)
axial_profile = np.exp(-(y_ax / 20.0) ** 2)
ring_r = 25.0
ring_w = 4.0

image = np.zeros((n_rows, n_cols))
for i, ax_amp in enumerate(axial_profile):
    fr_row = ax_amp * np.exp(-((np.arange(n_cols // 2 + 1) - ring_r) / ring_w) ** 2)
    Fy_row = decomp.abel_forward(fr_row, dr=1.0)
    m = len(Fy_row)
    image[i, cx:cx + m] = Fy_row
    if cx > 0:
        ml = min(m - 1, cx)
        image[i, cx - ml:cx] = Fy_row[ml:0:-1]

print(f"  Image shape: {image.shape}")

# Find center (should detect cx = {cx})
cr_found, cc_found = decomp.abel_center(image)
print(f"  abel_center() found: col = {cc_found}  (true: {cx})")

# Invert with both methods
result_3pt   = decomp.abel_image(image, method="three_point", center=(cr_found, cc_found))
result_onion = decomp.abel_image(image, method="onion",       center=(cr_found, cc_found))

print(f"  Radial image shape: {result_3pt['radial'].shape}")

# Check ring recovery at central row (highest intensity)
mid_row = n_rows // 2
fr_mid_3pt   = result_3pt["radial"][mid_row, cx:]
fr_mid_onion = result_onion["radial"][mid_row, cx:]

peak_3pt   = np.argmax(fr_mid_3pt)
peak_onion = np.argmax(fr_mid_onion)
print(f"  Ring peak at pixel (true: {int(ring_r)}) -- 3pt: {peak_3pt}  onion: {peak_onion}")

# ---------------------------------------------------------------
# Part 6: Round-trip validation
# ---------------------------------------------------------------
print("\n[6] Round-trip: invert -> re-project -> compare with original")

reprojected = decomp.abel_forward_image(result_3pt["radial"],
                                         center=(cr_found, cc_found))
err_rt = np.linalg.norm(image - reprojected) / np.linalg.norm(image)
print(f"  Round-trip error (project(invert(image)) vs image): {err_rt:.4f}")
print("  (Should be small; remaining error from edge effects and discretisation)")

# ---------------------------------------------------------------
# Part 7: Viz (optional)
# ---------------------------------------------------------------
print("\n[7] Visualization (requires matplotlib)")
try:
    from anvil import viz
    viz.abel_compare(image, result_3pt, show=False)
    print("  abel_compare() figure created. Call plt.show() or fig.savefig().")
    viz.abel_compare(image, result_onion, show=False, cmap="inferno")
    print("  Second figure (onion, inferno colormap) created.")
except ImportError:
    print("  matplotlib not installed -- skipping.")
except Exception as e:
    print(f"  Viz skipped: {e}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
