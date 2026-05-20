"""
Example: Signal Processing RSQs
=================================
Demonstrates all 7 signal processing RSQs in the misc domain:
  fft_spectrum, welch_psd, stft_spectrogram, bandpass_filter,
  envelope_detection, cross_correlation, signal_statistics

No external dependencies — numpy + scipy only (both Anvil core deps).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import anvil

rng = np.random.default_rng(42)

# ── Shared signals ────────────────────────────────────────────────────────────
fs   = 2048.0                              # sample rate [Hz]
dt   = 1.0 / fs
n    = 4096
t    = np.arange(n) * dt                   # 2 seconds

# Clean signal: 50 Hz fundamental + 3rd harmonic
sig_clean = np.sin(2*np.pi*50*t) + 0.3*np.sin(2*np.pi*150*t)

# Noisy version
noise     = 0.4 * rng.standard_normal(n)
sig_noisy = sig_clean + noise

# Chirp: frequency sweeps 20 -> 400 Hz over 2 s
chirp = np.sin(2*np.pi * (20 + 190*t) * t)

# AM signal: 500 Hz carrier, 8 Hz modulation
am = (1 + 0.7*np.sin(2*np.pi*8*t)) * np.sin(2*np.pi*500*t)

# Bearing fault: 2 kHz carrier, 120 Hz outer-race fault, noise
# Needs fs > 2*2500 = 5 kHz; use separate higher sample rate
fs_fault  = 8192.0
dt_fault  = 1.0 / fs_fault
n_fault   = 16384
t_fault   = np.arange(n_fault) * dt_fault
fault     = (1 + 0.6*np.sin(2*np.pi*120*t_fault)) * np.sin(2*np.pi*2000*t_fault) \
            + 0.3*rng.standard_normal(n_fault)


# ══════════════════════════════════════════════════════════════════════════════
# 1. fft_spectrum
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("1. fft_spectrum — power spectrum")
print("=" * 60)

r = anvil.R.fft_spectrum(signal=sig_clean, dt=dt, window="hann")
print(f"  Signal: 50 Hz + 0.3x150 Hz")
print(f"  dominant_freq  = {r['dominant_freq']:.1f} Hz")
print(f"  RMS            = {r['rms']:.4f}")
print(f"  THD            = {r['thd']:.4f}  (~= 0.30 = amplitude of 3rd harmonic)")
print(f"  f_resolution   = {r['f_resolution']:.3f} Hz  (= 1 / 2 s = 0.5 Hz)")
print(f"  spectrum shape : {r['power'].shape}  ({r['n_samples']} samples -> {len(r['freqs'])} bins)")

# Window comparison
print(f"\n  Window comparison (same signal):")
for win in ["none", "hann", "hamming", "blackman"]:
    rw = anvil.R.fft_spectrum(signal=sig_clean, dt=dt, window=win)
    print(f"    {win:10s}: dominant={rw['dominant_freq']:.1f} Hz  THD={rw['thd']:.4f}")
print("  (rectangular 'none' accurate for exact-integer-cycle signals)")


# ══════════════════════════════════════════════════════════════════════════════
# 2. welch_psd
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. welch_psd — averaged power spectral density")
print("=" * 60)

r_fft   = anvil.R.fft_spectrum(signal=sig_noisy, dt=dt)
r_welch = anvil.R.welch_psd(signal=sig_noisy, dt=dt, nperseg=512)

print(f"  Noisy signal (SNR ~= {20*np.log10(0.7/0.4):.1f} dB)")
print(f"  FFT  dominant_freq = {r_fft['dominant_freq']:.1f} Hz")
print(f"  Welch dominant_freq = {r_welch['dominant_freq']:.1f} Hz")
print(f"  Welch total_power   = {r_welch['total_power']:.4f}")
print(f"  Welch f_resolution  = {r_welch['f_resolution']:.3f} Hz  (nperseg=512)")
print(f"  PSD shape: {r_welch['psd'].shape}")

# nperseg tradeoff
print(f"\n  nperseg tradeoff (noise floor vs resolution):")
for nperseg in [128, 256, 512, 1024]:
    rw = anvil.R.welch_psd(signal=sig_noisy, dt=dt, nperseg=nperseg)
    print(f"    nperseg={nperseg:4d}: f_res={rw['f_resolution']:.2f} Hz  "
          f"dominant={rw['dominant_freq']:.1f} Hz")


# ══════════════════════════════════════════════════════════════════════════════
# 3. stft_spectrogram
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. stft_spectrogram — time-frequency power map")
print("=" * 60)

r = anvil.R.stft_spectrogram(signal=chirp, dt=dt, nperseg=256, window="hann")
print(f"  Chirp: 20 -> 400 Hz sweep over 2 s")
print(f"  S shape (n_freq x n_time): {r['S'].shape}")
print(f"  n_frames : {r['n_frames']}")
print(f"  t_peak   = {r['t_peak']:.3f} s   (energy peak near end, highest freq)")
print(f"  f_peak   = {r['f_peak']:.1f} Hz")

# Time-frequency slices: check instantaneous frequency tracks the chirp
t_centers = r['t']
f_inst_expected = 20 + 190 * t_centers   # f(t) = 20 + 2x95xt (chirp formula: d/dt[(20+190t)t])
f_inst_expected = np.clip(f_inst_expected, 0, fs/2)

# Find peak frequency per time frame
f_per_frame = r['freqs'][np.argmax(r['S'], axis=0)]
print(f"\n  Instantaneous frequency tracking (sample frames):")
step = max(1, len(t_centers)//8)
print(f"  {'t [s]':>7}  {'f_inst [Hz]':>12}  {'f_expected [Hz]':>16}")
for i in range(0, len(t_centers), step):
    print(f"  {t_centers[i]:7.3f}  {f_per_frame[i]:12.1f}  {f_inst_expected[i]:16.1f}")
print("  (STFT tracks swept frequency through time)")


# ══════════════════════════════════════════════════════════════════════════════
# 4. bandpass_filter
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. bandpass_filter — zero-phase Butterworth")
print("=" * 60)

# Lowpass: keep 50 Hz, suppress 150 Hz harmonic and noise
r_lp = anvil.R.bandpass_filter(signal=sig_noisy, dt=dt, f_high=80.0, order=5)
print(f"  Lowpass  (f_high=80 Hz, order=5):")
print(f"    RMS in  = {r_lp['rms_in']:.4f}")
print(f"    RMS out = {r_lp['rms_out']:.4f}  (noise + 150 Hz removed)")
print(f"    att.    = {r_lp['attenuation_dB']:.1f} dB")

# Bandpass: isolate 50 Hz ± 20 Hz band
r_bp = anvil.R.bandpass_filter(signal=sig_noisy, dt=dt, f_low=30.0, f_high=70.0, order=4)
print(f"\n  Bandpass (30–70 Hz, order=4):")
print(f"    RMS in  = {r_bp['rms_in']:.4f}")
print(f"    RMS out = {r_bp['rms_out']:.4f}  (only 50 Hz component passes)")
print(f"    att.    = {r_bp['attenuation_dB']:.1f} dB")

# Highpass: remove DC drift
drift = sig_clean + 2.5 + 0.3*t   # add DC + slow drift
r_hp = anvil.R.bandpass_filter(signal=drift, dt=dt, f_low=5.0, order=3)
print(f"\n  Highpass (f_low=5 Hz, order=3): removes DC/drift")
print(f"    mean before filter = {drift.mean():.3f}")
print(f"    mean after filter  = {r_hp['signal_filtered'].mean():.6f}  (~= 0)")

# Order comparison
print(f"\n  Filter order vs stopband attenuation (bandpass 30–70 Hz):")
for order in [2, 4, 6, 8]:
    rr = anvil.R.bandpass_filter(signal=sig_noisy, dt=dt, f_low=30, f_high=70, order=order)
    print(f"    order={order}: RMS_out={rr['rms_out']:.4f}  att={rr['attenuation_dB']:.1f} dB")


# ══════════════════════════════════════════════════════════════════════════════
# 5. envelope_detection
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. envelope_detection — Hilbert transform")
print("=" * 60)

r = anvil.R.envelope_detection(signal=am, dt=dt)
print(f"  AM signal: 500 Hz carrier, 8 Hz modulation depth=0.7")
print(f"  peak_envelope = {r['peak_envelope']:.4f}  (expected ~= 1.70)")
print(f"  mean_envelope = {r['mean_envelope']:.4f}  (expected ~= 1.00)")
print(f"  carrier freq  ~= {float(np.median(r['inst_freq'])):.1f} Hz  (median of inst_freq)")

# Envelope spectrum: FFT of envelope reveals modulation frequency
env_spec = anvil.R.fft_spectrum(signal=r['envelope'], dt=dt, window="hann")
# Find second peak (skip DC region)
mask = env_spec['freqs'] > 2
f_mod = env_spec['freqs'][mask][np.argmax(env_spec['power'][mask])]
print(f"  modulation freq from envelope spectrum = {f_mod:.1f} Hz  (expected 8 Hz)")

# Fault signal: bearing fault detection (uses higher sample rate signal)
print(f"\n  Bearing fault detection (2 kHz carrier, 120 Hz fault, fs={int(fs_fault)} Hz):")
# Step 1: bandpass around 2 kHz carrier
r_bp = anvil.R.bandpass_filter(signal=fault, dt=dt_fault, f_low=1500, f_high=2500, order=5)
# Step 2: envelope
r_env = anvil.R.envelope_detection(signal=r_bp['signal_filtered'], dt=dt_fault)
# Step 3: FFT of envelope -> fault frequency appears at 120 Hz
r_env_spec = anvil.R.fft_spectrum(signal=r_env['envelope'], dt=dt_fault, window="hann")
mask2 = r_env_spec['freqs'] > 10
f_fault_det = r_env_spec['freqs'][mask2][np.argmax(r_env_spec['power'][mask2])]
print(f"  Detected fault frequency = {f_fault_det:.1f} Hz  (expected 120 Hz)")


# ══════════════════════════════════════════════════════════════════════════════
# 6. cross_correlation
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("6. cross_correlation — time delay estimation")
print("=" * 60)

# Use broadband (noise) signal — xcorr on periodic sine has many equal peaks
# making argmax unreliable without restricting the lag search window.
delay_samples = 35
# Use broadband signal — xcorr on a pure periodic sine has many equal-height
# peaks separated by the signal period, making argmax unreliable.
# broadband noise has a unique peak at the true delay.
broadband = rng.standard_normal(n)
sig_ref    = broadband                          # reference (earlier sensor)
sig_del    = np.roll(broadband, delay_samples)  # delayed copy (later sensor)

# Correlate (delayed, reference) -> peak at +delay_samples
r = anvil.R.cross_correlation(signal_a=sig_del, signal_b=sig_ref, dt=dt)
print(f"  Broadband signal, delay = {delay_samples} samples = {delay_samples*dt*1000:.3f} ms")
print(f"  Detected lag    = {r['lag_peak']*1000:.3f} ms  ({round(r['lag_peak']/dt):.0f} samples)")
print(f"  corr_peak       = {r['corr_peak']:.6f}  (1.0 = perfect match)")

# Noisy: does xcorr still recover the delay?
print(f"\n  Noise robustness (broadband, 35-sample delay):")
for snr_db in [20, 10, 3, 0]:
    noise_amp = 10**(-snr_db/20)
    sig_del_noisy = sig_del + noise_amp * rng.standard_normal(n)
    rr = anvil.R.cross_correlation(signal_a=sig_del_noisy, signal_b=sig_ref, dt=dt)
    detected = round(rr['lag_peak']/dt)
    print(f"    SNR={snr_db:3d} dB: lag={detected:4.0f} samples  corr_peak={rr['corr_peak']:.4f}")

# Flow velocity measurement from two sensors
print(f"\n  Flow velocity (two probes, d=0.5 m apart):")
d_probe      = 0.5   # m
broadband2   = rng.standard_normal(n)
v_true       = 12.5  # m/s -> delay = d/v
delay_samp   = int(d_probe / v_true / dt)
sig_down     = np.roll(broadband2, delay_samp)
r_flow       = anvil.R.cross_correlation(signal_a=broadband2, signal_b=sig_down, dt=dt)
v_measured   = d_probe / abs(r_flow['lag_peak'])
print(f"    True velocity     = {v_true:.2f} m/s  (delay = {delay_samp} samples)")
print(f"    Measured velocity = {v_measured:.2f} m/s  (lag={r_flow['lag_peak']*1000:.2f} ms)")


# ══════════════════════════════════════════════════════════════════════════════
# 7. signal_statistics
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("7. signal_statistics — descriptive statistics")
print("=" * 60)

signals = {
    "sine 50 Hz":      (sig_clean,  dt),
    "sine + noise":    (sig_noisy,  dt),
    "Gaussian noise":  (rng.standard_normal(n), dt),
    "bearing fault":   (fault[:n],  dt_fault),   # use same-length slice
    "impulse train":   (np.where((np.arange(n) % 256) == 0, 5.0, 0.0) + 0.1*rng.standard_normal(n), dt),
}

print(f"  {'Signal':>16}  {'RMS':>6}  {'Crest':>6}  {'Kurtosis':>10}  {'Skew':>6}")
for name, (s, s_dt) in signals.items():
    r = anvil.R.signal_statistics(signal=s, dt=s_dt)
    print(f"  {name:>16}  {r['rms']:6.3f}  {r['crest_factor']:6.3f}  {r['kurtosis']:10.4f}  {r['skewness']:6.3f}")

print(f"\n  Notes:")
print(f"    Gaussian noise: kurtosis ~= 3.0 (mesokurtic)")
print(f"    Bearing fault:  kurtosis > 3 — impulsive content from carrier modulation")
print(f"    Impulse train:  very high crest factor and kurtosis — sparse, large peaks")
print(f"    Sine: kurtosis ~= 1.5, crest factor = sqrt2 ~= 1.414")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Sweep example: SNR effect on dominant frequency detection
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("8. Direct loop — nperseg vs Welch frequency resolution")
print("=" * 60)

# Note: sys.sweep() sweeps scalar parameters. Array inputs (signal) must be
# fixed; sweep over numeric parameters like nperseg directly.
print(f"  {'nperseg':>8}  {'f_res [Hz]':>12}  {'dominant [Hz]':>15}  {'dom_psd':>10}")
for nperseg in [64, 128, 256, 512, 1024, 2048]:
    rw = anvil.R.welch_psd(signal=sig_noisy, dt=dt, nperseg=nperseg)
    print(f"  {nperseg:>8}  {rw['f_resolution']:12.3f}  {rw['dominant_freq']:15.1f}  {rw['dominant_psd']:.4f}")
print("  (larger nperseg -> finer freq resolution; fewer averages -> higher variance)")


# ══════════════════════════════════════════════════════════════════════════════
# 9. Full pipeline: vibration health monitoring
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("9. Full pipeline: vibration health monitoring")
print("=" * 60)

for fault_level in [0.0, 0.3, 0.6, 1.0]:
    # Use higher fs to accommodate 2 kHz carrier + 1500-2500 Hz bandpass
    vibration = (1 + fault_level*np.sin(2*np.pi*120*t_fault)) * np.sin(2*np.pi*2000*t_fault) \
                + 0.2*rng.standard_normal(n_fault)

    # Step 1: raw statistics
    stats = anvil.R.signal_statistics(signal=vibration, dt=dt_fault)

    # Step 2: bandpass around 2 kHz, extract envelope
    bp     = anvil.R.bandpass_filter(signal=vibration, dt=dt_fault, f_low=1500, f_high=2500, order=5)
    env    = anvil.R.envelope_detection(signal=bp['signal_filtered'], dt=dt_fault)
    espec  = anvil.R.fft_spectrum(signal=env['envelope'], dt=dt_fault, window="hann")

    mask3  = espec['freqs'] > 10
    f_detected = espec['freqs'][mask3][np.argmax(espec['power'][mask3])]
    p_fault    = float(espec['power'][mask3][np.argmax(espec['power'][mask3])])

    print(f"  fault_level={fault_level:.1f}:  kurtosis={stats['kurtosis']:.2f}  "
          f"crest={stats['crest_factor']:.2f}  "
          f"f_fault={f_detected:.0f} Hz  fault_power={p_fault:.4f}")

print("  (fault_level 0 -> kurtosis near Gaussian, fault_power ~noise floor)")
print("  (fault_level 1.0 -> elevated kurtosis, fault frequency at 120 Hz clearly detected)")
