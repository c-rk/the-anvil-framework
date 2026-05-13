# Decomposition: POD and DMD

`anvil.decomp` provides data-driven decomposition methods for engineering signals and snapshot matrices. No additional dependencies beyond NumPy.

```python
import anvil.decomp as decomp
# or
from anvil import decomp
```

---

## Overview

| Method | Full name | What it gives you |
|--------|-----------|-------------------|
| POD | Proper Orthogonal Decomposition | Orthogonal spatial modes ranked by energy (variance) |
| DMD | Dynamic Mode Decomposition | Spatial modes + complex eigenvalues (frequency + growth rate) |

Both operate on **snapshot matrices** `X` of shape `(n_space, n_time)`. For 1D signals, use `hankel()` to create the matrix first.

---

## Quick Start

```python
import numpy as np
import anvil.decomp as decomp

# 1D signal with two frequencies
dt = 0.005
t  = np.arange(0, 8, dt)
x  = np.sin(2*np.pi*3*t) + 0.4*np.sin(2*np.pi*11*t)

# 1. Embed into Hankel matrix
H = decomp.hankel(x, window=len(t)//4)    # (400, 1201)

# 2. POD — energy decomposition
pod = decomp.pod(H, r=10)
print(decomp.pod_rank(pod, 0.99))          # modes needed for 99% energy

# 3. DMD — frequency identification
dmd = decomp.dmd(H, dt=dt, r=10)
idx = decomp.dmd_dominant(dmd, n=4)
print(dmd["frequencies"][idx])             # → ±3 Hz, ±11 Hz

# 4. Reconstruct
X_hat = decomp.dmd_reconstruct(dmd, n_steps=H.shape[1])
```

---

## `hankel` — 1D Signal Embedding

```python
H = decomp.hankel(x, window)
```

Embeds a scalar time series into a Hankel (trajectory) matrix by sliding a window along the signal. Each column of `H` is one window-length snapshot.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | array, shape (N,) | 1D signal |
| `window` | int | Embedding dimension (number of rows) |

**Returns:** `ndarray`, shape `(window, N - window + 1)`

**Window size rule of thumb:** `N // 4` to `N // 3`. Larger window → more spatial resolution in POD/DMD modes, fewer time columns. Too large → too few columns for meaningful SVD.

```python
t = np.linspace(0, 10, 2000)
x = np.sin(2*np.pi*5*t)

H = decomp.hankel(x, window=400)   # shape (400, 1601)
# H[:, k] = x[k : k+400]          — window starting at sample k
```

**Why Hankel?** POD and DMD are defined for multi-dimensional snapshot data. The Hankel embedding converts a 1D time series into a pseudo-spatial problem — each row corresponds to a "lag", enabling the methods to identify frequency content and reconstruct the signal.

---

## `pod` — Proper Orthogonal Decomposition

```python
result = decomp.pod(X, r=None, subtract_mean=True)
```

Decomposes `X = U S Vt` (economy SVD) where columns of `U` are orthonormal spatial modes ranked by their singular value (energy content).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `X` | required | Snapshot matrix, shape `(n_space, n_time)` |
| `r` | None | Modes to retain; None = all non-zero |
| `subtract_mean` | True | Remove temporal mean before decomposition |

**Returns dict:**

| Key | Shape | Description |
|-----|-------|-------------|
| `"modes"` | `(n_space, r)` | Orthonormal spatial modes |
| `"singular_values"` | `(r,)` | Ranked descending |
| `"temporal_coefficients"` | `(r, n_time)` | Time evolution of each mode |
| `"energy_fractions"` | `(r,)` | Fraction of total variance per mode |
| `"cumulative_energy"` | `(r,)` | `cumsum(energy_fractions)` |
| `"mean"` | `(n_space,)` | Subtracted mean (zeros if `subtract_mean=False`) |
| `"rank"` | int | Actual number of modes retained |

**SciPy backend:** `numpy.linalg.svd` (economy, `full_matrices=False`)

### POD energy interpretation

```python
pod = decomp.pod(X, r=20)

# How many modes for 99% energy?
r99 = decomp.pod_rank(pod, 0.99)

# Fraction captured by first 5 modes
print(pod["cumulative_energy"][4])     # index 4 = mode 5

# Is the data low-rank? Steep drop in singular values → yes
print(pod["singular_values"])
```

Energy fraction measures what fraction of the total variance (Frobenius norm squared) is captured by each mode. A fast decay indicates a low-dimensional structure in the data.

### Example

```python
# 64-sensor vibration measurement, 500 snapshots
X = load_sensor_data()    # shape (64, 500)

pod = decomp.pod(X, r=8)

print(f"Top mode: {pod['energy_fractions'][0]*100:.1f}% of variance")
print(f"Modes for 99%: {decomp.pod_rank(pod, 0.99)}")

# Mode shapes (spatial patterns)
mode1_shape = pod["modes"][:, 0]   # first bending mode

# Temporal coefficients (how each mode evolves in time)
mode1_time = pod["temporal_coefficients"][0, :]
```

---

## `pod_reconstruct` — Reconstruct from POD Modes

```python
X_hat = decomp.pod_reconstruct(pod_result, r=None)
```

Rebuilds the snapshot matrix from `r` POD modes. Mean is added back automatically.

| Parameter | Description |
|-----------|-------------|
| `pod_result` | Dict from `pod()` |
| `r` | Use first r modes; None = all retained |

**Returns:** `ndarray (n_space, n_time)` — `U[:,:r] @ TC[:r,:] + mean`

```python
pod = decomp.pod(X)

# Reconstruction with increasing rank
for r in [2, 5, 10]:
    X_hat = decomp.pod_reconstruct(pod, r=r)
    err = np.linalg.norm(X - X_hat) / np.linalg.norm(X)
    print(f"r={r}: error = {err:.3f}  (cumE = {pod['cumulative_energy'][r-1]:.3f})")
```

---

## `pod_project` — Project onto Existing Basis

```python
coefficients = decomp.pod_project(pod_result, X_new, subtract_mean=True)
```

Projects new snapshot data onto a pre-computed POD basis. Useful for reduced-order evaluation of new data without recomputing the SVD.

| Parameter | Description |
|-----------|-------------|
| `pod_result` | From `pod()` |
| `X_new` | New snapshots, shape `(n_space, n_time_new)` |
| `subtract_mean` | Subtract training mean (default True) |

**Returns:** `ndarray (r, n_time_new)` — modal amplitudes of `X_new` in the POD basis.

```python
# Train POD on first half of data
pod_train = decomp.pod(X[:, :250], r=10)

# Project second half (new data) onto training modes
coeff_test = decomp.pod_project(pod_train, X[:, 250:])
# coeff_test.shape = (10, 250)
```

---

## `pod_rank` — Minimum Modes for Target Energy

```python
r = decomp.pod_rank(pod_result, target_energy=0.99)
```

Returns the minimum number of modes needed to capture `target_energy` fraction of total variance.

```python
pod = decomp.pod(X)
print(decomp.pod_rank(pod, 0.90))   # 90%
print(decomp.pod_rank(pod, 0.99))   # 99%
print(decomp.pod_rank(pod, 0.999))  # 99.9%
```

---

## `dmd` — Dynamic Mode Decomposition

```python
result = decomp.dmd(X, dt=1.0, r=None, threshold=None)
```

Exact DMD (Tu et al. 2014). Fits a linear operator `A` such that `x(t+dt) ≈ A x(t)` and returns its eigendecomposition.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `X` | required | Snapshot matrix, shape `(n_space, n_time)`. Consecutive columns must be `dt` apart |
| `dt` | 1.0 | Time step between snapshots |
| `r` | None | SVD truncation rank for noise filtering |
| `threshold` | None | Keep singular values above `threshold × s_max`. Default `1e-10` when `r` is None |

**Returns dict:**

| Key | Shape | Description |
|-----|-------|-------------|
| `"eigenvalues"` | `(r,)` complex | Discrete-time: `|λ|>1` growing, `<1` decaying, `=1` neutral |
| `"omega"` | `(r,)` complex | Continuous-time: `log(λ)/dt` |
| `"modes"` | `(n_space, r)` complex | Spatial DMD modes |
| `"amplitudes"` | `(r,)` complex | Initial amplitude of each mode |
| `"frequencies"` | `(r,)` float | `Im(ω) / (2π)` — oscillation frequency in `1/dt_unit` |
| `"growth_rates"` | `(r,)` float | `Re(ω)` — positive = growing, negative = decaying |
| `"singular_values"` | `(r,)` float | SVD singular values used |

### Rank selection

- `r` specified: use exactly `r` modes (set `r` small to filter noise)
- `threshold` specified: keep modes where `s_i > threshold × s_max`
- Neither: use `threshold=1e-10` (keeps nearly all non-zero modes)

**Rule of thumb for noisy data:** Start with `r=2×(expected modes)` — DMD modes come in conjugate pairs for real-valued signals.

### Reading eigenvalues

```python
dmd_r = decomp.dmd(H, dt=0.005, r=12)

# Discrete-time eigenvalues
evals = dmd_r["eigenvalues"]
# |λ| < 1 → decaying;  |λ| > 1 → growing;  |λ| ≈ 1 → neutral/oscillatory

# Continuous-time frequency (Hz if dt is in seconds)
freqs = dmd_r["frequencies"]       # Im(log(λ)/dt) / (2π)
grows = dmd_r["growth_rates"]      # Re(log(λ)/dt)

# Example output for a 3 Hz + 11 Hz signal:
# freqs ≈ [+3.0, -3.0, +11.0, -11.0, ...]
# grows ≈ [~0,   ~0,   ~0,    ~0,   ...]  (stable modes)
```

**Conjugate pairs:** Real-valued signals always produce complex-conjugate eigenvalue pairs. The positive-frequency mode is the physical one; the negative-frequency mode is its mirror image. Both have the same amplitude and growth rate.

### Example: frequency identification

```python
import numpy as np
import anvil.decomp as decomp

dt = 0.005
t  = np.arange(0, 8, dt)
x  = np.sin(2*np.pi*3*t) + 0.4*np.sin(2*np.pi*11*t)

H = decomp.hankel(x, window=400)
dmd_r = decomp.dmd(H, dt=dt, r=8)

# Get dominant modes
idx = decomp.dmd_dominant(dmd_r, n=4, by="amplitude")
for i in idx:
    print(f"  f = {dmd_r['frequencies'][i]:+.2f} Hz  "
          f"  growth = {dmd_r['growth_rates'][i]:+.3f}  "
          f"  |amp| = {abs(dmd_r['amplitudes'][i]):.3f}")
# Output:
#   f =  +3.00 Hz   growth =  +0.001   |amp| = ...
#   f =  -3.00 Hz   growth =  +0.001   |amp| = ...
#   f = +11.00 Hz   growth =  +0.001   |amp| = ...
#   f = -11.00 Hz   growth =  +0.001   |amp| = ...
```

---

## `dmd_reconstruct` — Reconstruct from DMD Modes

```python
X_hat = decomp.dmd_reconstruct(dmd_result, n_steps=None, t=None)
```

Reconstructs the snapshot matrix (or extrapolates into the future) using `X_hat[:, k] = Re(Φ diag(b) λ^k)`.

| Parameter | Description |
|-----------|-------------|
| `dmd_result` | Dict from `dmd()` |
| `n_steps` | Number of time steps to generate |
| `t` | Time array; `n_steps = len(t)` (overrides `n_steps`) |

**Returns:** `ndarray (n_space, n_steps)`, real part only.

```python
dmd_r = decomp.dmd(H, dt=0.005, r=8)

# Reconstruct training window
X_train = decomp.dmd_reconstruct(dmd_r, n_steps=H.shape[1])

# Predict future (extrapolate)
n_future = H.shape[1] + 200
X_future = decomp.dmd_reconstruct(dmd_r, n_steps=n_future)

# Error on training data
err = np.linalg.norm(H - X_train) / np.linalg.norm(H)
```

**Extrapolation validity:** DMD extrapolates by raising eigenvalues to higher powers (`λ^k`). Stable modes (`|λ|≤1`) extrapolate reliably; growing modes (`|λ|>1`) will eventually diverge. Check `growth_rates` before extrapolating.

---

## `dmd_dominant` — Rank Modes by Importance

```python
indices = decomp.dmd_dominant(dmd_result, n=5, by="amplitude")
```

Returns indices of the `n` most dominant DMD modes.

| `by` | Ranking criterion |
|------|-------------------|
| `"amplitude"` | `|b_i|` — initial amplitude (default) |
| `"energy"` | `|b_i|²` — initial energy |
| `"growth"` | `Re(ω_i)` — most rapidly growing first |

```python
# Top 4 by amplitude
idx = decomp.dmd_dominant(dmd_r, n=4, by="amplitude")

# Top 3 growing modes (stability analysis)
growing = decomp.dmd_dominant(dmd_r, n=3, by="growth")
print(dmd_r["growth_rates"][growing])   # all positive
```

---

## Visualization

```python
from anvil import viz

# POD: singular value spectrum + cumulative energy
viz.pod_energy(pod_result, threshold=0.99)

# DMD: eigenvalue spectrum in complex plane
viz.dmd_spectrum(dmd_result, unit_circle=True)
```

### `viz.pod_energy(pod_result, ax=None, show=True, threshold=0.99)`

Two-panel figure:
- **Left:** Bar chart of singular values (log scale)
- **Right:** Cumulative energy % with guide line at `threshold` and annotation of how many modes are needed

### `viz.dmd_spectrum(dmd_result, ax=None, show=True, unit_circle=True)`

Complex eigenvalue plane scatter plot:
- Marker **size and color** encode normalized amplitude
- **Unit circle** drawn at `|λ|=1` — modes inside are stable, outside are growing
- Colorbar shows normalized amplitude

```python
# Save without displaying
fig = viz.pod_energy(pod, show=False)
fig.savefig("pod_energy.png", dpi=150, bbox_inches="tight")

fig2 = viz.dmd_spectrum(dmd_r, show=False)
fig2.savefig("dmd_spectrum.png", dpi=150, bbox_inches="tight")
```

---

## Multi-Dimensional Data (CFD / Sensor Arrays)

For data already in snapshot-matrix form, skip `hankel()`:

```python
# CFD: pressure field at 128×128 grid, 300 snapshots
# Shape: (128*128, 300) = (16384, 300)
X_cfd = load_snapshots()   # (n_space, n_time)

pod_cfd = decomp.pod(X_cfd, r=20)
dmd_cfd = decomp.dmd(X_cfd, dt=time_step, r=20)

# Most energetic mode shape (reshape to spatial grid)
mode1 = pod_cfd["modes"][:, 0].reshape(128, 128)

# Dominant DMD frequency
idx = decomp.dmd_dominant(dmd_cfd, n=2)
print(dmd_cfd["frequencies"][idx])
```

---

## Algorithm Details

### POD

1. Subtract temporal mean: `Xc = X - mean(X, axis=1)`
2. Economy SVD: `U, s, Vt = svd(Xc)`
3. Modes `U[:,i]` ranked by `s_i²` (energy)
4. Temporal coefficients: `diag(s) @ Vt`

### DMD (exact, Tu 2014)

1. Split: `X1 = X[:,:-1]`, `X2 = X[:,1:]`
2. SVD of X1: `U_r, s_r, Vt_r` (truncated to rank r)
3. Reduced operator: `Ã = U_r† X2 Vt_r† diag(1/s_r)` — shape `(r,r)`
4. Eigendecompose Ã: `Ã W = W diag(λ)`
5. Exact modes: `Φ = X2 Vt_r† diag(1/s_r) W diag(1/λ)`
6. Amplitudes b: least-squares fit `Φ b ≈ x(0)`
7. Continuous eigenvalues: `ω = log(λ)/dt`

---

## Limits and Gotchas

| Issue | Detail |
|-------|--------|
| Conjugate pairs | Real signals always produce `±freq` pairs. Both represent the same physical mode. |
| Rank choice | Too high → noise modes appear. Too low → real modes merged. Start with 2× expected physical modes. |
| Window size | For `hankel()`, window too small → poor frequency resolution. Too large → fewer columns → noisy SVD. |
| Growing DMD modes | `|λ|>1` extrapolation diverges. Only extrapolate stable or neutral modes. |
| POD vs DMD | POD sorts by energy, DMD sorts by dynamics. A low-energy mode can be physically important (e.g., an unstable growing mode). |
| `subtract_mean` | Default True for POD. Set False when passing Hankel matrix to DMD (DMD already handles the dynamics without mean subtraction). |
| Complex modes | DMD modes are complex. `np.real(mode)` gives the oscillatory part; `np.abs(mode)` gives the amplitude envelope. |
