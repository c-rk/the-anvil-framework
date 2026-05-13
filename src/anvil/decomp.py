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
    int — number of modes required.
    """
    ce = pod_result["cumulative_energy"]
    idx = np.searchsorted(ce, target_energy)
    return min(int(idx) + 1, pod_result["rank"])
