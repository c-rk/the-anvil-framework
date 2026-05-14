"""
Data decomposition: POD and DMD.

Both operate on snapshot matrices X of shape (n_space, n_time).
For 1D signals, use hankel() to embed into a trajectory matrix first.

Usage:
    import anvil.decomp as decomp

    # 1D signal
    H = decomp.hankel(x, window=50)

    # POD
    pod = decomp.pod(H, r=10)
    print(pod["cumulative_energy"])

    # DMD
    dmd = decomp.dmd(H, dt=0.01, r=20)
    print(dmd["frequencies"])          # Hz (or 1/dt_unit)

    # Reconstruct
    X_hat = decomp.dmd_reconstruct(dmd, n_steps=len(t))
    X_pod = decomp.pod_reconstruct(pod, r=5)

    # Project new data onto existing POD basis
    coeff = decomp.pod_project(pod, X_new)
"""

import numpy as np


# ============================================================
# Embedding
# ============================================================

def hankel(x, window):
    """
    Embed a 1D signal into a Hankel (trajectory) matrix.

    Shape: (window, N - window + 1). Each column is one window-length
    snapshot shifted by one sample. Converts a scalar time series into
    the (n_space, n_time) format expected by pod() and dmd().

    Parameters
    ----------
    x : array-like, shape (N,)
        1D signal.
    window : int
        Embedding dimension (number of rows). Rule of thumb: N // 3 to N // 2.

    Returns
    -------
    H : ndarray, shape (window, N - window + 1)

    Example
    -------
    t = np.linspace(0, 10, 1000)
    x = np.sin(2 * np.pi * 3 * t) + 0.5 * np.cos(2 * np.pi * 7 * t)
    H = anvil.decomp.hankel(x, window=200)
    dmd_result = anvil.decomp.dmd(H, dt=t[1] - t[0])
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    N = len(x)
    n_cols = N - window + 1
    if n_cols < 2:
        raise ValueError(
            f"Signal length {N} too short for window={window}. "
            f"Need N >= window + 1."
        )
    return np.lib.stride_tricks.sliding_window_view(x, window).T.copy()


# ============================================================
# POD
# ============================================================

def pod(X, r=None, subtract_mean=True):
    """
    Proper Orthogonal Decomposition via economy SVD.

    Decomposes snapshot matrix X ≈ U S Vt where columns of U are
    orthonormal spatial modes ranked by energy content (s_i^2).

    Parameters
    ----------
    X : array-like, shape (n_space, n_time)
        Snapshot matrix. Each column is one time snapshot.
    r : int or None
        Number of modes to retain. None = retain all non-zero modes.
    subtract_mean : bool
        Subtract temporal mean before decomposition (default True).

    Returns
    -------
    dict with keys:
        modes                 ndarray (n_space, r)  — orthonormal spatial modes
        singular_values       ndarray (r,)           — ranked descending
        temporal_coefficients ndarray (r, n_time)   — time evolution per mode
        energy_fractions      ndarray (r,)           — fraction of total energy
        cumulative_energy     ndarray (r,)           — cumsum of energy_fractions
        mean                  ndarray (n_space,)     — subtracted mean (zeros if subtract_mean=False)
        rank                  int                    — r actually retained

    Example
    -------
    X = np.random.randn(128, 500)  # 128 spatial pts, 500 snapshots
    result = anvil.decomp.pod(X, r=10)
    print(result["cumulative_energy"])  # energy captured by top-10 modes
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2:
        raise ValueError(f"X must be 2D (n_space, n_time), got shape {X.shape}")

    mean = X.mean(axis=1) if subtract_mean else np.zeros(X.shape[0])
    Xc = X - mean[:, np.newaxis]

    U, s, Vt = np.linalg.svd(Xc, full_matrices=False)

    if r is not None:
        r = min(int(r), len(s))
        U, s, Vt = U[:, :r], s[:r], Vt[:r, :]

    energy = s ** 2 / (s ** 2).sum()

    return {
        "modes": U,
        "singular_values": s,
        "temporal_coefficients": np.diag(s) @ Vt,
        "energy_fractions": energy,
        "cumulative_energy": np.cumsum(energy),
        "mean": mean,
        "rank": len(s),
    }


def pod_reconstruct(pod_result, r=None):
    """
    Reconstruct snapshot matrix from POD modes.

    Parameters
    ----------
    pod_result : dict
        Output from pod().
    r : int or None
        Use only first r modes. None = use all retained modes.

    Returns
    -------
    X_hat : ndarray (n_space, n_time)  — mean added back automatically.
    """
    U = pod_result["modes"]
    TC = pod_result["temporal_coefficients"]
    mean = pod_result["mean"]

    if r is not None:
        r = min(int(r), U.shape[1])
        U, TC = U[:, :r], TC[:r, :]

    return U @ TC + mean[:, np.newaxis]


def pod_project(pod_result, X_new, subtract_mean=True):
    """
    Project new snapshots onto existing POD basis.

    Useful for reduced-order evaluation or comparing datasets.

    Parameters
    ----------
    pod_result : dict
        From pod().
    X_new : array-like, shape (n_space, n_time_new)
    subtract_mean : bool
        Subtract the POD training mean before projection.

    Returns
    -------
    coefficients : ndarray (r, n_time_new)
        Modal amplitudes of X_new in the POD basis.
    """
    X_new = np.asarray(X_new, dtype=np.float64)
    U = pod_result["modes"]
    mean = pod_result["mean"]
    if subtract_mean:
        X_new = X_new - mean[:, np.newaxis]
    return U.T @ X_new


# ============================================================
# DMD
# ============================================================

def dmd(X, dt=1.0, r=None, threshold=None):
    """
    Dynamic Mode Decomposition — exact DMD (Tu et al. 2014).

    Fits a linear operator A such that x(t+dt) ≈ A x(t), then
    returns its spatiotemporal eigenmodes and eigenvalues.

    Parameters
    ----------
    X : array-like, shape (n_space, n_time)
        Snapshot matrix. Consecutive columns must be dt apart.
    dt : float
        Time step between snapshots.
    r : int or None
        SVD truncation rank for noise filtering. None = auto via threshold.
    threshold : float or None
        Keep singular values above threshold * s_max. Default 1e-10.
        Ignored when r is given.

    Returns
    -------
    dict with keys:
        eigenvalues     ndarray complex (r,)        — discrete: |λ|>1 growing, <1 decaying
        omega           ndarray complex (r,)        — continuous: log(λ)/dt
        modes           ndarray complex (n_space,r) — spatial DMD modes
        amplitudes      ndarray complex (r,)        — initial amplitude of each mode
        frequencies     ndarray float   (r,)        — Im(ω)/2π  [cycles per dt_unit]
        growth_rates    ndarray float   (r,)        — Re(ω); >0 growing, <0 decaying
        singular_values ndarray float   (r,)        — SVD values used in truncation

    Example
    -------
    t = np.linspace(0, 4, 400)
    x = np.sin(2*np.pi*3*t) + 0.5*np.sin(2*np.pi*7*t)
    H = anvil.decomp.hankel(x, window=80)
    result = anvil.decomp.dmd(H, dt=t[1]-t[0], r=8)
    print(result["frequencies"])   # should show ±3 Hz and ±7 Hz
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2:
        raise ValueError(f"X must be 2D (n_space, n_time), got shape {X.shape}")
    if X.shape[1] < 2:
        raise ValueError("Need at least 2 time snapshots for DMD.")

    X1 = X[:, :-1]
    X2 = X[:, 1:]

    # SVD of X1
    U, s, Vt = np.linalg.svd(X1, full_matrices=False)

    # Rank selection
    if r is not None:
        r = min(int(r), len(s))
    else:
        thr = (threshold if threshold is not None else 1e-10) * s[0]
        r = max(int(np.sum(s > thr)), 1)

    U_r, s_r, Vt_r = U[:, :r], s[:r], Vt[:r, :]
    S_inv = np.diag(1.0 / s_r)

    # Reduced linear operator: Ã = U_r† X2 V_r S_r⁻¹  (r × r)
    Atilde = U_r.T @ X2 @ Vt_r.T @ S_inv

    # Eigendecomposition of Ã
    evals, W = np.linalg.eig(Atilde)

    # Exact DMD modes: Φ = X2 V_r S_r⁻¹ W diag(1/λ)
    Phi = X2 @ Vt_r.T @ S_inv @ W / evals[np.newaxis, :]

    # Initial amplitudes — least-squares fit to first snapshot
    b = np.linalg.lstsq(Phi, X1[:, 0], rcond=None)[0]

    # Continuous-time eigenvalues
    omega = np.log(evals) / dt

    return {
        "eigenvalues": evals,
        "omega": omega,
        "modes": Phi,
        "amplitudes": b,
        "frequencies": omega.imag / (2.0 * np.pi),
        "growth_rates": omega.real,
        "singular_values": s_r,
    }


def dmd_reconstruct(dmd_result, n_steps=None, t=None):
    """
    Reconstruct snapshot matrix from DMD result.

    X_hat[:, k] = Re( Φ diag(b) λ^k )

    Parameters
    ----------
    dmd_result : dict
        Output from dmd().
    n_steps : int or None
        Number of time steps. Provide either n_steps or t.
    t : array-like or None
        Time array — n_steps inferred from len(t). Used for shape only.

    Returns
    -------
    X_hat : ndarray (n_space, n_steps)  — real part of reconstruction.
    """
    evals = dmd_result["eigenvalues"]
    modes = dmd_result["modes"]
    b = dmd_result["amplitudes"]

    if t is not None:
        n_steps = len(t)
    if n_steps is None:
        raise ValueError("Provide n_steps or t.")
    n_steps = int(n_steps)

    ks = np.arange(n_steps)
    # (r, n_steps): time_dyn[i, k] = b[i] * λ[i]^k
    time_dyn = b[:, np.newaxis] * (evals[:, np.newaxis] ** ks[np.newaxis, :])

    return np.real(modes @ time_dyn)


# ============================================================
# Utilities
# ============================================================

def dmd_dominant(dmd_result, n=5, by="amplitude"):
    """
    Return indices of the n most dominant DMD modes.

    Parameters
    ----------
    n : int
        Number of modes to return.
    by : str
        "amplitude" (default) — rank by |b_i|.
        "energy"    — rank by |b_i|^2.
        "growth"    — rank by Re(ω_i), most growing first.

    Returns
    -------
    indices : ndarray (n,)  — sorted indices into dmd_result arrays.
    """
    amps = np.abs(dmd_result["amplitudes"])
    if by == "amplitude":
        scores = amps
    elif by == "energy":
        scores = amps ** 2
    elif by == "growth":
        scores = dmd_result["growth_rates"]
    else:
        raise ValueError(f"Unknown ranking: '{by}'. Choose 'amplitude', 'energy', 'growth'.")
    return np.argsort(scores)[::-1][:n]


def pod_rank(pod_result, target_energy=0.99):
    """
    Return minimum number of POD modes needed to capture target energy fraction.

    Parameters
    ----------
    pod_result : dict
        From pod().
    target_energy : float
        Energy fraction in [0, 1]. Default 0.99 (99%).

    Returns
    -------
    int -- number of modes required.
    """
    ce = pod_result["cumulative_energy"]
    idx = np.searchsorted(ce, target_energy)
    return min(int(idx) + 1, pod_result["rank"])


# ============================================================
# Abel Transform
# ============================================================

def _abel_matrix(N):
    """
    Forward Abel projection matrix (dr=1, dimensionless pixel units).

    M[k, j] = 2 * (sqrt((j+0.5)^2 - k^2) - sqrt(lo^2 - k^2))  for j >= k
             = 0                                                   for j <  k

    where lo = max(j - 0.5, k) — the lower integration limit cannot go below
    the singularity at r = k (radial distance is non-negative).

    This matters only at k=0, j=0: without the clamp, sq_lo = sqrt(0.25) = 0.5
    instead of 0, making M[0,0] = 0 (wrong) instead of 1.0 (correct).

    Multiply by dr to get physical units: F = dr * M @ f.
    """
    k = np.arange(N, dtype=np.float64)
    j = np.arange(N, dtype=np.float64)
    K, J = np.meshgrid(k, j, indexing="ij")
    sq_hi = np.sqrt(np.maximum((J + 0.5) ** 2 - K ** 2, 0.0))
    # Lower limit: max(j - 0.5, k) — clamp so we never go below the singularity
    lo = np.maximum(J - 0.5, K)
    sq_lo = np.sqrt(np.maximum(lo ** 2 - K ** 2, 0.0))
    M = 2.0 * (sq_hi - sq_lo)
    M[K > J] = 0.0
    return M


def abel_forward(fr, dr=1.0):
    """
    Forward Abel transform: radial distribution f(r) -> projection F(y).

    F(y) = 2 * integral_y^inf  f(r) * r / sqrt(r^2 - y^2)  dr

    Uses exact analytical pixel-strip integration.

    Parameters
    ----------
    fr : array-like, shape (N,)
        Radial distribution. fr[0] = center (r=0), fr[N-1] = outer edge.
    dr : float
        Radial step size (any consistent length unit).

    Returns
    -------
    Fy : ndarray (N,) -- projection at positions y[k] = k * dr.

    Example
    -------
    r = np.arange(200)
    fr = np.exp(-((r - 60)**2) / 200)    # Gaussian ring
    Fy = anvil.decomp.abel_forward(fr)   # simulated camera image (one row)
    """
    fr = np.asarray(fr, dtype=np.float64)
    N = len(fr)
    return dr * (_abel_matrix(N) @ fr)


def abel_onion(Fy, dr=1.0):
    """
    Abel inversion by onion peeling (Dasch 1992).

    Solves the forward Abel system M*f = F/dr from the outside inward via
    backward substitution. Exact but amplifies noise toward the center
    (each shell error propagates inward).

    Parameters
    ----------
    Fy : array-like, shape (N,)
        Half-projection: Fy[0] = center, Fy[N-1] = outer edge.
    dr : float
        Pixel step size.

    Returns
    -------
    fr : ndarray (N,) -- radial distribution f(r).

    Notes
    -----
    For noisy data prefer abel_three_point(); for clean data both are equivalent.
    """
    Fy = np.asarray(Fy, dtype=np.float64)
    N = len(Fy)
    M = _abel_matrix(N)

    fr = np.zeros(N)
    for k in range(N - 1, -1, -1):
        rhs = Fy[k] / dr - (M[k, k+1:] @ fr[k+1:])
        diag = M[k, k]
        fr[k] = rhs / diag if diag > 1e-30 else 0.0
    return fr


def abel_three_point(Fy, dr=1.0):
    """
    Abel inversion using the three-point operator (Dasch 1992).

    Uses the derivative formulation:
        f(r) = -(1/pi) * integral_r^inf  (dF/dy) / sqrt(y^2 - r^2)  dy

    with central finite differences for dF/dy and an analytical log-kernel
    for the Abel integral. Less noise-amplification than onion peeling.

    Parameters
    ----------
    Fy : array-like, shape (N,)
        Half-projection: Fy[0] = center, Fy[N-1] = outer edge.
    dr : float
        Pixel step size.

    Returns
    -------
    fr : ndarray (N,) -- radial distribution.

    Notes
    -----
    The center pixel (r=0) uses the log-kernel formula directly; for very
    noisy data pass Fy through a 1D Gaussian/median filter before calling.
    """
    Fy = np.asarray(Fy, dtype=np.float64)
    N = len(Fy)

    # Boundary-padded F: F[-1] = F[1] (even symmetry), F[N] = 0
    F_ext = np.empty(N + 2)
    F_ext[0] = Fy[1] if N > 1 else 0.0
    F_ext[1:N + 1] = Fy
    F_ext[N + 1] = 0.0

    # Central differences: dF[j] = (F[j+1] - F[j-1]) / 2  (half-step, dimensionless)
    dF = (F_ext[2:] - F_ext[:-2]) / 2.0   # length N

    # Log-kernel weights W[k, j] (dimensionless)
    #   j > k : W = ln( (j+0.5 + sqrt((j+0.5)^2 - k^2)) /
    #                    (j-0.5 + sqrt((j-0.5)^2 - k^2)) )
    #   j = k : W = ln( (k+0.5 + sqrt((k+0.5)^2 - k^2)) / k )   (k >= 1)
    #   k = 0 : W[0,j] = ln((j+0.5)/(j-0.5))  for j >= 1; W[0,0] = 0 (dF[0]=0)
    k = np.arange(N, dtype=np.float64)
    j = np.arange(N, dtype=np.float64)
    K, J = np.meshgrid(k, j, indexing="ij")

    num = J + 0.5 + np.sqrt(np.maximum((J + 0.5) ** 2 - K ** 2, 0.0))
    # lower limit: k (diagonal) or j-0.5 (off-diagonal)
    den = np.where(J > K,
                   J - 0.5 + np.sqrt(np.maximum((J - 0.5) ** 2 - K ** 2, 0.0)),
                   K)
    with np.errstate(divide="ignore", invalid="ignore"):
        W = np.where(
            (J >= K) & (den > 0.0),
            np.log(np.maximum(num / np.where(den > 0.0, den, 1.0), 1e-300)),
            0.0,
        )

    fr = -(1.0 / (np.pi * dr)) * (W @ dF)
    return fr


def abel_center(image, search_range=None):
    """
    Find the vertical axis of symmetry in a 2D image.

    Minimizes the L2 asymmetry between left and right halves of the
    column-summed projection, searching over a range of candidate centers.

    Parameters
    ----------
    image : array-like, shape (n_rows, n_cols)
    search_range : int or None
        Half-width of the column search around n_cols//2.
        Default: max(1, n_cols // 8).

    Returns
    -------
    (center_row, center_col) : (int, int)
        Row center (n_rows // 2) and best-fit column center.

    Example
    -------
    cr, cc = anvil.decomp.abel_center(image)
    result = anvil.decomp.abel_image(image, center=(cr, cc))
    """
    image = np.asarray(image, dtype=np.float64)
    n_rows, n_cols = image.shape
    proj = image.sum(axis=0)

    cx0 = n_cols // 2
    half_w = search_range if search_range is not None else max(1, n_cols // 8)

    best_score, best_cx = np.inf, cx0

    for cx in range(max(1, cx0 - half_w), min(n_cols - 1, cx0 + half_w + 1)):
        half = min(cx, n_cols - cx - 1)
        if half < 2:
            continue
        left = proj[cx - half:cx][::-1]
        right = proj[cx:cx + half]
        score = float(np.sum((left - right) ** 2))
        if score < best_score:
            best_score, best_cx = score, cx

    return n_rows // 2, best_cx


def abel_image(image, method="three_point", center=None, dr=1.0, half="average"):
    """
    Apply Abel inversion to a 2D image, row by row.

    Assumes vertical axis of symmetry (constant along rows). Each row is
    treated as an independent 1D projection and inverted independently.

    Parameters
    ----------
    image : array-like, shape (n_rows, n_cols)
        Measured projection (camera frame). Intensity must be non-negative.
    method : str
        "three_point" (default) -- Dasch log-kernel; smooth, recommended
        "onion"                 -- onion peeling; simpler, noisier at center
    center : (row, col) or None
        (row, col) of symmetry axis. row is unused (axis is vertical).
        None = auto-detect with abel_center().
    dr : float
        Physical pixel size. Default 1.0 (pixel units).
    half : str
        "right"   -- use right half only
        "left"    -- use left half only
        "average" -- average left and right (default; best SNR)

    Returns
    -------
    dict with keys:
        "radial"   ndarray (n_rows, n_cols) -- Abel-inverted image
        "center"   (int, int)               -- (row, col) used
        "method"   str
        "n_radial" int                      -- half-width in pixels

    Example
    -------
    result = anvil.decomp.abel_image(frame, method="three_point", half="average")
    print(result["center"])   # (row, col) of symmetry axis found
    anvil.viz.abel_compare(frame, result)
    """
    image = np.asarray(image, dtype=np.float64)
    n_rows, n_cols = image.shape

    if center is None:
        cr, cc = abel_center(image)
    else:
        cr, cc = int(center[0]), int(round(center[1]))

    n = min(cc + 1, n_cols - cc)   # symmetric half-width

    _inv = {
        "three_point": abel_three_point,
        "onion": abel_onion,
        "onion_peeling": abel_onion,
    }
    if method not in _inv:
        raise ValueError(f"Unknown method '{method}'. Choose: {sorted(_inv)}")
    inv_fn = _inv[method]

    radial = np.zeros_like(image)

    for i in range(n_rows):
        row = image[i]
        right = row[cc:cc + n]
        # Left half reversed so index 0 = center, increasing outward
        stop = cc - n if cc >= n else None
        left = row[cc:stop:-1]
        left = left[:n]

        if half == "right":
            Fy = right[:n]
        elif half == "left":
            Fy = left[:n]
        else:
            m = min(len(right), len(left))
            Fy = 0.5 * (right[:m] + left[:m])

        fr = inv_fn(Fy, dr=dr)
        m = len(fr)

        # Write radial distribution symmetrically
        radial[i, cc:cc + m] = fr
        if cc > 0:
            # mirror: pixel cc-1 gets fr[1], cc-2 gets fr[2], ...
            mirror_len = min(m - 1, cc)
            if mirror_len > 0:
                radial[i, cc - mirror_len:cc] = fr[mirror_len:0:-1]

    return {
        "radial": radial,
        "center": (cr, cc),
        "method": method,
        "n_radial": n,
    }


def abel_forward_image(fr_image, center=None, dr=1.0):
    """
    Apply forward Abel transform to a 2D radial image, row by row.

    Converts a known radial distribution back to what a camera would see.
    Useful for validating an inversion: abel_forward_image(abel_image(frame)) ~= frame.

    Parameters
    ----------
    fr_image : array-like, shape (n_rows, n_cols)
        Radial distribution (axis of symmetry = center column).
    center : (row, col) or None
        Center column. None = n_cols // 2.
    dr : float

    Returns
    -------
    Fy_image : ndarray (n_rows, n_cols) -- forward-projected (simulated camera) image.
    """
    fr_image = np.asarray(fr_image, dtype=np.float64)
    n_rows, n_cols = fr_image.shape
    cc = n_cols // 2 if center is None else int(round(center[1]))
    n = min(cc + 1, n_cols - cc)

    Fy_image = np.zeros_like(fr_image)
    for i in range(n_rows):
        fr = fr_image[i, cc:cc + n]
        Fy = abel_forward(fr, dr=dr)
        m = len(Fy)
        Fy_image[i, cc:cc + m] = Fy
        if cc > 0:
            mirror_len = min(m - 1, cc)
            if mirror_len > 0:
                Fy_image[i, cc - mirror_len:cc] = Fy[mirror_len:0:-1]
    return Fy_image
