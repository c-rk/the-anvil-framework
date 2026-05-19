"""
Example 18: POD and DMD Signal Decomposition
=============================================

Demonstrates:
    - hankel() to embed 1D signals into snapshot matrices
    - pod() for energy-ranked spatial modes
    - pod_rank() to select truncation from energy threshold
    - pod_reconstruct() and error analysis
    - dmd() for frequency and growth rate identification
    - dmd_reconstruct() for signal synthesis
    - dmd_dominant() to rank modes by amplitude
    - Multi-dimensional snapshot matrix (simulated sensor array)
    - viz.pod_energy() and viz.dmd_spectrum() (matplotlib, optional)

Engineering context:
    Decompose vibration sensor data to identify dominant frequencies,
    separate signal from noise, and build a reduced-order model.
    Then demonstrate on a simulated 2D pressure field.
"""

import sys, os
import numpy as np

import anvil
import anvil.decomp as decomp

print("=" * 60)
print("  Example 18: POD and DMD Decomposition")
print("=" * 60)

rng = np.random.default_rng(42)


# --------------------------------------------------------------
# Part 1: Synthetic 1D signal — known frequencies
# --------------------------------------------------------------
print("\n[1] Synthetic signal: 3 Hz + 11 Hz + noise")

dt   = 0.005          # 200 Hz sample rate
t    = np.arange(0, 8, dt)
N    = len(t)

# True signal: two sinusoids + broadband noise
x = (1.0 * np.sin(2*np.pi*3*t)
   + 0.4 * np.sin(2*np.pi*11*t + 0.7)
   + 0.08 * rng.standard_normal(N))

print(f"  Signal length: {N} samples  ({t[-1]:.1f} s at {1/dt:.0f} Hz)")

# --------------------------------------------------------------
# Part 2: Hankel embedding
# --------------------------------------------------------------
print("\n[2] Hankel embedding")

window = N // 4     # rule of thumb: N/4 to N/3
H = decomp.hankel(x, window=window)
print(f"  window = {window},  Hankel shape = {H.shape}  (rows x columns)")
print(f"  Each column: one {window}-sample snapshot")

# --------------------------------------------------------------
# Part 3: POD
# --------------------------------------------------------------
print("\n[3] POD — energy decomposition")

pod_r = decomp.pod(H)   # all modes first

print(f"  Total modes retained: {pod_r['rank']}")
print(f"  Singular values (top 6): {pod_r['singular_values'][:6].round(1)}")
print(f"  Energy per mode  (top 6): {(pod_r['energy_fractions'][:6]*100).round(2)} %")
print(f"  Cumulative energy (top 6): {(pod_r['cumulative_energy'][:6]*100).round(2)} %")

r_99   = decomp.pod_rank(pod_r, 0.99)
r_999  = decomp.pod_rank(pod_r, 0.999)
print(f"\n  Modes for 99.0% energy : {r_99}")
print(f"  Modes for 99.9% energy : {r_999}")

# --------------------------------------------------------------
# Part 4: POD reconstruction
# --------------------------------------------------------------
print("\n[4] POD reconstruction error vs rank")

for r in [2, 4, 6, 10, 20]:
    X_hat = decomp.pod_reconstruct(pod_r, r=r)
    err = np.linalg.norm(H - X_hat) / np.linalg.norm(H)
    # Recover 1D signal from first row of reconstruction
    x_hat = X_hat[0, :]
    print(f"  r={r:3d}  matrix error = {err:.4f}  "
          f"  cumE = {pod_r['cumulative_energy'][r-1]*100:.2f}%")

# --------------------------------------------------------------
# Part 5: DMD — frequency identification
# --------------------------------------------------------------
print("\n[5] DMD — frequency and growth rate identification")

dmd_r = decomp.dmd(H, dt=dt, r=12)

print(f"  DMD rank used : {len(dmd_r['eigenvalues'])}")
print(f"  {'Mode':>4}  {'|eval|':>8}  {'Freq (Hz)':>12}  {'Growth rate':>12}  {'|Amplitude|':>12}")
print(f"  {'-'*55}")

dom_idx = decomp.dmd_dominant(dmd_r, n=8, by="amplitude")
for i in dom_idx:
    lam  = dmd_r["eigenvalues"][i]
    freq = dmd_r["frequencies"][i]
    grow = dmd_r["growth_rates"][i]
    amp  = np.abs(dmd_r["amplitudes"][i])
    print(f"  {i:4d}  {abs(lam):8.5f}  {freq:+12.4f}  {grow:+12.4f}  {amp:12.4f}")

print("\n  Note: dominant frequencies should match +/-3 Hz and +/-11 Hz")

# --------------------------------------------------------------
# Part 6: DMD reconstruction
# --------------------------------------------------------------
print("\n[6] DMD reconstruction")

X_dmd = decomp.dmd_reconstruct(dmd_r, n_steps=H.shape[1])
dmd_err = np.linalg.norm(H - X_dmd) / np.linalg.norm(H)
print(f"  Reconstruction error (r=12): {dmd_err:.4f}")

# Future prediction: extend 20% beyond training data
n_future = H.shape[1] + int(0.2 * H.shape[1])
X_future = decomp.dmd_reconstruct(dmd_r, n_steps=n_future)
print(f"  Extended to {n_future} steps ({n_future*dt:.2f} s) for future prediction")
print(f"  (DMD extrapolates via eigenvalue powers — valid for stable modes)")

# --------------------------------------------------------------
# Part 7: Multi-dim snapshot matrix (simulated sensor array)
# --------------------------------------------------------------
print("\n[7] Multi-dimensional snapshot matrix: 64-sensor vibration array")

n_sensors   = 64
n_snapshots = 500
dt_vib      = 1e-3     # 1 kHz

# Simulated: mode 1 at 80 Hz decaying, mode 2 at 220 Hz growing slightly
t_vib = np.arange(n_snapshots) * dt_vib
locs  = np.linspace(0, 1, n_sensors)

mode1_space = np.sin(np.pi * locs)           # first bending mode
mode2_space = np.sin(2 * np.pi * locs)       # second bending mode

mode1_time = np.exp(-0.5*t_vib) * np.sin(2*np.pi*80*t_vib)
mode2_time = np.exp(0.3*t_vib)  * np.sin(2*np.pi*220*t_vib) * 0.3

X_vib = (np.outer(mode1_space, mode1_time)
        + np.outer(mode2_space, mode2_time)
        + 0.02 * rng.standard_normal((n_sensors, n_snapshots)))

print(f"  Snapshot matrix shape: {X_vib.shape}  (sensors x time)")

# POD on vibration data
pod_vib = decomp.pod(X_vib, r=6)
print(f"\n  POD energy (top 6 modes):")
for i in range(6):
    bar = "#" * int(pod_vib["energy_fractions"][i] * 50)
    print(f"    Mode {i+1}: {pod_vib['energy_fractions'][i]*100:6.2f}%  {bar}")

# DMD on vibration data
dmd_vib = decomp.dmd(X_vib, dt=dt_vib, r=6)
print(f"\n  DMD dominant frequencies (top 4 by amplitude):")
idx_vib = decomp.dmd_dominant(dmd_vib, n=4, by="amplitude")
for i in idx_vib:
    freq = abs(dmd_vib["frequencies"][i])
    grow = dmd_vib["growth_rates"][i]
    amp  = np.abs(dmd_vib["amplitudes"][i])
    stab = "DECAYING" if grow < -0.1 else ("GROWING" if grow > 0.1 else "neutral")
    print(f"    freq = {freq:7.1f} Hz   growth = {grow:+.2f}   amp = {amp:.2f}  [{stab}]")

print("\n  (Should identify ~80 Hz decaying + ~220 Hz growing modes)")

# POD projection: project last 50 snapshots onto training basis
coeff = decomp.pod_project(pod_vib, X_vib[:, -50:])
print(f"\n  pod_project(): projected last 50 snapshots -> coefficients shape {coeff.shape}")

# --------------------------------------------------------------
# Part 8: Viz (optional — skipped if no matplotlib)
# --------------------------------------------------------------
print("\n[8] Visualization (requires matplotlib)")
try:
    from anvil import viz
    viz.pod_energy(pod_r, show=False)
    viz.dmd_spectrum(dmd_r, show=False)
    print("  Figures created. Call plt.show() or save with fig.savefig().")
    print("  (Running headless — no display. Remove show=False for interactive use.)")
except ImportError:
    print("  matplotlib not installed — skipping plots.")
except Exception as e:
    print(f"  Viz skipped: {e}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
