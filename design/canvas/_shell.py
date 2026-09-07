from _lib import T, icon, avatar

CONVS = [
    ("PN", "Priya Nair",   "See you at 7 then",            "09:24", 0, False, False),
    ("DG", "Design Guild", "Maya: pushed the new tokens",  "08:55", 3, False, True),
    ("RM", "Rohan Mehta",  "Thanks, that helps",           "Yesterday", 0, True, False),
    ("AR", "Aditi Rao",    "Can you check the draft?",     "Yesterday", 1, False, False),
    ("FM", "Family",       "Dad: Photo",                   "Mon", 0, False, True),
    ("KS", "Karan Singh",  "Sounds good to me",            "Mon", 0, False, False),
    ("NV", "Neha Verma",   "Shared a link",                "Sun", 0, False, False),
]


def conv_row(t, c, active=False, unread_override=None):
    ini, name, prev, time, unread, muted, group = c
    if unread_override is not None:
        unread = unread_override
    bg = t["active"] if active else "transparent"
    name_w = "600" if unread else "500"
    prev_col = t["text"] if unread else t["text2"]
    prev_w = "500" if unread else "400"
    badge = ""
    if unread:
        badge = (f'<span style="min-width:20px;height:20px;padding:0 6px;border-radius:999px;'
                 f'background:{t["accent"]};color:#fff;font-size:11px;font-weight:600;display:flex;'
                 f'align-items:center;justify-content:center;">{unread}</span>')
    mute_icon = (f'<span style="color:{t["text3"]};display:flex;">{icon("mute",14,sw=1.7)}</span>'
                 if muted else "")
    return f"""<div class="r" style="gap:12px;padding:10px 12px;border-radius:10px;background:{bg};">
  {avatar(ini, 44, t, bg=t["hover"] if not active else "#FFFFFF", fg=t["text2"])}
  <div class="c g" style="gap:2px;min-width:0;">
    <div class="r" style="gap:6px;">
      <span class="t14 ell" style="font-weight:{name_w};">{name}</span>
      {mute_icon}
      <span class="g"></span>
      <span class="t11" style="color:{t['text3']};flex:0 0 auto;">{time}</span>
    </div>
    <div class="r" style="gap:8px;">
      <span class="t13 ell g" style="color:{prev_col};font-weight:{prev_w};">{prev}</span>
      {badge}
    </div>
  </div>
</div>"""


def sidebar(t, active_index=0, search_value=None, results_mode=False, conv_html=None):
    rows = conv_html
    if rows is None:
        rows = "\n".join(conv_row(t, c, active=(i == active_index))
                         for i, c in enumerate(CONVS))
    sv = search_value or "Search"
    sc = t["text"] if search_value else t["text3"]
    caret = (f'<span style="width:1.5px;height:16px;background:{t["accent"]};"></span>'
             if search_value else "")
    return f"""<div class="c" style="width:340px;flex:0 0 340px;background:{t['surface']};
     border-right:1px solid {t['border']};height:100%;">
  <div class="r" style="gap:12px;padding:16px;border-bottom:1px solid {t['subtle']};">
    {avatar("AS", 36, t, online=True)}
    <div class="c g" style="min-width:0;">
      <span class="t14 w6 ell">Ayush Swamy</span>
      <span class="t11" style="color:{t['text3']};">@ayush</span>
    </div>
    <button style="all:unset;cursor:pointer;width:32px;height:32px;border-radius:8px;
      display:flex;align-items:center;justify-content:center;color:{t['text2']};">{icon('edit',20)}</button>
    <button style="all:unset;cursor:pointer;width:32px;height:32px;border-radius:8px;
      display:flex;align-items:center;justify-content:center;color:{t['text2']};">{icon('settings',20)}</button>
  </div>
  <div style="padding:12px 16px;">
    <div class="r" style="gap:8px;height:36px;padding:0 12px;border-radius:8px;
      background:{t['hover']};border:1px solid {'%s' % (t['accent'] if search_value else 'transparent')};">
      <span style="color:{t['text3']};display:flex;">{icon('search',18)}</span>
      <span class="t14 g" style="color:{sc};">{sv}</span>
      {caret}
    </div>
  </div>
  <div class="c g" style="gap:2px;padding:0 8px 8px;overflow:hidden;">{rows}</div>
</div>"""


def bubble(t, text, out, time, status=None, first=True, last=True, sender=None,
           quote=None, edited=False):
    bg = t["outBg"] if out else t["inBg"]
    fg = t["outText"] if out else t["inText"]
    near = "4px"
    far = "14px"
    if out:
        radius = f"{far} {near if not first else far} {near if not last else far} {far}"
        if first and last:
            radius = f"{far} {far} {near} {far}"
    else:
        radius = f"{near if not first else far} {far} {far} {near if not last else far}"
        if first and last:
            radius = f"{far} {far} {far} {near}"
    meta_col = "rgba(255,255,255,.75)" if out else t["text3"]
    tick = ""
    if status == "sent":
        tick = f'<span style="display:flex;color:{meta_col};">{icon("check",13,sw=2)}</span>'
    elif status == "delivered":
        tick = f'<span style="display:flex;color:{meta_col};">{icon("checks",15,sw=2)}</span>'
    elif status == "read":
        tick = f'<span style="display:flex;color:#FFFFFF;">{icon("checks",15,sw=2.4)}</span>'
    sender_html = ""
    if sender:
        sender_html = (f'<div class="t12 w6" style="color:{t["accent"]};margin-bottom:2px;">'
                       f'{sender}</div>')
    quote_html = ""
    if quote:
        qn, qt = quote
        qbg = "rgba(255,255,255,.16)" if out else t["quoteBg"]
        qbc = "#FFFFFF" if out else t["quoteBorder"]
        qname = "rgba(255,255,255,.95)" if out else t["accent"]
        qtext = "rgba(255,255,255,.8)" if out else t["text2"]
        quote_html = f"""<div style="display:flex;gap:8px;padding:6px 10px;margin-bottom:6px;
     border-radius:6px;background:{qbg};border-left:3px solid {qbc};">
  <div class="c" style="min-width:0;gap:1px;">
    <span class="t12 w6" style="color:{qname};">{qn}</span>
    <span class="t12 ell" style="color:{qtext};max-width:240px;">{qt}</span>
  </div>
</div>"""
    ed = f'<span class="t11" style="color:{meta_col};">edited</span>' if edited else ""
    return f"""<div style="display:flex;justify-content:{'flex-end' if out else 'flex-start'};">
  <div style="max-width:460px;padding:8px 12px;border-radius:{radius};background:{bg};color:{fg};">
    {sender_html}{quote_html}
    <div class="t14" style="white-space:pre-wrap;">{text}</div>
    <div class="r" style="gap:5px;justify-content:flex-end;margin-top:2px;">
      {ed}<span class="t11" style="color:{meta_col};">{time}</span>{tick}
    </div>
  </div>
</div>"""


def date_sep(t, label):
    return f"""<div class="r" style="gap:12px;padding:4px 0;">
  <span class="g" style="height:1px;background:{t['subtle']};"></span>
  <span class="t11 w5" style="color:{t['text3']};">{label}</span>
  <span class="g" style="height:1px;background:{t['subtle']};"></span>
</div>"""


def unread_sep(t, n=3):
    return f"""<div class="r" style="gap:12px;padding:4px 0;">
  <span class="g" style="height:1px;background:{t['accent']};opacity:.35;"></span>
  <span class="t11 w6" style="color:{t['accent']};">{n} unread messages</span>
  <span class="g" style="height:1px;background:{t['accent']};opacity:.35;"></span>
</div>"""


def chat_header(t, ini, name, sub, sub_color=None, group=False, members=None):
    sub_color = sub_color or t["text2"]
    dot = ""
    if sub == "Online":
        dot = (f'<span style="width:7px;height:7px;border-radius:999px;'
               f'background:{t["online"]};flex:0 0 auto;"></span>')
    return f"""<div class="r" style="gap:12px;padding:12px 20px;border-bottom:1px solid {t['border']};
     background:{t['surface']};">
  {avatar(ini, 38, t, bg=t["hover"], fg=t["text2"])}
  <div class="c g" style="min-width:0;gap:1px;">
    <span class="t16 w6 ell">{name}</span>
    <span class="r t12" style="gap:6px;color:{sub_color};">{dot}{sub}</span>
  </div>
  <div class="r" style="gap:4px;color:{t['text2']};">
    <button style="all:unset;cursor:pointer;width:34px;height:34px;border-radius:8px;display:flex;
      align-items:center;justify-content:center;">{icon('phone',19)}</button>
    <button style="all:unset;cursor:pointer;width:34px;height:34px;border-radius:8px;display:flex;
      align-items:center;justify-content:center;">{icon('video',19)}</button>
    <button style="all:unset;cursor:pointer;width:34px;height:34px;border-radius:8px;display:flex;
      align-items:center;justify-content:center;">{icon('info',19)}</button>
  </div>
</div>"""


def composer(t, value=None, reply=None, disabled=False, sending=False, error=None):
    placeholder = value or "Message"
    col = t["text"] if value else t["text3"]
    send_bg = t["accent"] if value else t["hover"]
    send_fg = "#FFFFFF" if value else t["text3"]
    caret = (f'<span style="width:1.5px;height:18px;background:{t["accent"]};"></span>'
             if value and not sending else "")
    reply_html = ""
    if reply:
        rn, rt = reply
        reply_html = f"""<div class="r" style="gap:10px;padding:8px 12px;margin-bottom:8px;
     border-radius:8px;background:{t['hover']};border-left:3px solid {t['accent']};">
  <div class="c g" style="min-width:0;gap:1px;">
    <span class="t12 w6" style="color:{t['accent']};">Replying to {rn}</span>
    <span class="t12 ell" style="color:{t['text2']};">{rt}</span>
  </div>
  <button style="all:unset;cursor:pointer;color:{t['text3']};display:flex;">{icon('close',16)}</button>
</div>"""
    err_html = ""
    if error:
        err_html = f"""<div class="r" style="gap:8px;margin-bottom:8px;padding:8px 12px;
     border-radius:8px;background:#FBE3E3;color:#B32B2B;">
  <span style="display:flex;">{icon('warn',16,sw=1.8)}</span>
  <span class="t12 w5 g">{error}</span>
  <button style="all:unset;cursor:pointer;font-size:12px;font-weight:600;
    text-decoration:underline;">Retry</button>
</div>"""
    op = "opacity:.6;" if disabled else ""
    spinner = ""
    if sending:
        spinner = (f'<span style="width:14px;height:14px;border-radius:999px;'
                   f'border:2px solid {t["text3"]};border-top-color:transparent;"></span>')
    return f"""<div style="padding:12px 20px 16px;background:{t['surface']};
     border-top:1px solid {t['border']};{op}">
  {err_html}{reply_html}
  <div class="r" style="gap:10px;">
    <div class="r g" style="gap:10px;min-height:40px;padding:9px 14px;border-radius:20px;
      background:{t['hover']};border:1px solid {t['border']};">
      <span class="t14 g" style="color:{col};">{placeholder}</span>{caret}{spinner}
      <span style="color:{t['text3']};display:flex;">{icon('clip',19)}</span>
      <span style="color:{t['text3']};display:flex;">{icon('smile',19)}</span>
    </div>
    <button style="all:unset;cursor:pointer;width:40px;height:40px;border-radius:999px;
      background:{send_bg};color:{send_fg};display:flex;align-items:center;justify-content:center;
      flex:0 0 auto;">{icon('send',19,sw=1.8)}</button>
  </div>
</div>"""


def typing_row(t, who="Priya"):
    d = ('<span style="width:6px;height:6px;border-radius:999px;background:%s;"></span>'
         % t["text3"])
    return f"""<div class="r" style="gap:10px;padding:2px 0 0;">
  {avatar("PN", 26, t, bg=t["hover"], fg=t["text2"])}
  <div class="r" style="gap:5px;padding:9px 13px;border-radius:14px 14px 14px 4px;
    background:{t['inBg']};">{d}{d}{d}</div>
</div>"""


def shell(t, sidebar_html, panel_html, w=1280, h=800):
    return f"""<div class="r" style="width:{w}px;height:{h}px;background:{t['canvas']};
     overflow:hidden;">
  {sidebar_html}
  <div class="c g" style="min-width:0;height:100%;background:{t['canvas']};">{panel_html}</div>
</div>"""
