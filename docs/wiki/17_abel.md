# Abel Transform

`anvil.decomp` includes forward and inverse Abel transforms for cylindrically symmetric data: plasma spectroscopy, combustion emission, ion velocity-map imaging, and any system where a camera measures a line-of-sight integral of a 3D radially symmetric source.

```python
import anvil.decomp as decomp
from anvil import viz
```

---

## Background

A cylindrically symmetric 3D distribution `f(r)` projects onto a 2D camera image as:

```
F(y) = 2 * integral_y^inf  f(r) * r / sqrt(r^2 - y^2)  dr   (forward Abel)
```

The inverse (Abel inversion) recovers `f(r)` from the measured projection `F(y)`:

```
f(r) = -(1/pi) * integral_r^inf  (dF/dy) / sqrt(y^2 - r^2)  dy
```

**Inputs and outputs:**

| Symbol | Meaning | In Anvil |
|--------|---------|---------|
| `f(r)` | True radial distribution (3D) | `fr` array, index 0 = center |
| `F(y)` | Measured camera projection (2D) | `Fy` array, index 0 = center |
| `dr` | Pixel size (any length unit) | `dr` parameter |

---

## Quick Start

```python
import numpy as np
import anvil.decomp as decomp
from anvil import viz

# --- 1D: single row ---
N = 300
dr = 0.05
r = np.arange(N) * dr

fr_true = np.exp(-(r / 3.0)**2)              # Gaussian radial source
Fy = decomp.abel_forward(fr_true, dr=dr)      # simulate camera projection
fr_recovered = decomp.abel_three_point(Fy, dr=dr)   # invert

# --- 2D: full image ---
result = decomp.abel_image(camera_frame, method="three_point")
viz.abel_compare(camera_frame, result)
```

---

## `abel_forward` -- Forward Transform

```python
Fy = decomp.abel_forward(fr, dr=1.0)
```

Computes the Abel projection using exact analytical pixel-strip integration.

**Returns:** `ndarray (N,)` — projection values `F(y[k])` at `y[k] = k * dr`.

**Analytic check:** for `f(r) = exp(-r^2/s^2)`:
```
F(y) = s * sqrt(pi) * exp(-y^2 / s^2)
```

```python
sigma = 3.0
fr = np.exp(-(r / sigma)**2)
Fy = decomp.abel_forward(fr, dr=dr)
Fy_analytic = sigma * np.sqrt(np.pi) * np.exp(-(r / sigma)**2)
# relative error ~ 1e-4 for N=300, dr=0.05
```

---

## `abel_three_point` -- Inversion (recommended)

```python
fr = decomp.abel_three_point(Fy, dr=1.0)
```

Inverse Abel transform using the Dasch (1992) three-point operator. Evaluates the derivative formulation analytically with a log-kernel, producing less noise amplification than onion peeling.

**When to use:** Default choice for most data. Handles both smooth and moderately noisy projections. Noise increases toward the center (r=0) but less severely than onion peeling.

**Center point:** The `r=0` pixel is computed from the kernel formula using the even-symmetry boundary condition `F(-y) = F(y)` (so `dF/dy = 0` at `y=0`). No extrapolation is applied by default.

```python
fr = decomp.abel_three_point(Fy, dr=dr)

# For noisy data: smooth F before inverting
from scipy.ndimage import gaussian_filter1d
Fy_smooth = gaussian_filter1d(Fy, sigma=1.5)
fr_smooth = decomp.abel_three_point(Fy_smooth, dr=dr)
```

---

## `abel_onion` -- Inversion (onion peeling)

```python
fr = decomp.abel_onion(Fy, dr=1.0)
```

Backward substitution on the forward Abel matrix, working from the outermost shell inward. Each shell's error propagates to all inner shells — noise amplifies toward the center.

**When to use:** High SNR data, or when an exact matrix-inversion approach is needed. For noisy data, prefer `abel_three_point`.

```python
fr_op = decomp.abel_onion(Fy, dr=dr)
```

---

## `abel_center` -- Find Axis of Symmetry

```python
center_row, center_col = decomp.abel_center(image, search_range=None)
```

Finds the vertical axis of symmetry by minimizing L2 asymmetry between the left and right halves of the column-summed projection. Searches within `search_range` pixels of `n_cols // 2`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `image` | required | `(n_rows, n_cols)` array |
| `search_range` | `n_cols // 8` | Search half-width in pixels |

**Returns:** `(center_row, center_col)` both integers. `center_row = n_rows // 2` (axis assumed vertical).

```python
cr, cc = decomp.abel_center(frame)
print(f"Symmetry axis at column {cc}")

# Narrow the search if you know the approximate center
cr, cc = decomp.abel_center(frame, search_range=10)
```

**Limitations:** Assumes a single vertical axis of symmetry. Works best when the source is bright and the background is low. For off-center or tilted sources, crop the image first.

---

## `abel_image` -- 2D Image Inversion

```python
result = decomp.abel_image(image, method="three_point", center=None,
                            dr=1.0, half="average")
```

Applies 1D Abel inversion to each row of a 2D image independently. The axis of symmetry is assumed to be vertical (constant column index across all rows).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `image` | required | Camera frame, shape `(n_rows, n_cols)` |
| `method` | `"three_point"` | `"three_point"` or `"onion"` |
| `center` | None | `(row, col)`; auto-detected with `abel_center()` if None |
| `dr` | 1.0 | Physical pixel size |
| `half` | `"average"` | `"right"`, `"left"`, or `"average"` (average both halves) |

**Returns dict:**

| Key | Description |
|-----|-------------|
| `"radial"` | `(n_rows, n_cols)` Abel-inverted image |
| `"center"` | `(row, col)` of symmetry axis used |
| `"method"` | method string |
| `"n_radial"` | half-width in pixels |

```python
# Basic usage
result = decomp.abel_image(frame)
radial = result["radial"]

# With known center
result = decomp.abel_image(frame, center=(60, 256), method="three_point")

# Left half only (if right half is obscured)
result = decomp.abel_image(frame, half="left")
```

**`half` parameter:**
- `"average"` (default): averages both halves before inversion — best SNR, assumes good symmetry
- `"right"` / `"left"`: uses only one side — useful when the other is blocked or noisy
- Both sides are always written to the output image (mirrored)

---

## `abel_forward_image` -- Forward Project a Radial Image

```python
Fy_image = decomp.abel_forward_image(fr_image, center=None, dr=1.0)
```

Applies the forward Abel transform to each row of a 2D radial distribution, producing the simulated camera projection. Primary use: round-trip validation.

```python
result = decomp.abel_image(frame)
reprojected = decomp.abel_forward_image(result["radial"],
                                         center=result["center"])
err = np.linalg.norm(frame - reprojected) / np.linalg.norm(frame)
print(f"Round-trip error: {err:.4f}")   # should be small (< 0.05)
```

---

## Visualization

### `viz.abel_compare(image, abel_result, ...)`

Side-by-side figure: raw projection (left) vs Abel-inverted radial distribution (right). A cyan dashed line marks the detected symmetry axis.

```python
from anvil import viz

result = decomp.abel_image(frame)
viz.abel_compare(frame, result)

# Options
viz.abel_compare(frame, result, cmap="inferno", log_scale=True)

# Save without display
fig = viz.abel_compare(frame, result, show=False)
fig.savefig("abel_inversion.png", dpi=150, bbox_inches="tight")
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `image` | required | Original projection |
| `abel_result` | required | Dict from `abel_image()` |
| `ax` | None | Array of 2 Axes |
| `show` | True | Call `plt.show()` |
| `cmap` | `"hot"` | Matplotlib colormap |
| `log_scale` | False | Apply `log1p` (useful for high dynamic range) |

---

## Full Workflow Example

```python
import numpy as np
import anvil.decomp as decomp
from anvil import viz

# Load image (e.g. from a camera or simulation)
frame = np.load("plasma_emission.npy")   # shape (480, 640)

# Step 1: find axis of symmetry
cr, cc = decomp.abel_center(frame, search_range=20)
print(f"Axis at column {cc}")

# Step 2: invert
result = decomp.abel_image(
    frame,
    method="three_point",
    center=(cr, cc),
    dr=0.05,          # 50 microns per pixel
    half="average",
)

# Step 3: visualize
viz.abel_compare(frame, result, cmap="hot", log_scale=True)

# Step 4: extract radial profile at a specific row
radial = result["radial"]
mid_row = result["center"][0]
r_profile = radial[mid_row, cc:]      # half-profile from center outward
r_axis = np.arange(len(r_profile)) * 0.05   # physical r in mm

# Step 5: validate with round-trip
reprojected = decomp.abel_forward_image(radial, center=(cr, cc), dr=0.05)
err = np.linalg.norm(frame - reprojected) / np.linalg.norm(frame)
print(f"Round-trip error: {err:.4f}")
```

---

## Method Comparison

| Method | Noise sensitivity | Speed | Center accuracy | Best for |
|--------|-------------------|-------|-----------------|---------|
| `three_point` | Low-moderate | O(N^2) | Good | General purpose (default) |
| `onion` | High at center | O(N^2) | Moderate | Clean/simulated data |

Both methods are O(N^2) per row (matrix operations). For a 500-column image with 500 rows: ~0.2 s per method on a modern CPU.

---

## Limits and Gotchas

| Issue | Detail |
|-------|--------|
| Noise at center | Both methods amplify noise toward r=0. Pre-smooth Fy with `gaussian_filter1d(Fy, sigma=1-2)` before inverting noisy data. |
| Non-symmetric image | `half="average"` improves SNR but amplifies errors if the image is not truly symmetric. Check with `half="right"` vs `half="left"` separately. |
| Center accuracy | `abel_center()` works to the nearest pixel. Sub-pixel centering reduces artifacts; for high-precision work, find the center externally and pass it explicitly. |
| Edge effects | The outermost 2-3 pixels of the inverted image are unreliable (boundary treatment). Trim them before analysis. |
| Background | Non-zero background in F(y) introduces a spike at r=0 in the inversion. Subtract background from Fy before inverting. |
| Memory | Each `abel_image()` call builds an N x N matrix per row. For N=1000: 8 MB per row. Use `half="right"` or `half="left"` (smaller N) for very wide images. |
| Layer 2 (PyAbel) | BASEX, rbasex, DAUN (regularized), Hansen-Law — higher accuracy for difficult data — will be added as a PyAbel adapter. |
