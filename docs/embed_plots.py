"""
Generate missing example plots and embed all viz plots into ANVIL_GUIDE.html
as inline base64 PNG images, replacing the text out-block descriptions.
"""

import sys, os, base64, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

EXAMPLES = os.path.join(os.path.dirname(__file__), '..', 'examples')
GUIDE    = os.path.join(os.path.dirname(__file__), 'ANVIL_GUIDE.html')


# ── Generate missing plots ──────────────────────────────────────────────────

def gen_pod_energy():
    path = os.path.join(EXAMPLES, 'pod_energy.png')
    if os.path.exists(path):
        print(f'  exists: {path}')
        return path

    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from anvil import viz, decomp

    rng = np.random.default_rng(42)
    # Low-rank signal + small noise — clear elbow in singular values
    r_true = 5
    n, m = 50, 80
    U = rng.standard_normal((n, r_true))
    V = rng.standard_normal((r_true, m))
    S = np.diag([200, 80, 30, 10, 3])
    X = U @ S @ V + 0.5 * rng.standard_normal((n, m))

    pod = decomp.pod(X, r=20)
    fig = viz.pod_energy(pod, show=False)
    fig.savefig(path, dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'  generated: {path}')
    return path


def gen_dmd_spectrum():
    path = os.path.join(EXAMPLES, 'dmd_spectrum.png')
    if os.path.exists(path):
        print(f'  exists: {path}')
        return path

    from anvil import viz, decomp

    rng = np.random.default_rng(7)
    dt = 0.01
    t = np.arange(0, 2, dt)
    # Two dominant frequencies + decay
    x1 = np.exp(-0.5 * t) * np.cos(2 * np.pi * 5 * t)
    x2 = np.exp(-0.1 * t) * np.cos(2 * np.pi * 12 * t)
    x3 = 0.3 * np.cos(2 * np.pi * 20 * t)
    states = np.vstack([x1, x2, x3, x1 + x2, x2 + x3])
    X_dmd = states + 0.02 * rng.standard_normal(states.shape)

    dmd_r = decomp.dmd(X_dmd, dt=dt, r=10)
    fig = viz.dmd_spectrum(dmd_r, show=False)
    fig.savefig(path, dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'  generated: {path}')
    return path


def gen_abel_compare():
    path = os.path.join(EXAMPLES, 'abel_compare.png')
    if os.path.exists(path):
        print(f'  exists: {path}')
        return path

    from anvil import viz, decomp

    # Synthetic axisymmetric flame-like image
    ny, nx = 120, 200
    xc = nx // 2
    y = np.arange(ny)
    x = np.arange(nx)
    XX, YY = np.meshgrid(x, y)
    r = np.abs(XX - xc)
    # Annular emission profile: bright ring, dark centre
    sigma_outer, sigma_ring = 8, 3
    profile = (np.exp(-0.5 * (r - 20)**2 / sigma_ring**2) *
               np.exp(-0.002 * (YY - ny//2)**2))
    profile += 0.1 * np.exp(-0.5 * r**2 / sigma_outer**2)
    rng = np.random.default_rng(99)
    image = profile + 0.01 * rng.standard_normal((ny, nx))
    image = np.clip(image, 0, None)

    abel_r = decomp.abel_image(image, method='three_point')
    fig = viz.abel_compare(image, abel_r, show=False)
    fig.savefig(path, dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'  generated: {path}')
    return path


# ── Base64 helper ───────────────────────────────────────────────────────────

def b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def img_tag(path, alt='', style='max-width:100%;border-radius:4px;margin:6px 0;display:block;'):
    data = b64(path)
    return f'<img src="data:image/png;base64,{data}" alt="{alt}" style="{style}">'


def two_img_tags(p1, alt1, p2, alt2):
    return img_tag(p1, alt1) + '\n' + img_tag(p2, alt2)


# ── Patch guide ─────────────────────────────────────────────────────────────

def patch_out_block(html, label_fragment, new_inner_html):
    """
    Find <div class="out-wrap"> whose out-label contains label_fragment.
    Replace its <div class="out-block">...</div> with new_inner_html.
    Returns patched html and True/False for match found.
    """
    # Pattern: out-wrap block containing the label
    pattern = (
        r'(<div class="out-wrap">\s*'
        r'<div class="out-label">[^<]*' + re.escape(label_fragment) + r'[^<]*</div>\s*)'
        r'<div class="out-block">.*?</div>'
    )
    replacement = r'\1' + new_inner_html
    new_html, n = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if n == 0:
        print(f'  WARNING: no match for label fragment "{label_fragment}"')
    else:
        print(f'  patched: "{label_fragment}"')
    return new_html


def main():
    print('Generating missing plots...')
    conv_png   = os.path.join(EXAMPLES, 'convergence.png')
    vtrace_png = os.path.join(EXAMPLES, 'variable_trace.png')
    sweep_png  = os.path.join(EXAMPLES, 'sweep_plot.png')
    depgraph_png = os.path.join(EXAMPLES, 'dependency_graph.png')
    pod_png    = gen_pod_energy()
    dmd_png    = gen_dmd_spectrum()
    abel_png   = gen_abel_compare()
    # Use ramp (supersonic, shows clear shock) for CFD contour
    cfd_fields_png = os.path.join(EXAMPLES, 'ramp_fields.png')
    if not os.path.exists(cfd_fields_png):
        cfd_fields_png = os.path.join(EXAMPLES, 'bump_fields.png')

    print('\nReading guide...')
    with open(GUIDE, encoding='utf-8') as f:
        html = f.read()

    print('Patching output blocks...')

    # 1. Convergence + variable trace (combined section)
    html = patch_out_block(
        html,
        'matplotlib window (semi-log convergence curve)',
        img_tag(conv_png, 'Convergence plot') + '\n' + img_tag(vtrace_png, 'Variable trace plot'),
    )

    # 2. Sweep plot
    html = patch_out_block(
        html,
        'matplotlib Figure (2×2 grid)',
        img_tag(sweep_png, 'Sweep plot'),
    )

    # 3. Dependency graph
    html = patch_out_block(
        html,
        'matplotlib Figure',
        img_tag(depgraph_png, 'Dependency graph'),
    )

    # 4. POD energy + DMD spectrum
    html = patch_out_block(
        html,
        'two matplotlib windows',
        img_tag(pod_png, 'POD energy spectrum') + '\n' + img_tag(dmd_png, 'DMD eigenvalue spectrum'),
    )

    # 5. Abel compare
    html = patch_out_block(
        html,
        'side-by-side matplotlib Figure (1×2)',
        img_tag(abel_png, 'Abel compare: projection vs radial'),
    )

    # 6. CFD viz contour
    html = patch_out_block(
        html,
        'cfd_viz.contour(result',
        img_tag(cfd_fields_png, 'CFD contour: Mach number field'),
    )

    print('Writing patched guide...')
    with open(GUIDE, 'w', encoding='utf-8') as f:
        f.write(html)

    sz = os.path.getsize(GUIDE)
    print(f'Done. Guide size: {sz//1024} KB')


if __name__ == '__main__':
    main()
