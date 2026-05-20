# Signal Processing RSQs

Seven built-in RSQs for time-domain and frequency-domain signal analysis. All live in domain `misc`, accept NumPy arrays, and return arrays + scalar summaries.

---

## Quick reference

| RSQ | Purpose | Key outputs |
|-----|---------|-------------|
| `fft_spectrum` | One-sided power spectrum | `freqs`, `power`, `dominant_freq`, `rms`, `thd` |
| `welch_psd` | Averaged PSD (Welch) | `freqs`, `psd`, `total_power`, `dominant_freq` |
| `stft_spectrogram` | Time-frequency map | `t`, `freqs`, `S` (n_freq × n_time), `f_peak` |
| `bandpass_filter` | Zero-phase Butterworth | `signal_filtered`, `rms_in`, `rms_out`, `attenuation_dB` |
| `envelope_detection` | Hilbert envelope + inst. freq | `envelope`, `inst_freq`, `inst_phase`, `peak_envelope` |
| `cross_correlation` | Normalized xcorr + lag | `lags`, `xcorr`, `lag_peak`, `corr_peak` |
| `signal_statistics` | Descriptive statistics | `rms`, `peak`, `crest_factor`, `kurtosis`, `skewness` |

All available via `anvil.R.<name>(...)` after `import anvil`.

---

## fft_spectrum

```python
r = anvil.R.fft_spectrum(signal, dt=1.0, window="hann")
```

**Inputs**

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | array | 1-D time-domain signal |
| `dt` | float | Sampling interval in seconds (default 1.0) |
| `window` | str | `"hann"` (default), `"hamming"`, `"blackman"`, `"none"` |

**Outputs**: `freqs [Hz]`, `power`, `amplitude`, `dominant_freq [Hz]`, `dominant_power`, `rms`, `thd`, `n_samples`, `f_resolution [Hz]`

**Notes**
- THD (Total Harmonic Distortion) = √(Σ harmonic power, 2nd–5th) / fundamental amplitude
- Use `"none"` window only for exactly periodic signals (integer number of cycles in window)
- `f_resolution` = 1/(n·dt): more samples → finer resolution

```python
import numpy as np, anvil
t  = np.linspace(0, 1, 1024, endpoint=False)
sig = np.sin(2*np.pi*50*t) + 0.3*np.sin(2*np.pi*150*t)
r  = anvil.R.fft_spectrum(signal=sig, dt=t[1]-t[0])
# dominant_freq = 50.0 Hz   thd ≈ 0.300   rms ≈ 0.740
```

---

## welch_psd

```python
r = anvil.R.welch_psd(signal, dt=1.0, nperseg=256, noverlap=None, window="hann")
```

**Inputs**

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal` | array | 1-D signal |
| `dt` | float | Sampling interval (s) |
| `nperseg` | int | Segment length; controls frequency resolution (default 256) |
| `noverlap` | int or None | Overlap samples (default: nperseg//2) |
| `window` | str | Same options as `fft_spectrum` |

**Outputs**: `freqs`, `psd` (power/Hz), `total_power`, `dominant_freq`, `dominant_psd`, `f_resolution`

**When to use over `fft_spectrum`**: noisy or stochastic signals where variance reduction matters more than exact amplitude. `psd` is in power per Hz — integrate to get total power. Good for NVH, acoustic measurements, sensor noise floors.

---

## stft_spectrogram

```python
r = anvil.R.stft_spectrogram(signal, dt=1.0, nperseg=256, noverlap=None, window="hann")
```

**Outputs**: `t [s]`, `freqs [Hz]`, `S` (power array, shape `n_freq × n_time`), `t_peak`, `f_peak`, `n_frames`

**Plotting**:
```python
import matplotlib.pyplot as plt
plt.pcolormesh(r["t"], r["freqs"], 10*np.log10(r["S"] + 1e-12))
plt.xlabel("time (s)"); plt.ylabel("frequency (Hz)"); plt.colorbar(label="dB")
```

**Time–frequency resolution tradeoff**: large `nperseg` → fine frequency resolution, coarse time resolution. Small `nperseg` → good time resolution, coarse frequency resolution.

---

## bandpass_filter

```python
r = anvil.R.bandpass_filter(signal, dt=1.0, f_low=None, f_high=None, order=4)
```

**Inputs**: `f_low`, `f_high` in Hz. Omit one for lowpass/highpass.

**Outputs**: `signal_filtered` (array), `rms_in`, `rms_out`, `attenuation_dB`

**Implementation**: `scipy.signal.sosfiltfilt` (zero-phase forward+backward) — no phase distortion. Effective filter order = 2×`order`.

```python
# Lowpass at 100 Hz
r = anvil.R.bandpass_filter(signal=noisy, dt=dt, f_high=100.0, order=5)

# Bandpass 30–80 Hz
r = anvil.R.bandpass_filter(signal=noisy, dt=dt, f_low=30, f_high=80, order=4)

# Highpass at 10 Hz (remove DC drift)
r = anvil.R.bandpass_filter(signal=drift, dt=dt, f_low=10.0)
```

---

## envelope_detection

```python
r = anvil.R.envelope_detection(signal, dt=1.0)
```

**Outputs**: `envelope` (array, same length), `inst_freq [Hz]` (array), `inst_phase [rad]` (array), `peak_envelope`, `mean_envelope`, `n_samples`

**Applications**: bearing fault detection (envelope spectrum of high-frequency band), flutter amplitude tracking, AM signal demodulation, AE hit detection.

**Tip**: apply `bandpass_filter` first to isolate the carrier band, then `envelope_detection` to extract the modulation, then `fft_spectrum` on the envelope to find fault frequencies.

---

## cross_correlation

```python
r = anvil.R.cross_correlation(signal_a, signal_b, dt=1.0, mode="full")
```

**Outputs**: `lags [s]`, `xcorr` (normalized, array), `lag_peak [s]`, `corr_peak`, `n_samples`

**Applications**:
- **Time delay**: `lag_peak` = propagation delay between two sensor signals
- **Flow velocity** from cross-correlation of upstream/downstream probes: v = d / lag_peak
- **Signal alignment**: shift signal_b by lag_peak to align with signal_a
- **Coherence check**: corr_peak close to 1.0 means signals are linearly related

Normalization: both signals zero-meaned and unit-variance before correlation → `corr_peak` ∈ [−1, 1].

---

## signal_statistics

```python
r = anvil.R.signal_statistics(signal, dt=1.0)
```

**Outputs**

| Key | Description |
|-----|-------------|
| `mean` | DC offset |
| `std` | Standard deviation (AC RMS) |
| `rms` | True RMS (includes DC) |
| `peak` | Max absolute value |
| `peak_to_peak` | Max − min |
| `crest_factor` | peak / rms |
| `kurtosis` | 4th statistical moment (3.0 for Gaussian) |
| `skewness` | 3rd statistical moment (0.0 for symmetric) |
| `n_samples` | Sample count |
| `duration` | n_samples × dt (seconds) |
| `sample_rate` | 1/dt (Hz) |

**Fault indicators** (vibration health monitoring):
- Kurtosis > 4: impulsive content, possible bearing spalling or structural crack
- High crest factor (> 4–5): isolated impacts superimposed on background vibration
- Sine wave: kurtosis ≈ 1.5, crest factor ≈ 1.414

---

## Chaining RSQs — vibration fault diagnosis example

```python
import numpy as np, anvil

# Simulated bearing outer-race fault: carrier at 2 kHz, fault at 120 Hz
fs = 10e3; dt = 1/fs; n = 8192
t = np.arange(n) * dt
fault_sig = (1 + 0.6*np.sin(2*np.pi*120*t)) * np.sin(2*np.pi*2000*t)
noise = 0.2 * np.random.default_rng(0).standard_normal(n)
raw = fault_sig + noise

# Step 1: statistics to characterize raw signal
s = anvil.R.signal_statistics(signal=raw, dt=dt)
print(f"kurtosis={s['kurtosis']:.2f}  crest={s['crest_factor']:.2f}")
# kurtosis≈2.1 (masked by noise)

# Step 2: bandpass around 2 kHz carrier band (1500–2500 Hz)
f = anvil.R.bandpass_filter(signal=raw, dt=dt, f_low=1500, f_high=2500, order=5)

# Step 3: envelope (Hilbert)
e = anvil.R.envelope_detection(signal=f["signal_filtered"], dt=dt)

# Step 4: FFT of envelope → fault frequency appears at 120 Hz
r = anvil.R.fft_spectrum(signal=e["envelope"], dt=dt, window="hann")
print(f"envelope dominant_freq = {r['dominant_freq']:.1f} Hz")
# envelope dominant_freq = 120.0 Hz  ← bearing fault frequency detected
```

---

## Usage in Systems and sweeps

```python
# Sweep: how does SNR affect dominant frequency detection?
sys_ = anvil.system("snr_study")
sys_.add("signal", signal)
sys_.add("dt", dt)
sys_.add("window", "hann")
sys_.use("fft_spectrum")

# Can't sweep over array-valued inputs in sys.sweep() — sweep scalars only.
# For array signals, build a loop and call the RSQ directly:
for noise_level in [0.01, 0.1, 0.5, 1.0]:
    noisy = signal + noise_level * np.random.default_rng(0).standard_normal(len(signal))
    r = anvil.R.fft_spectrum(signal=noisy, dt=dt)
    print(f"noise={noise_level:.2f}  f_dom={r['dominant_freq']:.1f} Hz")
```

**Note**: `sys.sweep()` sweeps over scalar parameters. Array inputs (`signal`) must be fixed at System level; sweep over scalar parameters like `dt`, `nperseg`, `f_low`, etc.

---

## Dependencies

| RSQ | scipy required | notes |
|-----|---------------|-------|
| `fft_spectrum` | No | numpy.fft only |
| `welch_psd` | Yes (`scipy.signal.welch`) | always available (Anvil core dep) |
| `stft_spectrogram` | No | numpy.fft only |
| `bandpass_filter` | Yes (`scipy.signal.butter`, `sosfiltfilt`) | always available |
| `envelope_detection` | Yes (`scipy.signal.hilbert`) | always available |
| `cross_correlation` | No | numpy.correlate |
| `signal_statistics` | No | numpy only |

scipy is a core Anvil dependency — all signal RSQs are always available.
