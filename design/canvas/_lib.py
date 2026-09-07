"""Shared visual language for the Signaler design canvas.

Values are lifted verbatim from design/design-tokens.md — the governing
design system — not rounded or re-invented.
"""

T = {
    "canvas": "#F7F8FA", "surface": "#FFFFFF", "raised": "#FFFFFF",
    "hover": "#EEF0F4", "active": "#EAF2FF",
    "text": "#141A21", "text2": "#6B7683", "text3": "#9AA4B2", "onAccent": "#FFFFFF",
    "subtle": "#EEF0F4", "border": "#E1E5EB", "strong": "#C9D0DA",
    "accent": "#2C6BED", "accentHover": "#1E55C9", "accentSubtle": "#EAF2FF",
    "outBg": "#2C6BED", "outText": "#FFFFFF", "inBg": "#EEF0F4", "inText": "#141A21",
    "quoteBg": "#E1E5EB", "quoteBorder": "#2C6BED",
    "online": "#1E9E62", "danger": "#D93A3A", "warning": "#D98B0A",
}

D = {
    "canvas": "#0B0F14", "surface": "#141A21", "raised": "#182029",
    "hover": "#182029", "active": "#1F262F",
    "text": "#F7F8FA", "text2": "#9AA4B2", "text3": "#6B7683", "onAccent": "#FFFFFF",
    "subtle": "#182029", "border": "#1F262F", "strong": "#333C49",
    "accent": "#4B8BFF", "accentHover": "#7BAAFF", "accentSubtle": "#0D2450",
    "outBg": "#1E55C9", "outText": "#FFFFFF", "inBg": "#1F262F", "inText": "#F7F8FA",
    "quoteBg": "#333C49", "quoteBorder": "#7BAAFF",
    "online": "#3DBE84", "danger": "#E76A6A", "warning": "#EBAA3A",
}


def css(t):
    return f"""
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background: {t['canvas']}; color: {t['text']};
      font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: {t['accent']}; text-decoration: none; }}
    a:hover {{ color: {t['accentHover']}; }}
    .r {{ display: flex; align-items: center; }}
    .c {{ display: flex; flex-direction: column; }}
    .g {{ flex-grow: 1; }}
    .t11 {{ font-size: 11px; line-height: 16px; }}
    .t12 {{ font-size: 12px; line-height: 16px; }}
    .t13 {{ font-size: 13px; line-height: 18px; }}
    .t14 {{ font-size: 14px; line-height: 20px; }}
    .t16 {{ font-size: 16px; line-height: 24px; }}
    .t20 {{ font-size: 20px; line-height: 28px; }}
    .t24 {{ font-size: 24px; line-height: 32px; }}
    .t32 {{ font-size: 32px; line-height: 40px; }}
    .w4 {{ font-weight: 400; }} .w5 {{ font-weight: 500; }}
    .w6 {{ font-weight: 600; }} .w7 {{ font-weight: 700; }}
    .dim {{ color: {t['text2']}; }} .dim2 {{ color: {t['text3']}; }}
    .ell {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    """


def icon(name, size=20, color="currentColor", sw=1.6):
    p = {
        "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.2-3.2"/>',
        "edit": '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3z"/>',
        "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M22 12h-3M5 12H2M18.4 5.6l-2 2M7.6 16.4l-2 2M18.4 18.4l-2-2M7.6 7.6l-2-2"/>',
        "more": '<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
        "phone": '<path d="M6 3h4l2 5-2.5 1.5a11 11 0 0 0 5 5L16 12l5 2v4a2 2 0 0 1-2.2 2A16 16 0 0 1 4 5.2 2 2 0 0 1 6 3z"/>',
        "video": '<rect x="3" y="6" width="12" height="12" rx="2.5"/><path d="M15 10.5l6-3.5v10l-6-3.5z"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.6v.1"/>',
        "send": '<path d="M4 12l16-8-6 8 6 8-16-8z"/>',
        "smile": '<circle cx="12" cy="12" r="9"/><path d="M8.5 14.5a4.5 4.5 0 0 0 7 0M9 9.5v.1M15 9.5v.1"/>',
        "clip": '<path d="M17 8l-7.6 7.6a2.5 2.5 0 0 0 3.5 3.5L21 11a4.5 4.5 0 0 0-6.4-6.4L6 13.2"/>',
        "back": '<path d="M15 5l-7 7 7 7"/>',
        "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
        "checks": '<path d="M2 12.5l4 4L14 8"/><path d="M10 15.5l1.5 1.5L21 7"/>',
        "close": '<path d="M6 6l12 12M18 6L6 18"/>',
        "plus": '<path d="M12 5v14M5 12h14"/>',
        "users": '<circle cx="9" cy="9" r="3.2"/><path d="M3 19a6 6 0 0 1 12 0"/><path d="M16.5 7.2a3 3 0 0 1 0 5.6M17 19a6 6 0 0 0-2-4.3"/>',
        "bell": '<path d="M18 9a6 6 0 0 0-12 0c0 5-2 6-2 6h16s-2-1-2-6"/><path d="M13.7 20a2 2 0 0 1-3.4 0"/>',
        "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2.2"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/>',
        "palette": '<path d="M12 3a9 9 0 1 0 0 18c1.4 0 1.8-1 1.2-1.8-.7-1 .1-2.2 1.4-2.2H17a4 4 0 0 0 4-4c0-5-4-10-9-10z"/><circle cx="8" cy="11" r="1"/><circle cx="12" cy="8" r="1"/><circle cx="16" cy="11" r="1"/>',
        "devices": '<rect x="3" y="5" width="12" height="9" rx="1.8"/><path d="M6 18h6"/><rect x="16" y="9" width="5" height="10" rx="1.5"/>',
        "chev": '<path d="M9 5l7 7-7 7"/>',
        "camera": '<path d="M4 8h3l1.5-2h7L17 8h3a1.6 1.6 0 0 1 1.6 1.6v8A1.6 1.6 0 0 1 20 19H4a1.6 1.6 0 0 1-1.6-1.6v-8A1.6 1.6 0 0 1 4 8z"/><circle cx="12" cy="13" r="3.4"/>',
        "reply": '<path d="M9 7L4 12l5 5"/><path d="M4 12h9a6 6 0 0 1 6 6v1"/>',
        "warn": '<path d="M12 4.5L21 19H3z"/><path d="M12 10v4M12 16.6v.1"/>',
        "wifi": '<path d="M2.5 9.5a15 15 0 0 1 19 0M6 13a10 10 0 0 1 12 0M9.5 16.5a5 5 0 0 1 5 0"/><path d="M12 20v.1"/>',
        "mute": '<path d="M18 9a6 6 0 0 0-9.3-5"/><path d="M6 9c0 5-2 6-2 6h11"/><path d="M13.7 20a2 2 0 0 1-3.4 0"/><path d="M3.5 3.5l17 17"/>',
        "arrowdown": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    }[name]
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{p}</svg>')


def page(body, t, w, h, extra=""):
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>{css(t)}{extra}</style>
</helmet>
{body}
</x-dc>
</body>
</html>
"""


def avatar(initials, size, t, bg=None, fg=None, online=False, ring=None):
    bg = bg or t["accentSubtle"]
    fg = fg or t["accent"]
    fs = {24: 10, 28: 11, 32: 12, 40: 14, 48: 16, 56: 19, 72: 24, 96: 32}.get(size, 14)
    dot = max(8, round(size * 0.28))
    r = f"border:2px solid {ring};" if ring else ""
    d = ""
    if online:
        d = (f'<span style="position:absolute;right:-1px;bottom:-1px;width:{dot}px;height:{dot}px;'
             f'border-radius:999px;background:{t["online"]};border:2px solid {t["surface"]};"></span>')
    return (f'<span style="position:relative;flex:0 0 auto;width:{size}px;height:{size}px;'
            f'border-radius:999px;background:{bg};color:{fg};{r}display:flex;align-items:center;'
            f'justify-content:center;font-weight:600;font-size:{fs}px;letter-spacing:.2px;">'
            f'{initials}{d}</span>')
