"""
terminal.py - PitWall Report & Dashboard Generator

Generates:
1. An awesome, interactive 3D Glassmorphic Formula 1 PitWall HTML Dashboard.
2. A high-tech terminal-only telemetry report for console display.

Supports standard post dicts or objects with:
    - text:       str            -> the post's text content
    - timestamp:  str / datetime -> when it was posted
    - url:        str            -> link to the original post
    - image_url:  list[str]      -> list of image URLs attached to the post
"""

from __future__ import annotations

import html
import os
import re
import sys
import textwrap
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


_RELATIVE_RE = re.compile(r"^\s*(\d+)\s*([smhdwy])\s*$", re.IGNORECASE)


def _relative_from_delta(delta_seconds: float) -> str:
    """Motorsport/Twitter-style compact relative time."""
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
    """
    if ts is None:
        return "LIVE", "Live Session"

    if isinstance(ts, datetime):
        delta = (datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()) - ts
        return _relative_from_delta(delta.total_seconds()), ts.strftime("%b %d, %Y · %I:%M %p")

    ts_str = str(ts).strip()

    m = _RELATIVE_RE.match(ts_str)
    if m:
        return ts_str.lower().replace(" ", ""), f"{ts_str} ago"

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
# Visual Accents & Card Rendering
# --------------------------------------------------------------------------

# Formula 1 PitWall Racing Accents:
# Racing Red, Telemetry Cyan, Speed Amber, Aero Electric Blue, Podium Violet, Green Flag Emerald
_ACCENTS = ["#E10600", "#00F5D4", "#FFB703", "#3B82F6", "#A855F7", "#10B981"]

_HASHTAG_RE = re.compile(r"(#\w+)")
_MENTION_RE = re.compile(r"(@\w+)")


def _accent_for(idx: int) -> str:
    return _ACCENTS[idx % len(_ACCENTS)]


def _linkify_entities(escaped_text: str) -> str:
    text = _HASHTAG_RE.sub(r'<span class="tag">\1</span>', escaped_text)
    text = _MENTION_RE.sub(r'<span class="mention">\1</span>', text)
    return text


def _render_image_gallery(images: list[str], idx: int) -> str:
    if not images:
        return ""

    if len(images) == 1:
        return f"""
        <div class="gallery single">
            <img src="{html.escape(images[0])}" loading="lazy" alt="transmission media"
                 onclick="openLightbox('{idx}', 0)">
        </div>"""

    thumbs = "".join(
        f'<div class="thumb"><img src="{html.escape(src)}" loading="lazy" alt="transmission media {i+1}" '
        f'onclick="openLightbox(\'{idx}\', {i})"></div>'
        for i, src in enumerate(images[:4])
    )
    extra = len(images) - 4
    if extra > 0:
        thumbs = thumbs.rsplit('<div class="thumb">', 1)[0] + (
            f'<div class="thumb more-overlay" onclick="openLightbox(\'{idx}\', 3)">'
            f'<img src="{html.escape(images[3])}" loading="lazy" alt="transmission media 4">'
            f'<span class="more-badge">+{extra}</span></div>'
        )
    grid_class = "grid-2" if len(images) == 2 else ("grid-3" if len(images) == 3 else "grid-4")
    return f'<div class="gallery {grid_class}">{thumbs}</div>'


def _render_card(post: PostLike, idx: int) -> str:
    raw_text = str(_get(post, "text", "") or "")
    text = _linkify_entities(html.escape(raw_text, quote=False)).replace("\n", "<br>")
    rel_time, full_time = _format_timestamp(_get(post, "timestamp"))
    rel_time = html.escape(rel_time)
    full_time = html.escape(full_time)
    url = _get(post, "url", "") or ""
    images = _normalize_images(_get(post, "image_url"))
    accent = _accent_for(idx)
    has_media = "true" if images else "false"

    gallery_html = _render_image_gallery(images, idx)
    images_json = "[" + ",".join(f'"{html.escape(u)}"' for u in images) + "]"

    link_html = (
        f'<a class="post-link" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">'
        f'<span>OPEN</span> <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg></a>'
        if url else ""
    )

    body = text if text.strip() else '<span class="muted">// NO TELEMETRY TEXT CONTENT</span>'
    char_count = len(raw_text.strip())

    return f"""
    <div class="card-tilt-container" data-idx="{idx}">
        <article class="card" data-idx="{idx}" data-has-media="{has_media}" data-images='{images_json}' style="--accent: {accent}">
            <div class="card-glare"></div>
            <div class="card-sheen"></div>
            
            <header class="card-header">
                <div class="tx-badge">
                    <span class="tx-pulse" style="background: {accent}"></span>
                    <span class="tx-label">TX #{idx+1:02d}</span>
                </div>
                <div class="meta-block">
                    <span class="timestamp" title="{full_time}">⏱ {rel_time}</span>
                </div>
                {link_html}
            </header>

            {gallery_html}

            <div class="post-text-wrap">
                <p class="post-text">{body}</p>
                <button class="expand-btn" onclick="toggleExpand(this)">SHOW MORE ▾</button>
            </div>

            <footer class="card-footer">
                <div class="telemetry-tag">
                    <span class="dot"></span> PITWALL FEED
                </div>
                <div class="card-stats">
                    {f'<span class="stat-media">📷 {len(images)}</span>' if images else ''}
                    <span class="stat-chars">{char_count} chars</span>
                </div>
            </footer>
        </article>
    </div>
    """


# --------------------------------------------------------------------------
# 3D Glassmorphic Full Page Template
# --------------------------------------------------------------------------

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PitWall // Formula 1 Telemetry Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
    :root {{
        --bg-base: #06070a;
        --bg-surface: #0a0d14;
        --glass-bg: rgba(14, 18, 28, 0.55);
        --glass-bg-hover: rgba(20, 26, 40, 0.75);
        --glass-border: rgba(255, 255, 255, 0.12);
        --glass-border-hover: rgba(255, 255, 255, 0.28);
        --text-main: #f0f3fa;
        --text-muted: #8b92a5;
        --f1-red: #E10600;
        --telemetry-cyan: #00F5D4;
        --speed-amber: #FFB703;
        --card-radius: 20px;
        --shadow-elevation: 0 20px 45px rgba(0, 0, 0, 0.6), 0 1px 2px rgba(255, 255, 255, 0.05);
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        min-height: 100vh;
        background-color: var(--bg-base);
        background-image: 
            radial-gradient(circle at 15% 10%, rgba(225, 6, 0, 0.12) 0%, transparent 45%),
            radial-gradient(circle at 85% 15%, rgba(0, 245, 212, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 50% 85%, rgba(59, 130, 246, 0.07) 0%, transparent 55%),
            linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 100% 100%, 40px 40px, 40px 40px;
        color: var(--text-main);
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        -webkit-font-smoothing: antialiased;
        overflow-x: hidden;
    }}

    /* 3D Ambient Perspective Layer */
    .viewport-3d {{
        perspective: 1400px;
        transform-style: preserve-3d;
    }}

    /* Topbar Glassmorphic Cockpit */
    .topbar {{
        position: sticky;
        top: 0;
        z-index: 100;
        background: rgba(8, 11, 18, 0.72);
        backdrop-filter: blur(24px) saturate(190%);
        -webkit-backdrop-filter: blur(24px) saturate(190%);
        border-bottom: 1px solid var(--glass-border);
        padding: 16px 36px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }}

    .brand-cluster {{
        display: flex;
        align-items: center;
        gap: 16px;
    }}

    .f1-badge {{
        background: linear-gradient(135deg, var(--f1-red) 0%, #b30000 100%);
        color: #fff;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 14px;
        padding: 8px 14px;
        border-radius: 10px;
        letter-spacing: 0.12em;
        box-shadow: 0 4px 18px rgba(225, 6, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    .f1-badge .pulse-ring {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #fff;
        box-shadow: 0 0 10px #fff;
        animation: pulseRadar 1.5s infinite;
    }}

    @keyframes pulseRadar {{
        0% {{ transform: scale(0.9); opacity: 0.8; }}
        50% {{ transform: scale(1.3); opacity: 1; }}
        100% {{ transform: scale(0.9); opacity: 0.8; }}
    }}

    .brand-title h1 {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 19px;
        font-weight: 700;
        letter-spacing: -0.02em;
        display: flex;
        align-items: center;
        gap: 10px;
        color: #fff;
    }}

    .brand-title .live-indicator {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 600;
        color: var(--telemetry-cyan);
        background: rgba(0, 245, 212, 0.12);
        padding: 2px 8px;
        border-radius: 6px;
        border: 1px solid rgba(0, 245, 212, 0.3);
        letter-spacing: 0.08em;
    }}

    .brand-title .meta {{
        font-size: 12px;
        color: var(--text-muted);
        margin-top: 2px;
        font-family: 'JetBrains Mono', monospace;
    }}

    /* Cockpit Telemetry Stats Header */
    .telemetry-strip {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}

    .stat-pill {{
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(12px);
        padding: 6px 14px;
        border-radius: 10px;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--text-muted);
    }}

    .stat-pill strong {{
        color: #fff;
        font-weight: 700;
    }}

    /* Search & Filter Controls */
    .controls {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}

    .search-wrapper {{
        position: relative;
    }}

    .search-wrapper input {{
        background: rgba(14, 18, 28, 0.8);
        border: 1px solid var(--glass-border);
        color: var(--text-main);
        padding: 10px 16px 10px 38px;
        border-radius: 12px;
        font-size: 13px;
        width: 260px;
        font-family: inherit;
        backdrop-filter: blur(16px);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.4);
    }}

    .search-wrapper input:focus {{
        outline: none;
        border-color: var(--telemetry-cyan);
        width: 310px;
        box-shadow: 0 0 20px rgba(0, 245, 212, 0.25), inset 0 2px 4px rgba(0,0,0,0.4);
    }}

    .search-icon {{
        position: absolute;
        left: 14px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 13px;
        color: var(--text-muted);
        pointer-events: none;
    }}

    .filter-pills {{
        display: flex;
        gap: 6px;
    }}

    .pill-btn {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid var(--glass-border);
        color: var(--text-muted);
        padding: 8px 14px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        font-family: inherit;
    }}

    .pill-btn:hover, .pill-btn.active {{
        background: rgba(255, 255, 255, 0.15);
        color: #fff;
        border-color: rgba(255, 255, 255, 0.35);
    }}

    .pill-btn.active {{
        background: linear-gradient(135deg, rgba(225, 6, 0, 0.35), rgba(0, 245, 212, 0.2));
        border-color: var(--telemetry-cyan);
        color: #fff;
        box-shadow: 0 0 14px rgba(0, 245, 212, 0.25);
    }}

    .select-control {{
        background: rgba(14, 18, 28, 0.8);
        border: 1px solid var(--glass-border);
        color: var(--text-main);
        padding: 9px 14px;
        border-radius: 12px;
        font-size: 12.5px;
        font-family: inherit;
        cursor: pointer;
        outline: none;
        transition: border-color 0.2s ease;
    }}

    .select-control:focus {{
        border-color: var(--telemetry-cyan);
    }}

    /* 3D Cards Grid Container */
    .grid-wrap {{
        padding: 36px 36px 80px;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
        gap: 26px;
        max-width: 1800px;
        margin: 0 auto;
    }}

    /* 3D Tilt Wrapper */
    .card-tilt-container {{
        perspective: 1200px;
        transform-style: preserve-3d;
    }}

    /* Glassmorphism 3D Card */
    .card {{
        background: var(--glass-bg);
        backdrop-filter: blur(24px) saturate(190%);
        -webkit-backdrop-filter: blur(24px) saturate(190%);
        border: 1px solid var(--glass-border);
        border-radius: var(--card-radius);
        padding: 20px;
        display: flex;
        flex-direction: column;
        gap: 16px;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-elevation);
        transform-style: preserve-3d;
        transition: transform 0.15s ease-out, border-color 0.25s ease, box-shadow 0.25s ease;
        will-change: transform;
    }}

    .card::before {{
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--accent);
        box-shadow: 0 0 16px var(--accent);
        opacity: 0.9;
    }}

    .card-sheen {{
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
        pointer-events: none;
    }}

    .card-glare {{
        position: absolute;
        inset: 0;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.25s ease;
        border-radius: var(--card-radius);
    }}

    .card:hover {{
        border-color: var(--glass-border-hover);
        box-shadow: 0 26px 60px rgba(0, 0, 0, 0.7), 0 0 25px rgba(255, 255, 255, 0.08);
    }}

    /* Card Header */
    .card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        transform: translateZ(12px);
    }}

    .tx-badge {{
        display: flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 5px 10px;
        border-radius: 8px;
    }}

    .tx-pulse {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px currentColor;
    }}

    .tx-label {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #fff;
    }}

    .meta-block {{
        display: flex;
        align-items: center;
        flex: 1;
        margin-left: 4px;
    }}

    .timestamp {{
        color: var(--text-muted);
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 500;
    }}

    .post-link {{
        color: var(--text-main);
        text-decoration: none;
        font-size: 11px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 5px 12px;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.14);
        transition: all 0.2s ease;
    }}

    .post-link:hover {{
        background: var(--accent);
        color: #000;
        border-color: var(--accent);
        box-shadow: 0 0 16px var(--accent);
    }}

    /* Card Media Gallery */
    .gallery {{
        display: grid;
        gap: 6px;
        border-radius: 14px;
        overflow: hidden;
        background: #020305;
        border: 1px solid rgba(255, 255, 255, 0.07);
        transform: translateZ(16px);
        transition: transform 0.25s ease;
    }}

    .thumb {{
        position: relative;
        overflow: hidden;
        aspect-ratio: 1/1;
    }}

    .gallery img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        cursor: zoom-in;
        display: block;
        transition: transform 0.4s cubic-bezier(0.2, 0.9, 0.3, 1);
    }}

    .thumb:hover img {{
        transform: scale(1.06);
    }}

    .gallery.single {{
        aspect-ratio: 16/9;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #020305;
    }}

    .gallery.single img {{
        width: 100%;
        height: 100%;
        object-fit: contain;
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
        position: absolute;
        inset: 0;
        background: rgba(8, 11, 18, 0.7);
        backdrop-filter: blur(4px);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 20px;
        font-weight: 700;
    }}

    /* Card Body Text */
    .post-text-wrap {{
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex: 1;
        transform: translateZ(8px);
    }}

    .post-text {{
        font-size: 14.5px;
        line-height: 1.6;
        word-wrap: break-word;
        color: #dce1ee;
        display: -webkit-box;
        -webkit-line-clamp: 4;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    .post-text.expanded {{
        -webkit-line-clamp: unset;
        overflow: visible;
    }}

    .tag {{
        color: var(--telemetry-cyan);
        font-weight: 600;
        background: rgba(0, 245, 212, 0.08);
        padding: 1px 6px;
        border-radius: 6px;
    }}

    .mention {{
        color: var(--speed-amber);
        font-weight: 600;
    }}

    .muted {{
        color: var(--text-muted);
        font-style: italic;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
    }}

    .expand-btn {{
        display: none;
        align-self: flex-start;
        background: none;
        border: none;
        color: var(--telemetry-cyan);
        font-size: 11.5px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        letter-spacing: 0.06em;
        cursor: pointer;
        padding: 4px 0;
    }}

    .expand-btn.visible {{
        display: inline-block;
    }}

    /* Card Footer */
    .card-footer {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 11px;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-muted);
        transform: translateZ(10px);
    }}

    .telemetry-tag {{
        display: flex;
        align-items: center;
        gap: 6px;
        letter-spacing: 0.06em;
    }}

    .telemetry-tag .dot {{
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--accent);
    }}

    .card-stats {{
        display: flex;
        gap: 10px;
    }}

    /* Empty State */
    #emptyState {{
        text-align: center;
        color: var(--text-muted);
        padding: 90px 20px;
        display: none;
        font-size: 15px;
        font-family: 'Space Grotesk', sans-serif;
    }}

    /* Lightbox Modal */
    #lightbox {{
        position: fixed;
        inset: 0;
        background: rgba(3, 5, 8, 0.92);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        display: none;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        flex-direction: column;
    }}

    #lightbox.active {{
        display: flex;
    }}

    #lightbox img {{
        max-width: 90vw;
        max-height: 78vh;
        border-radius: 14px;
        box-shadow: 0 30px 80px rgba(0, 0, 0, 0.8), 0 0 30px rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.15);
    }}

    .lb-controls {{
        margin-top: 22px;
        display: flex;
        gap: 16px;
        align-items: center;
    }}

    .lb-btn {{
        background: rgba(255, 255, 255, 0.08);
        color: #fff;
        border: 1px solid var(--glass-border);
        padding: 10px 20px;
        border-radius: 12px;
        cursor: pointer;
        font-size: 13px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        letter-spacing: 0.06em;
        backdrop-filter: blur(10px);
        transition: all 0.2s ease;
    }}

    .lb-btn:hover {{
        background: rgba(255, 255, 255, 0.2);
        border-color: #fff;
    }}

    .close-btn {{
        position: absolute;
        top: 28px;
        right: 32px;
        font-size: 20px;
        cursor: pointer;
        color: #fff;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
    }}

    .close-btn:hover {{
        background: var(--f1-red);
        border-color: var(--f1-red);
    }}

    #lightboxCounter {{
        font-size: 13px;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-muted);
        min-width: 60px;
        text-align: center;
    }}

    @media (max-width: 768px) {{
        .topbar {{
            padding: 14px 18px;
            flex-direction: column;
            align-items: stretch;
        }}
        .controls {{
            flex-direction: column;
            align-items: stretch;
        }}
        .search-wrapper input {{
            width: 100%;
        }}
        .search-wrapper input:focus {{
            width: 100%;
        }}
        .grid-wrap {{
            padding: 20px 16px 60px;
            grid-template-columns: 1fr;
        }}
    }}
</style>
</head>
<body>

<div class="viewport-3d">
    <header class="topbar">
        <div class="brand-cluster">
            <div class="f1-badge">
                <span class="pulse-ring"></span>
                <span>PITWALL</span>
            </div>
            <div class="brand-title">
                <h1>Formula 1 Telemetry <span class="live-indicator">ACTIVE</span></h1>
                <div class="meta">{count} Transmissions · Synced {generated_at}</div>
            </div>
        </div>

        <div class="telemetry-strip">
            <div class="stat-pill">
                <span>FEED:</span>
                <strong>OFFICIAL F1</strong>
            </div>
            <div class="stat-pill">
                <span>MEDIA:</span>
                <strong>{media_count} FILES</strong>
            </div>
        </div>

        <div class="controls">
            <div class="search-wrapper">
                <span class="search-icon">🔍</span>
                <input type="text" id="searchBox" placeholder="Search telemetry or tags..." oninput="filterCards()">
            </div>
            <div class="filter-pills">
                <button class="pill-btn active" data-filter="all" onclick="setFilter(this, 'all')">ALL</button>
                <button class="pill-btn" data-filter="media" onclick="setFilter(this, 'media')">MEDIA</button>
                <button class="pill-btn" data-filter="text" onclick="setFilter(this, 'text')">TEXT ONLY</button>
            </div>
            <select id="sortSelect" class="select-control" onchange="sortCards()">
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
            </select>
        </div>
    </header>

    <main class="grid-wrap" id="grid">
{cards}
    </main>
    <div id="emptyState">No telemetry transmissions match your filter query.</div>
</div>

<div id="lightbox">
    <span class="close-btn" onclick="closeLightbox()">✕</span>
    <img id="lightboxImg" src="" alt="expanded preview">
    <div class="lb-controls">
        <button class="lb-btn" onclick="navLightbox(-1)">‹ PREV</button>
        <span id="lightboxCounter"></span>
        <button class="lb-btn" onclick="navLightbox(1)">NEXT ›</button>
    </div>
</div>

<script>
// --- 3D Interactive Tilt & Holographic Glare Physics ---
function init3DTilt() {{
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {{
        card.addEventListener('mousemove', (e) => {{
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = ((y - centerY) / centerY) * -8;
            const rotateY = ((x - centerX) / centerX) * 8;
            
            card.style.transform = `perspective(1200px) rotateX(${{rotateX}}deg) rotateY(${{rotateY}}deg) translateZ(8px) scale3d(1.015, 1.015, 1.015)`;
            
            const glare = card.querySelector('.card-glare');
            if (glare) {{
                glare.style.opacity = '1';
                glare.style.background = `radial-gradient(circle at ${{x}}px ${{y}}px, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.03) 50%, transparent 80%)`;
            }}
        }});

        card.addEventListener('mouseleave', () => {{
            card.style.transform = 'perspective(1200px) rotateX(0deg) rotateY(0deg) translateZ(0px) scale3d(1, 1, 1)';
            const glare = card.querySelector('.card-glare');
            if (glare) glare.style.opacity = '0';
        }});
    }});
}}

// --- Lightbox Viewer ---
let currentImages = [];
let currentIndex = 0;

function openLightbox(cardIdx, imgIdx) {{
    const card = document.querySelector(`.card[data-idx="${{cardIdx}}"]`);
    if (!card) return;
    currentImages = JSON.parse(card.getAttribute('data-images') || '[]');
    currentIndex = imgIdx;
    updateLightbox();
    document.getElementById('lightbox').classList.add('active');
}}

function updateLightbox() {{
    if (!currentImages.length) return;
    document.getElementById('lightboxImg').src = currentImages[currentIndex];
    document.getElementById('lightboxCounter').textContent =
        (currentIndex + 1) + ' / ' + currentImages.length;
}}

function navLightbox(delta) {{
    if (!currentImages.length) return;
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

// --- Realtime Filtering & Search ---
let currentFilter = 'all';

function setFilter(btn, filterType) {{
    document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = filterType;
    filterCards();
}}

function filterCards() {{
    const query = document.getElementById('searchBox').value.toLowerCase().trim();
    const cards = document.querySelectorAll('.card-tilt-container');
    let visibleCount = 0;

    cards.forEach(wrap => {{
        const card = wrap.querySelector('.card');
        const text = card.innerText.toLowerCase();
        const hasMedia = card.getAttribute('data-has-media') === 'true';

        let matchesFilter = true;
        if (currentFilter === 'media' && !hasMedia) matchesFilter = false;
        if (currentFilter === 'text' && hasMedia) matchesFilter = false;

        const matchesQuery = !query || text.includes(query);

        if (matchesFilter && matchesQuery) {{
            wrap.style.display = '';
            visibleCount++;
        }} else {{
            wrap.style.display = 'none';
        }}
    }});

    document.getElementById('emptyState').style.display = visibleCount === 0 ? 'block' : 'none';
}}

function sortCards() {{
    const grid = document.getElementById('grid');
    const wrappers = Array.from(grid.querySelectorAll('.card-tilt-container'));
    const order = document.getElementById('sortSelect').value;

    wrappers.sort((a, b) => {{
        const idxA = parseInt(a.getAttribute('data-idx'));
        const idxB = parseInt(b.getAttribute('data-idx'));
        return order === 'newest' ? idxA - idxB : idxB - idxA;
    }});

    wrappers.forEach(w => grid.appendChild(w));
}}

function toggleExpand(btn) {{
    const p = btn.previousElementSibling;
    p.classList.toggle('expanded');
    btn.textContent = p.classList.contains('expanded') ? 'COLLAPSE ▴' : 'SHOW MORE ▾';
}}

function initExpandButtons() {{
    document.querySelectorAll('.post-text-wrap').forEach(wrap => {{
        const p = wrap.querySelector('.post-text');
        const btn = wrap.querySelector('.expand-btn');
        if (p.scrollHeight > p.clientHeight + 2) {{
            btn.classList.add('visible');
        }}
    }});
}}

window.addEventListener('load', () => {{
    init3DTilt();
    initExpandButtons();
}});

window.addEventListener('resize', () => {{
    document.querySelectorAll('.post-text.expanded').forEach(p => p.classList.remove('expanded'));
    document.querySelectorAll('.expand-btn').forEach(b => {{ b.classList.remove('visible'); b.textContent = 'SHOW MORE ▾'; }});
    initExpandButtons();
}});
</script>

</body>
</html>
"""


# --------------------------------------------------------------------------
# Terminal-Only Mode Renderer
# --------------------------------------------------------------------------

def _setup_console_encoding() -> None:
    """Ensure standard output handles UTF-8 encoding across Windows, Linux, and macOS."""
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        clean = text.encode("ascii", errors="replace").decode("ascii")
        print(clean, **kwargs)


def render_terminal(posts: Iterable[PostLike]) -> None:
    """
    Renders telemetry posts neatly in the terminal with motorsport styling.
    Uses 'rich' if installed; otherwise falls back to a clean ANSI box renderer.
    """
    _setup_console_encoding()
    posts_list = list(posts)
    total_posts = len(posts_list)

    # Try rich rendering first
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console = Console()

        banner_text = Text()
        banner_text.append("\n  FORMULA 1 PITWALL TELEMETRY SYSTEM\n", style="bold red")
        banner_text.append(f"  {total_posts} Transmissions Captured  •  Track Status: GREEN  •  Session: LIVE\n", style="cyan")
        console.print(Panel(banner_text, style="bold red", border_style="red"))

        for i, post in enumerate(posts_list):
            raw_text = str(_get(post, "text", "") or "").strip()
            rel_time, full_time = _format_timestamp(_get(post, "timestamp"))
            url = _get(post, "url", "") or ""
            images = _normalize_images(_get(post, "image_url"))

            card_content = Text()
            card_content.append(f"⏱ Time: {rel_time} ({full_time})\n", style="yellow")
            
            if raw_text:
                card_content.append(f"\n{raw_text}\n", style="white")
            else:
                card_content.append("\n(No text content in transmission)\n", style="dim italic")

            if images:
                card_content.append(f"\n📷 Media Assets ({len(images)}):\n", style="bold green")
                for img in images:
                    card_content.append(f"   • {img}\n", style="cyan")

            if url:
                card_content.append(f"\n🔗 Source Link: {url}\n", style="underline blue")

            panel_title = f"[bold white]TRANSMISSION #{i+1:02d} of {total_posts:02d}[/bold white]"
            console.print(Panel(card_content, title=panel_title, border_style="cyan", padding=(1, 2)))
        
        return
    except ImportError:
        pass

    # ANSI Fallback Renderer (Works everywhere on Windows, Linux, macOS with zero dependencies)
    enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    can_unicode = True
    try:
        "╔═╗┌─┐⏱📷🔗".encode(enc)
    except Exception:
        can_unicode = False

    RED = "\033[1;31m"
    CYAN = "\033[1;36m"
    YELLOW = "\033[1;33m"
    GREEN = "\033[1;32m"
    WHITE = "\033[1;37m"
    GRAY = "\033[0;90m"
    RESET = "\033[0m"

    width = 76
    tl, tr, bl, br, hz, vt = ("╔", "╗", "╚", "╝", "═", "║") if can_unicode else ("+", "+", "+", "+", "=", "|")
    ctl, ctr, cbl, cbr, chz, cvt = ("┌", "┐", "└", "┘", "─", "│") if can_unicode else ("+", "+", "+", "+", "-", "|")
    time_icon = "⏱ " if can_unicode else "TIME: "
    media_icon = "📷 " if can_unicode else "MEDIA: "
    link_icon = "🔗 " if can_unicode else "LINK: "

    _safe_print("\n" + RED + tl + hz * (width - 2) + tr + RESET)
    _safe_print(RED + vt + f"  FORMULA 1 PITWALL TELEMETRY SYSTEM".center(width - 2) + vt + RESET)
    _safe_print(RED + vt + f"  {total_posts} Transmissions Captured  •  Status: GREEN  •  Session: LIVE".center(width - 2) + vt + RESET)
    _safe_print(RED + bl + hz * (width - 2) + br + "\n" + RESET)

    for i, post in enumerate(posts_list):
        raw_text = str(_get(post, "text", "") or "").strip()
        rel_time, full_time = _format_timestamp(_get(post, "timestamp"))
        url = _get(post, "url", "") or ""
        images = _normalize_images(_get(post, "image_url"))

        header = f" TRANSMISSION #{i+1:02d} / {total_posts:02d} "
        _safe_print(CYAN + ctl + chz * 2 + header + chz * max(0, width - len(header) - 4) + ctr + RESET)
        _safe_print(CYAN + cvt + " " + YELLOW + f"{time_icon}{rel_time} ({full_time})" + RESET)

        if raw_text:
            _safe_print(CYAN + cvt + RESET)
            wrapped = textwrap.fill(raw_text, width=width - 6)
            for line in wrapped.split("\n"):
                _safe_print(CYAN + cvt + "  " + WHITE + line + RESET)

        if images:
            _safe_print(CYAN + cvt + RESET)
            _safe_print(CYAN + cvt + "  " + GREEN + f"{media_icon}Media Assets ({len(images)}):" + RESET)
            for img in images:
                _safe_print(CYAN + cvt + "    " + GRAY + f"• {img}" + RESET)

        if url:
            _safe_print(CYAN + cvt + RESET)
            _safe_print(CYAN + cvt + "  " + CYAN + f"{link_icon}{url}" + RESET)

        _safe_print(CYAN + cbl + chz * (width - 2) + cbr + "\n" + RESET)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def render_dashboard(
    posts: Iterable[PostLike],
    output_path: str = "dashboard.html",
    open_browser: bool = True,
) -> str:
    """
    Build an interactive 3D Glassmorphic HTML dashboard from a collection of posts.
    """
    posts_list = list(posts)
    cards_html = "\n".join(_render_card(post, i) for i, post in enumerate(posts_list))

    total_media = sum(len(_normalize_images(_get(p, "image_url"))) for p in posts_list)

    page = _PAGE_TEMPLATE.format(
        count=len(posts_list),
        media_count=total_media,
        generated_at=datetime.now().strftime("%b %d, %Y · %I:%M %p"),
        cards=cards_html if posts_list else "",
    )

    abs_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(page)

    if open_browser:
        webbrowser.open(f"file://{abs_path}")

    return abs_path


# --------------------------------------------------------------------------
# Direct Module Run (Tests both 3D HTML Dashboard and Terminal Renderer)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    sample_posts = [
        {
            "text": "POLE POSITION IN MONZA! 🔴 An astonishing lap at the Temple of Speed sets up a thrilling Grand Prix weekend! #F1 #ItalianGP @ScuderiaFerrari",
            "timestamp": "2m",
            "url": "https://x.com/F1/status/123456789",
            "image_url": [
                "https://picsum.photos/seed/monza1/800/600",
                "https://picsum.photos/seed/monza2/800/600",
            ],
        },
        {
            "text": "Full telemetry breakdown from Sector 2: Apex speeds are 12 km/h higher with the new low-drag rear wing configuration. Pit strategy will be crucial tomorrow under tire degradation.",
            "timestamp": "14m",
            "url": "https://x.com/F1/status/123456790",
            "image_url": [
                "https://picsum.photos/seed/telemetry/900/500",
                "https://picsum.photos/seed/paddock/800/600",
                "https://picsum.photos/seed/tires/800/600",
                "https://picsum.photos/seed/pitstop/800/600",
            ],
        },
        {
            "text": "Weather radar indicates a 40% chance of rain before lights out. Track temperature currently sitting at 38°C.",
            "timestamp": "1h",
            "url": "https://x.com/F1/status/123456791",
            "image_url": [],
        },
    ]

    print("[Testing Terminal Renderer]")
    render_terminal(sample_posts)

    out = render_dashboard(sample_posts, output_path="dashboard.html", open_browser=False)
    print(f"\n[Sample 3D Glassmorphic dashboard written to {out}]")