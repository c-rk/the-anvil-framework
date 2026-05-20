"""
Build the Anvil wiki into a single self-contained HTML file.

Usage:
    cd docs
    python build_wiki.py          -> writes ANVIL_WIKI.html
    python build_wiki.py --open   -> build and open in browser
"""

import os
import re
import sys
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension
from markdown.extensions.extra import ExtraExtension

try:
    from pygments.formatters import HtmlFormatter
    PYGMENTS_CSS = HtmlFormatter(style="one-dark").get_style_defs(".codehilite")
except Exception:
    PYGMENTS_CSS = ""

# ── Wiki page manifest ────────────────────────────────────────────────────────
WIKI_DIR = os.path.join(os.path.dirname(__file__), "wiki")

PAGES = [
    ("index",    "Overview",               "wiki/index.md"),
    ("01",       "Quick Start",            "wiki/01_quickstart.md"),
    ("02",       "Quantity (Q)",           "wiki/02_quantity.md"),
    ("03",       "Unit Engine",            "wiki/03_units.md"),
    ("04",       "Relation",               "wiki/04_relation.md"),
    ("05",       "System",                 "wiki/05_system.md"),
    ("06",       "Solvers",                "wiki/06_solvers.md"),
    ("07",       "Registry",               "wiki/07_registry.md"),
    ("08",       "Project Registry",       "wiki/08_project.md"),
    ("09",       "Built-in RSQs",          "wiki/09_builtin_rsqs.md"),
    ("10",       "Adapters",               "wiki/10_adapters.md"),
    ("11",       "Sweep & Sensitivity",    "wiki/11_sweep_sensitivity.md"),
    ("12",       "Visualization",          "wiki/12_visualization.md"),
    ("13",       "Databases",              "wiki/13_databases.md"),
    ("14",       "Limits & Gotchas",       "wiki/14_limits.md"),
    ("15",       "Advanced",               "wiki/15_advanced.md"),
    ("16",       "Decomposition",          "wiki/16_decomp.md"),
    ("17",       "Abel Transform",         "wiki/17_abel.md"),
]

# ── Markdown → HTML conversion ────────────────────────────────────────────────
MD_EXTENSIONS = [
    ExtraExtension(),          # tables, fenced code, footnotes, attr_list
    CodeHiliteExtension(
        css_class="codehilite",
        guess_lang=True,
        linenums=False,
    ),
    FencedCodeExtension(),
    TocExtension(permalink=True, toc_depth="2-3"),
]


def md_to_html(text):
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    html = md.convert(text)
    return html


def read_page(rel_path):
    full = os.path.join(os.path.dirname(__file__), rel_path)
    if not os.path.exists(full):
        return f"<p><em>File not found: {rel_path}</em></p>"
    with open(full, encoding="utf-8") as f:
        return md_to_html(f.read())


# ── Sidebar HTML ──────────────────────────────────────────────────────────────
SECTION_GROUPS = [
    ("Getting Started",  ["index", "01"]),
    ("Core Primitives",  ["02", "03", "04", "05"]),
    ("Computation",      ["06", "07", "08"]),
    ("RSQs & Adapters",  ["09", "10"]),
    ("Analysis",         ["11", "12"]),
    ("Reference",        ["13", "14", "15", "16", "17"]),
]


def build_sidebar():
    page_map = {pid: label for pid, label, _ in PAGES}
    lines = []
    for group_title, ids in SECTION_GROUPS:
        lines.append(f'<div class="sb-section">{group_title}</div>')
        for pid in ids:
            label = page_map.get(pid, pid)
            lines.append(
                f'<a href="#{pid}" onclick="showPage(\'{pid}\')">'
                f'{label}</a>'
            )
    return "\n".join(lines)


# ── Build all page content ────────────────────────────────────────────────────
def build_pages():
    parts = []
    for pid, label, path in PAGES:
        html = read_page(path)
        parts.append(
            f'<section id="page-{pid}" class="wiki-page" style="display:none">'
            f'{html}'
            f'</section>'
        )
    return "\n".join(parts)


# ── Full HTML template ────────────────────────────────────────────────────────
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anvil Framework — Wiki</title>
<style>
/* ── Reset & Base ───────────────────────────────────────────────────────────── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
     font-size:15px;line-height:1.75;color:#1a1a2e;background:#f7f8fa}}

/* ── Layout ─────────────────────────────────────────────────────────────────── */
#sidebar{{
  position:fixed;top:0;left:0;width:270px;height:100vh;
  background:#0d1117;color:#c9d1d9;overflow-y:auto;
  padding:0 0 40px;z-index:100;font-size:13.5px;
}}
#sidebar::-webkit-scrollbar{{width:4px}}
#sidebar::-webkit-scrollbar-thumb{{background:#333;border-radius:2px}}
#main{{margin-left:270px;min-height:100vh;padding:0}}
.page-wrap{{max-width:900px;padding:48px 56px 80px}}

/* ── Sidebar ─────────────────────────────────────────────────────────────────── */
.sb-brand{{
  padding:22px 20px 16px;border-bottom:1px solid #21262d;
  font-weight:700;font-size:16px;color:#58a6ff;letter-spacing:-.3px;
  cursor:pointer;
}}
.sb-brand small{{display:block;font-size:11px;color:#8b949e;font-weight:400;margin-top:3px}}
.sb-search{{
  padding:10px 14px;border-bottom:1px solid #21262d;
}}
.sb-search input{{
  width:100%;background:#161b22;border:1px solid #30363d;
  color:#c9d1d9;border-radius:6px;padding:6px 10px;font-size:13px;
  outline:none;
}}
.sb-search input:focus{{border-color:#58a6ff}}
.sb-section{{
  padding:12px 20px 4px;font-size:10px;text-transform:uppercase;
  letter-spacing:.8px;color:#6e7681;font-weight:600;margin-top:4px;
}}
#sidebar a{{
  display:block;padding:5px 20px 5px 26px;color:#8b949e;
  text-decoration:none;transition:color .15s,background .15s;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;
}}
#sidebar a:hover{{color:#e6edf3;background:#161b22}}
#sidebar a.active{{color:#58a6ff;background:#161b22;
  border-left:2px solid #58a6ff;padding-left:24px;font-weight:600}}
.search-highlight{{background:#ffd700;color:#000;border-radius:2px;padding:0 2px}}

/* ── Typography ──────────────────────────────────────────────────────────────── */
.wiki-page h1{{font-size:2em;font-weight:800;color:#0f1117;
  line-height:1.2;margin:0 0 10px}}
.wiki-page h2{{font-size:1.45em;font-weight:700;color:#0f1117;
  margin:40px 0 12px;padding-top:18px;border-top:2px solid #e1e4e8}}
.wiki-page h2:first-child{{border-top:none;margin-top:0;padding-top:0}}
.wiki-page h3{{font-size:1.18em;font-weight:700;color:#24292f;margin:28px 0 10px}}
.wiki-page h4{{font-size:1em;font-weight:600;color:#444d56;margin:18px 0 6px}}
.wiki-page p{{margin:10px 0;color:#24292f}}
.wiki-page ul,.wiki-page ol{{margin:10px 0 10px 22px}}
.wiki-page li{{margin:5px 0}}
.wiki-page strong{{color:#0f1117}}
.wiki-page em{{color:#555}}
.wiki-page blockquote{{
  border-left:4px solid #58a6ff;padding:10px 16px;
  background:#f0f7ff;border-radius:0 6px 6px 0;margin:14px 0;
  color:#0550ae;font-style:normal;
}}
.wiki-page hr{{border:none;border-top:1px solid #d0d7de;margin:28px 0}}
.wiki-page a{{color:#0969da;text-decoration:none}}
.wiki-page a:hover{{text-decoration:underline}}

/* ── Code ────────────────────────────────────────────────────────────────────── */
.wiki-page :not(pre) > code {{
  font-family:'Consolas','Cascadia Code','Fira Mono',monospace;
  font-size:.87em;background:#f0f2f5;color:#c7254e;
  padding:1px 6px;border-radius:4px;
}}
.wiki-page pre{{margin:14px 0;border-radius:8px;overflow-x:auto;border:1px solid #30363d}}
.wiki-page pre code {{
  background:none!important;color:inherit!important;padding:0!important;
  border-radius:0!important;font-size:1em!important;
}}
/* Override codehilite to use our dark theme */
.codehilite{{background:#0d1117!important;padding:18px 22px;border-radius:8px;
  font-family:'Consolas','Cascadia Code','Fira Mono',monospace;font-size:.84em;
  line-height:1.6;border:1px solid #30363d;overflow-x:auto}}
.codehilite .hll{{background:#ff03}}
/* Pygments one-dark overrides */
PYGMENTS_CSS_PLACEHOLDER

/* ── Tables ──────────────────────────────────────────────────────────────────── */
.wiki-page table{{border-collapse:collapse;width:100%;font-size:.88em;margin:14px 0;overflow-x:auto;display:block}}
.wiki-page th{{background:#0d1117;color:#e6edf3;padding:9px 14px;
  text-align:left;font-weight:600;white-space:nowrap}}
.wiki-page td{{padding:8px 14px;border-bottom:1px solid #e1e4e8;vertical-align:top}}
.wiki-page tr:hover td{{background:#f6f8fa}}
.wiki-page td code{{background:#f0f2f5;color:#c7254e}}

/* ── TOC ─────────────────────────────────────────────────────────────────────── */
.wiki-page .toc{{
  background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;
  padding:16px 20px;margin:0 0 28px;font-size:.9em;
}}
.wiki-page .toc ul{{margin:4px 0 4px 16px;list-style:none}}
.wiki-page .toc li{{margin:2px 0}}
.wiki-page .toc a{{color:#0969da}}
.wiki-page .toc::before{{
  content:'Contents';display:block;font-weight:700;
  color:#24292f;margin-bottom:8px;font-size:.95em;
}}

/* ── Header bar ──────────────────────────────────────────────────────────────── */
#topbar{{
  background:#fff;border-bottom:1px solid #e1e4e8;
  padding:14px 56px 14px 40px;display:flex;align-items:center;gap:16px;
  position:sticky;top:0;z-index:90;
}}
#topbar .breadcrumb{{color:#6e7681;font-size:.9em}}
#topbar .breadcrumb span{{color:#0969da;font-weight:600}}
#topbar .nav-btns{{margin-left:auto;display:flex;gap:8px}}
#topbar button{{
  background:#f0f2f5;border:1px solid #d0d7de;border-radius:6px;
  padding:5px 12px;font-size:.85em;cursor:pointer;color:#24292f;
  transition:background .15s;
}}
#topbar button:hover{{background:#e1e4e8}}

/* ── Search results overlay ─────────────────────────────────────────────────── */
#search-results{{
  position:fixed;top:0;left:270px;right:0;bottom:0;background:rgba(0,0,0,.6);
  z-index:200;display:none;align-items:flex-start;justify-content:center;
  padding-top:80px;
}}
#search-results.open{{display:flex}}
#search-box{{
  background:#fff;border-radius:10px;padding:20px;width:min(700px,90%);
  max-height:70vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.3);
}}
#search-box h3{{margin:0 0 14px;font-size:1em;color:#444}}
.sr-item{{padding:10px 14px;border-radius:6px;cursor:pointer;margin-bottom:6px;border:1px solid #e1e4e8}}
.sr-item:hover{{background:#f0f7ff;border-color:#58a6ff}}
.sr-item strong{{color:#0550ae;display:block;font-size:.95em}}
.sr-item span{{color:#555;font-size:.85em;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
</style>
</head>
<body>

<!-- ══ SIDEBAR ════════════════════════════════════════════════════════════ -->
<nav id="sidebar">
  <div class="sb-brand" onclick="showPage('index')">
    Anvil Framework
    <small>Developer Wiki — v1.3</small>
  </div>
  <div class="sb-search">
    <input id="sb-search-input" type="text" placeholder="Search wiki..."
           oninput="liveSearch(this.value)" onkeydown="if(event.key==='Escape')clearSearch()">
  </div>
SIDEBAR_PLACEHOLDER
</nav>

<!-- ══ MAIN ═══════════════════════════════════════════════════════════════ -->
<div id="main">
  <div id="topbar">
    <div class="breadcrumb">Anvil Wiki &rsaquo; <span id="page-title">Overview</span></div>
    <div class="nav-btns">
      <button onclick="navigatePage(-1)">&#8592; Prev</button>
      <button onclick="navigatePage(1)">Next &#8594;</button>
    </div>
  </div>
  <div class="page-wrap">
PAGES_PLACEHOLDER
  </div>
</div>

<!-- ══ SEARCH OVERLAY ════════════════════════════════════════════════════ -->
<div id="search-results" onclick="if(event.target===this)clearSearch()">
  <div id="search-box">
    <h3 id="search-heading">Search results</h3>
    <div id="search-list"></div>
  </div>
</div>

<script>
// ── Page data ─────────────────────────────────────────────────────────────────
const PAGES = PAGES_DATA_PLACEHOLDER;
let currentIdx = 0;

// ── Show a page ───────────────────────────────────────────────────────────────
function showPage(pid) {
  document.querySelectorAll('.wiki-page').forEach(s => s.style.display = 'none');
  const sec = document.getElementById('page-' + pid);
  if (sec) sec.style.display = 'block';

  document.querySelectorAll('#sidebar a').forEach(a => a.classList.remove('active'));
  const link = document.querySelector(`#sidebar a[href="#${pid}"]`);
  if (link) { link.classList.add('active'); link.scrollIntoView({block:'nearest'}); }

  const p = PAGES.find(x => x[0] === pid);
  document.getElementById('page-title').textContent = p ? p[1] : pid;
  currentIdx = PAGES.findIndex(x => x[0] === pid);

  location.hash = pid;
  window.scrollTo(0, 0);
  clearSearch();
}

// ── Prev / Next ───────────────────────────────────────────────────────────────
function navigatePage(dir) {
  const idx = Math.max(0, Math.min(PAGES.length - 1, currentIdx + dir));
  showPage(PAGES[idx][0]);
}

// ── Live search ───────────────────────────────────────────────────────────────
function liveSearch(q) {
  const overlay = document.getElementById('search-results');
  const list    = document.getElementById('search-list');
  const heading = document.getElementById('search-heading');
  q = q.trim().toLowerCase();
  if (q.length < 2) { overlay.classList.remove('open'); return; }

  const re = new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'), 'gi');
  const results = [];
  PAGES.forEach(([pid, label]) => {
    const sec = document.getElementById('page-' + pid);
    if (!sec) return;
    const text = sec.innerText;
    const idx = text.toLowerCase().indexOf(q);
    if (idx !== -1) {
      const snippet = text.slice(Math.max(0, idx-60), idx+120).replace(/\\n+/g,' ');
      results.push({pid, label, snippet, count: (text.toLowerCase().match(new RegExp(q,'g'))||[]).length});
    }
  });
  results.sort((a,b) => b.count - a.count);

  heading.textContent = `${results.length} result${results.length !== 1 ? 's' : ''} for "${q}"`;
  list.innerHTML = results.map(r =>
    `<div class="sr-item" onclick="showPage('${r.pid}');document.getElementById('sb-search-input').value='';clearSearch()">
       <strong>${r.label}</strong>
       <span>${r.snippet.replace(re, m => '<mark class=\\'search-highlight\\'>' + m + '</mark>')}</span>
     </div>`
  ).join('') || '<p style="color:#888;padding:8px 0">No results found.</p>';
  overlay.classList.add('open');
}

function clearSearch() {
  document.getElementById('search-results').classList.remove('open');
}

// ── Hash routing ──────────────────────────────────────────────────────────────
function routeFromHash() {
  const hash = location.hash.slice(1);
  if (hash && PAGES.some(p => p[0] === hash)) showPage(hash);
  else showPage(PAGES[0][0]);
}

document.addEventListener('DOMContentLoaded', routeFromHash);
window.addEventListener('hashchange', routeFromHash);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') clearSearch();
  if (e.key === 'ArrowLeft'  && e.altKey) navigatePage(-1);
  if (e.key === 'ArrowRight' && e.altKey) navigatePage(1);
});

// ── Anchor links inside pages ─────────────────────────────────────────────────
document.addEventListener('click', e => {
  const a = e.target.closest('a');
  if (!a) return;
  const href = a.getAttribute('href');
  if (!href) return;
  // Internal page links (#pid)
  if (href.startsWith('#') && !href.includes('-')) {
    const pid = href.slice(1);
    if (PAGES.some(p => p[0] === pid)) { e.preventDefault(); showPage(pid); }
  }
});
</script>
</body>
</html>
"""


def build():
    print("Building Anvil Wiki HTML...")

    sidebar_html = build_sidebar()
    pages_html   = build_pages()

    # Pages data for JS
    pages_data = str([[p[0], p[1]] for p in PAGES]).replace("'", '"')

    # Pygments CSS
    pygments_css = PYGMENTS_CSS
    # Override background to match our dark theme
    pygments_css = re.sub(r'\.codehilite\s*\{[^}]*\}', '', pygments_css)

    html = (HTML_TEMPLATE
            .replace("PYGMENTS_CSS_PLACEHOLDER", pygments_css)
            .replace("SIDEBAR_PLACEHOLDER", sidebar_html)
            .replace("PAGES_PLACEHOLDER", pages_html)
            .replace("PAGES_DATA_PLACEHOLDER", pages_data))

    out = os.path.join(os.path.dirname(__file__), "ANVIL_WIKI.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(out) // 1024
    print(f"Written: {out}  ({size_kb} KB)")
    return out


if __name__ == "__main__":
    out = build()
    if "--open" in sys.argv:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(out)}")
