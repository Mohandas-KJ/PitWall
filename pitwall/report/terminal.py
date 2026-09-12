"""
dashboard.py

Generates a clean, responsive HTML dashboard from a list of "posts".

Each post is expected to be a dict-like object with these keys:
    - text:       str            -> the post's text content
    - timestamp:  str / datetime -> when it was posted
    - url:        str            -> link to the original post
    - image_url:  list[str]      -> list of image URLs attached to the post

Usage from main.py:

    from dashboard import render_dashboard
    from my_scraper import get_posts   # whatever function returns your posts

    posts = get_posts()
    render_dashboard(posts, output_path="dashboard.html", open_browser=True)

That's it — it writes a self-contained HTML file (images are loaded
directly from their URLs, no downloading needed) and can optionally
pop it open in your default browser right away.
"""

from __future__ import annotations

import html
import os
import webbrowser
from datetime import datetime
from typing import Any, Iterable, Mapping, Union

PostLike = Union[Mapping[str, Any], Any]


# --------------------------------------------------------------------------
# Helpers to normalize input (works with dicts OR objects with attributes)
# --------------------------------------------------------------------------

_ALIASES = {
    "timestamp": ("timestamp", "time", "ts", "created_at", "date", "posted_at"),
    "text": ("text", "content", "body", "caption"),
    "url": ("url", "link", "permalink"),
    "image_url": ("image_url", "images", "image_urls", "media"),
}


def _get(post: PostLike, key: str, default=None):
    candidates = _ALIASES.get(key, (key,))
    for cand in candidates:
        if isinstance(post, Mapping):
            if cand in post and post[cand] not in (None, ""):
                return post[cand]
        else:
            val = getattr(post, cand, None)
            if val not in (None, ""):
                return val
    return default


import re

_RELATIVE_RE = re.compile(r"^\s*(\d+)\s*([smhdwy])\s*$", re.IGNORECASE)


def _relative_from_delta(delta_seconds: float) -> str:
    """X/Twitter-style relative time: 4s, 12m, 3h, 2d, 5w, 1y"""
    seconds = int(delta_seconds)
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{max(seconds, 1)}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 7:
        return f"{days}d"
    weeks = days // 7
    if weeks < 52:
        return f"{weeks}w"
    years = days // 365
    return f"{years}y"


def _format_timestamp(ts: Any) -> tuple[str, str]:
    """
    Returns (short_relative_label, full_tooltip_string).
    Accepts:
      - datetime objects
      - ISO / common date strings -> converted to relative ("3h", "2d")
      - already-relative strings like "2m", "4h", "46h", "1d" -> passed through
        (normalized to X-style compact form) with best-effort full tooltip
    """
    if ts is None:
        return "•", "Unknown time"

    if isinstance(ts, datetime):
        delta = (datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()) - ts
        return _relative_from_delta(delta.total_seconds()), ts.strftime("%b %d, %Y · %I:%M %p")

    ts_str = str(ts).strip()

    # Already a compact relative string like "2m", "46h", "3d", "1w"
    m = _RELATIVE_RE.match(ts_str)
    if m:
        return ts_str.lower().replace(" ", ""), ts_str

    # Try absolute date/time formats -> convert to relative
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(ts_str.replace("Z", "+0000"), fmt)
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            return _relative_from_delta((now - dt).total_seconds()), dt.strftime("%b %d, %Y · %I:%M %p")
        except ValueError:
            continue

    # Fallback: show raw string as-is for both
    return ts_str, ts_str


def _normalize_images(image_url: Any) -> list[str]:
    if not image_url:
        return []
    if isinstance(image_url, str):
        return [image_url]
    try:
        return [str(u) for u in image_url if u]
    except TypeError:
        return [str(image_url)]


# --------------------------------------------------------------------------
# Card / gallery rendering
# --------------------------------------------------------------------------

_ACCENTS = ["#6ea8fe", "#f97583", "#3ddc97", "#ffb454", "#c78bff", "#4dd0e1"]

_HASHTAG_RE = re.compile(r"(#\w+)")


def _accent_for(idx: int) -> str:
    return _ACCENTS[idx % len(_ACCENTS)]


def _linkify_hashtags(escaped_text: str) -> str:
    return _HASHTAG_RE.sub(r'<span class="tag">\1</span>', escaped_text)


def _render_image_gallery(images: list[str], idx: int) -> str:
    if not images:
        return ""

    if len(images) == 1:
        return f"""
        <div class="gallery single">
            <img src="{html.escape(images[0])}" loading="lazy" alt="post image"
                 onclick="openLightbox('{idx}', 0)">
        </div>"""

    thumbs = "".join(
        f'<div class="thumb"><img src="{html.escape(src)}" loading="lazy" alt="post image {i+1}" '
        f'onclick="openLightbox(\'{idx}\', {i})"></div>'
        for i, src in enumerate(images[:4])
    )
    extra = len(images) - 4
    if extra > 0:
        thumbs = thumbs.rsplit("<div class=\"thumb\">", 1)[0] + (
            f'<div class="thumb more-overlay" onclick="openLightbox(\'{idx}\', 3)">'
            f'<img src="{html.escape(images[3])}" loading="lazy" alt="post image 4">'
            f'<span class="more-badge">+{extra}</span></div>'
        )
    grid_class = "grid-2" if len(images) == 2 else ("grid-3" if len(images) == 3 else "grid-4")
    return f'<div class="gallery {grid_class}">{thumbs}</div>'


def _render_card(post: PostLike, idx: int) -> str:
    raw_text = str(_get(post, "text", "") or "")
    # quote=False: keep apostrophes/quotes readable instead of turning them into &#x27; / &quot;
    text = _linkify_hashtags(html.escape(raw_text, quote=False)).replace("\n", "<br>")
    rel_time, full_time = _format_timestamp(_get(post, "timestamp"))
    rel_time = html.escape(rel_time)
    full_time = html.escape(full_time)
    url = _get(post, "url", "") or ""
    images = _normalize_images(_get(post, "image_url"))
    accent = _accent_for(idx)

    gallery_html = _render_image_gallery(images, idx)
    images_json = "[" + ",".join(f'"{html.escape(u)}"' for u in images) + "]"

    link_html = (
        f'<a class="post-link" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">'
        f'Open ↗</a>'
        if url else ""
    )

    initial = html.escape(raw_text.strip()[:1].upper()) or "•"

    body = text if text.strip() else '<span class="muted">(no text)</span>'

    return f"""
    <article class="card" data-idx="{idx}" data-images='{images_json}' style="--accent: {accent}">
        <header class="card-header">
            <div class="avatar" style="background: {accent}">{initial}</div>
            <div class="meta-block">
                <span class="timestamp" title="{full_time}">{rel_time}</span>
            </div>
            {link_html}
        </header>
        {gallery_html}
        <div class="post-text-wrap">
            <p class="post-text">{body}</p>
            <button class="expand-btn" onclick="toggleExpand(this)">Show more</button>
        </div>
    </article>
    """


# --------------------------------------------------------------------------
# Full page template
# --------------------------------------------------------------------------

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Post Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
    :root {{
        --bg: #0b0d12;
        --bg-2: #0e1016;
        --card-bg: #14161d;
        --card-bg-hover: #171a22;
        --text: #f1f2f5;
        --muted: #90959f;
        --border: #23262f;
        --accent: #6ea8fe;
        --radius: 16px;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
        margin: 0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background:
            radial-gradient(1200px 600px at 10% -10%, rgba(110,168,254,0.10), transparent 60%),
            radial-gradient(1000px 500px at 90% 0%, rgba(199,139,255,0.08), transparent 55%),
            var(--bg);
        color: var(--text);
        -webkit-font-smoothing: antialiased;
    }}

    .topbar {{
        position: sticky; top: 0; z-index: 5;
        background: rgba(11,13,18,0.78);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border-bottom: 1px solid var(--border);
        padding: 18px 28px;
        display: flex; align-items: center; justify-content: space-between;
        flex-wrap: wrap; gap: 14px;
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand-icon {{
        width: 38px; height: 38px; border-radius: 11px;
        background: linear-gradient(135deg, #6ea8fe, #c78bff);
        display: flex; align-items: center; justify-content: center;
        font-size: 18px; box-shadow: 0 4px 16px rgba(110,168,254,0.35);
    }}
    .topbar h1 {{ font-size: 17px; margin: 0; font-weight: 700; letter-spacing: -0.01em; }}
    .topbar .meta {{ color: var(--muted); font-size: 12.5px; margin-top: 2px; }}
    .controls {{ display: flex; gap: 10px; align-items: center; }}
    .controls input {{
        background: var(--card-bg); border: 1px solid var(--border);
        color: var(--text); padding: 9px 14px; border-radius: 10px;
        font-size: 13px; width: 230px; font-family: inherit;
        transition: border-color .15s ease;
    }}
    .controls input:focus {{ outline: none; border-color: var(--accent); }}
    .controls select {{
        background: var(--card-bg); border: 1px solid var(--border);
        color: var(--text); padding: 9px 12px; border-radius: 10px; font-size: 13px;
        font-family: inherit; cursor: pointer;
    }}

    .grid-wrap {{
        padding: 24px 28px 60px;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        grid-auto-rows: 1fr;
        gap: 18px;
        max-width: 1800px;
        margin: 0 auto;
    }}

    .card {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        position: relative;
        overflow: hidden;
        transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease;
    }}
    .card::before {{
        content: "";
        position: absolute; top: 0; left: 0; right: 0; height: 3px;
        background: var(--accent);
        opacity: 0.9;
    }}
    .card:hover {{
        border-color: var(--accent);
        background: var(--card-bg-hover);
        transform: translateY(-3px);
        box-shadow: 0 12px 28px rgba(0,0,0,0.35);
    }}

    .card-header {{
        display: flex; align-items: center; gap: 10px;
    }}
    .avatar {{
        width: 30px; height: 30px; min-width: 30px; border-radius: 9px;
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 13px; color: #0b0d12;
    }}
    .meta-block {{ display: flex; flex-direction: column; flex: 1; min-width: 0; }}
    .timestamp {{
        color: var(--muted); font-size: 12px; font-weight: 500; white-space: nowrap;
        cursor: default;
    }}
    .post-link {{
        color: var(--accent); text-decoration: none; font-size: 12px; font-weight: 700;
        white-space: nowrap; padding: 5px 10px; border-radius: 8px;
        background: rgba(110,168,254,0.10);
        transition: background .15s ease;
    }}
    .post-link:hover {{ background: rgba(110,168,254,0.20); }}

    .post-text-wrap {{ display: flex; flex-direction: column; gap: 4px; flex: 1; }}
    .post-text {{
        font-size: 14px; line-height: 1.55; margin: 0; word-wrap: break-word;
        color: #dfe1e6;
        display: -webkit-box;
        -webkit-line-clamp: 4;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}
    .post-text.expanded {{ -webkit-line-clamp: unset; overflow: visible; }}
    .muted {{ color: var(--muted); font-style: italic; }}
    .tag {{ color: var(--accent); font-weight: 600; }}
    .expand-btn {{
        display: none; align-self: flex-start;
        background: none; border: none; color: var(--accent);
        font-size: 12.5px; font-weight: 700; cursor: pointer; padding: 0;
        font-family: inherit;
    }}
    .expand-btn.visible {{ display: inline-block; }}

    .gallery {{
        display: grid; gap: 4px; border-radius: 12px; overflow: hidden;
        background: #000;
    }}
    .thumb {{ position: relative; overflow: hidden; aspect-ratio: 1/1; }}
    .gallery img {{
        width: 100%; height: 100%; object-fit: cover; cursor: zoom-in; display: block;
        transition: transform .25s ease;
    }}
    .thumb:hover img {{ transform: scale(1.05); }}
    /* Single image: show the WHOLE image (no cropping), letterboxed on a dark backdrop */
    .gallery.single {{
        aspect-ratio: 16/9;
        display: flex; align-items: center; justify-content: center;
        background: #000;
    }}
    .gallery.single img {{
        width: 100%; height: 100%; object-fit: contain; background: #000;
    }}
    .gallery.grid-2 {{ grid-template-columns: 1fr 1fr; aspect-ratio: 16/9; }}
    .gallery.grid-2 .thumb {{ aspect-ratio: auto; }}
    .gallery.grid-3 {{ grid-template-columns: 1.3fr 1fr; grid-template-rows: 1fr 1fr; aspect-ratio: 16/9; }}
    .gallery.grid-3 .thumb {{ aspect-ratio: auto; }}
    .gallery.grid-3 .thumb:first-child {{ grid-row: span 2; }}
    .gallery.grid-4 {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; aspect-ratio: 16/9; }}
    .gallery.grid-4 .thumb {{ aspect-ratio: auto; }}
    .more-overlay {{ position: relative; }}
    .more-badge {{
        position: absolute; inset: 0; background: rgba(0,0,0,0.55);
        display: flex; align-items: center; justify-content: center;
        color: #fff; font-size: 20px; font-weight: 700;
    }}

    #emptyState {{
        text-align: center; color: var(--muted); padding: 80px 20px; display: none;
        font-size: 14px;
    }}

    /* Lightbox */
    #lightbox {{
        position: fixed; inset: 0; background: rgba(5,6,9,0.94);
        backdrop-filter: blur(6px);
        display: none; align-items: center; justify-content: center;
        z-index: 50; flex-direction: column;
    }}
    #lightbox.active {{ display: flex; }}
    #lightbox img {{ max-width: 90vw; max-height: 78vh; border-radius: 10px; box-shadow: 0 20px 60px rgba(0,0,0,0.6); }}
    #lightbox .lb-controls {{
        margin-top: 18px; display: flex; gap: 18px; align-items: center; color: #fff;
    }}
    #lightbox button {{
        background: #1c1f28; color: #fff; border: 1px solid var(--border); padding: 9px 16px;
        border-radius: 10px; cursor: pointer; font-size: 14px; font-family: inherit; font-weight: 600;
        transition: background .15s ease;
    }}
    #lightbox button:hover {{ background: #262a35; }}
    #lightbox .close-btn {{
        position: absolute; top: 22px; right: 26px; font-size: 22px; cursor: pointer; color: #fff;
        width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.08);
        display: flex; align-items: center; justify-content: center;
    }}
    #lightbox .close-btn:hover {{ background: rgba(255,255,255,0.16); }}
    #lightboxCounter {{ font-size: 13px; color: var(--muted); min-width: 50px; text-align: center; }}
</style>
</head>
<body>

<div class="topbar">
    <div class="brand">
        <div class="brand-icon">📋</div>
        <div>
            <h1>Post Dashboard</h1>
            <div class="meta">{count} posts · generated {generated_at}</div>
        </div>
    </div>
    <div class="controls">
        <input type="text" id="searchBox" placeholder="Search text or URL..." oninput="filterCards()">
        <select id="sortSelect" onchange="sortCards()">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
        </select>
    </div>
</div>

<div class="grid-wrap" id="grid">
{cards}
</div>
<div id="emptyState">No posts match your search.</div>

<div id="lightbox">
    <span class="close-btn" onclick="closeLightbox()">✕</span>
    <img id="lightboxImg" src="">
    <div class="lb-controls">
        <button onclick="navLightbox(-1)">‹ Prev</button>
        <span id="lightboxCounter"></span>
        <button onclick="navLightbox(1)">Next ›</button>
    </div>
</div>

<script>
let currentImages = [];
let currentIndex = 0;

function openLightbox(cardIdx, imgIdx) {{
    const card = document.querySelector(`.card[data-idx="${{cardIdx}}"]`);
    currentImages = JSON.parse(card.getAttribute('data-images'));
    currentIndex = imgIdx;
    updateLightbox();
    document.getElementById('lightbox').classList.add('active');
}}
function updateLightbox() {{
    document.getElementById('lightboxImg').src = currentImages[currentIndex];
    document.getElementById('lightboxCounter').textContent =
        (currentIndex + 1) + ' / ' + currentImages.length;
}}
function navLightbox(delta) {{
    currentIndex = (currentIndex + delta + currentImages.length) % currentImages.length;
    updateLightbox();
}}
function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('active');
}}
document.addEventListener('keydown', (e) => {{
    if (!document.getElementById('lightbox').classList.contains('active')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowRight') navLightbox(1);
    if (e.key === 'ArrowLeft') navLightbox(-1);
}});

function filterCards() {{
    const q = document.getElementById('searchBox').value.toLowerCase();
    const cards = document.querySelectorAll('.card');
    let visibleCount = 0;
    cards.forEach(card => {{
        const match = card.innerText.toLowerCase().includes(q);
        card.style.display = match ? '' : 'none';
        if (match) visibleCount++;
    }});
    document.getElementById('emptyState').style.display = visibleCount === 0 ? 'block' : 'none';
}}

function sortCards() {{
    const grid = document.getElementById('grid');
    const cards = Array.from(grid.querySelectorAll('.card'));
    const order = document.getElementById('sortSelect').value;
    cards.sort((a, b) => {{
        const idxA = parseInt(a.getAttribute('data-idx'));
        const idxB = parseInt(b.getAttribute('data-idx'));
        return order === 'newest' ? idxA - idxB : idxB - idxA;
    }});
    cards.forEach(c => grid.appendChild(c));
}}

function toggleExpand(btn) {{
    const p = btn.previousElementSibling;
    p.classList.toggle('expanded');
    btn.textContent = p.classList.contains('expanded') ? 'Show less' : 'Show more';
}}

// Only show "Show more" when text actually overflows its clamp
function initExpandButtons() {{
    document.querySelectorAll('.post-text-wrap').forEach(wrap => {{
        const p = wrap.querySelector('.post-text');
        const btn = wrap.querySelector('.expand-btn');
        if (p.scrollHeight > p.clientHeight + 2) {{
            btn.classList.add('visible');
        }}
    }});
}}
window.addEventListener('load', initExpandButtons);
window.addEventListener('resize', () => {{
    document.querySelectorAll('.post-text.expanded').forEach(p => p.classList.remove('expanded'));
    document.querySelectorAll('.expand-btn').forEach(b => {{ b.classList.remove('visible'); b.textContent = 'Show more'; }});
    initExpandButtons();
}});
</script>

</body>
</html>
"""


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def render_dashboard(
    posts: Iterable[PostLike],
    output_path: str = "dashboard.html",
    open_browser: bool = True,
) -> str:
    """
    Build an HTML dashboard from a collection of posts and write it to disk.

    Parameters
    ----------
    posts : iterable of dict-like objects
        Each item must expose: text, timestamp, url, image_url (list).
        Assumed to already be ordered newest -> oldest (as returned by
        your scraping function). The dashboard preserves that order by
        default ("Newest first").
    output_path : str
        Where to write the HTML file.
    open_browser : bool
        If True, automatically opens the generated dashboard in the
        default web browser.

    Returns
    -------
    str
        The absolute path to the generated HTML file.
    """
    posts = list(posts)
    cards_html = "\n".join(_render_card(post, i) for i, post in enumerate(posts))

    page = _PAGE_TEMPLATE.format(
        count=len(posts),
        generated_at=datetime.now().strftime("%b %d, %Y · %I:%M %p"),
        cards=cards_html if posts else "",
    )

    abs_path = os.path.abspath(output_path)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(page)

    if open_browser:
        webbrowser.open(f"file://{abs_path}")

    return abs_path


# --------------------------------------------------------------------------
# Example usage (only runs if you execute this file directly)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    sample_posts = [
        {
            "text": "Just launched our new product! Check out the screenshots below 🚀 It's finally here.",
            "timestamp": "2m",
            "url": "https://example.com/post/1",
            "image_url": [
                "https://picsum.photos/seed/1/600/400",
                "https://picsum.photos/seed/2/600/400",
            ],
        },
        {
            "text": "A quiet Saturday morning walk. Didn't expect it to be this nice out.",
            "timestamp": "46h",
            "url": "https://example.com/post/2",
            "image_url": ["https://picsum.photos/seed/3/900/500"],
        },
        {
            "text": "No images here, just text — testing empty gallery state.",
            "timestamp": "4h",
            "url": "https://example.com/post/3",
            "image_url": [],
        },
    ]
    render_dashboard(sample_posts, output_path="dashboard.html", open_browser=False)
    print("Sample dashboard written to dashboard.html")