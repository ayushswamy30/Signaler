import sys; sys.path.insert(0, '.')
from _lib import T, icon, avatar, page
from _shell import CONVS, conv_row, sidebar, shell

W, H = 1280, 800


def write(name, body, t=T):
    open(name, "w").write(page(body, t, W, H))


def nav_item(t, ic, label, active=False, placeholder=False):
    bg = t["active"] if active else "transparent"
    col = t["accent"] if active else t["text"]
    tag = ""
    if placeholder:
        tag = (f'<span class="t11 w6" style="padding:2px 7px;border-radius:999px;'
               f'background:{t["hover"]};color:{t["text3"]};">Placeholder</span>')
    return f"""<div class="r" style="gap:11px;padding:10px 12px;border-radius:9px;background:{bg};">
  <span style="display:flex;color:{col};">{icon(ic,19)}</span>
  <span class="t14 {'w6' if active else 'w5'} g" style="color:{col};">{label}</span>{tag}
  <span style="display:flex;color:{t['text3']};">{icon('chev',15,sw=2)}</span>
</div>"""


def row(t, label, sub=None, trailing=""):
    s = f'<span class="t12 dim">{sub}</span>' if sub else ""
    return f"""<div class="r" style="gap:14px;padding:14px 0;border-bottom:1px solid {t['subtle']};">
  <div class="c g" style="gap:2px;"><span class="t14 w5">{label}</span>{s}</div>{trailing}
</div>"""


def toggle(t, on=True):
    bg = t["accent"] if on else t["strong"]
    x = "calc(100% - 18px)" if on else "2px"
    return (f'<span style="position:relative;width:38px;height:22px;border-radius:999px;'
            f'background:{bg};flex:0 0 auto;"><span style="position:absolute;top:2px;left:{x};'
            f'width:18px;height:18px;border-radius:999px;background:#fff;"></span></span>')


def theme_card(t, name, selected, dark=False):
    bg = "#0B0F14" if dark else "#F7F8FA"
    sur = "#141A21" if dark else "#FFFFFF"
    bar = "#1F262F" if dark else "#E1E5EB"
    bub = "#1E55C9" if dark else "#2C6BED"
    ring = f"2px solid {t['accent']}" if selected else f"1px solid {t['border']}"
    mark = (f'<span style="width:18px;height:18px;border-radius:999px;background:{t["accent"]};'
            f'display:flex;align-items:center;justify-content:center;">'
            f'{icon("check",11,color="#fff",sw=3)}</span>' if selected else "")
    return f"""<div class="c" style="gap:8px;">
  <div style="width:150px;height:96px;border-radius:10px;border:{ring};background:{bg};
    padding:8px;display:flex;gap:6px;overflow:hidden;">
    <div style="width:40px;border-radius:5px;background:{sur};"></div>
    <div class="c g" style="gap:5px;">
      <div style="height:9px;border-radius:3px;background:{sur};"></div>
      <div style="height:20px;width:70%;border-radius:6px;background:{bar};"></div>
      <div style="height:20px;width:80%;border-radius:6px;background:{bub};align-self:flex-end;"></div>
    </div>
  </div>
  <div class="r" style="gap:7px;"><span class="t13 w5">{name}</span>{mark}</div>
</div>"""


nav = "".join([
    nav_item(T, "settings", "Profile", active=True),
    nav_item(T, "lock", "Privacy", placeholder=True),
    nav_item(T, "bell", "Notifications", placeholder=True),
    nav_item(T, "phone", "Calls", placeholder=True),
    nav_item(T, "devices", "Linked devices", placeholder=True),
    nav_item(T, "palette", "Appearance"),
])

placeholder_note = f"""<div class="r" style="gap:9px;padding:10px 12px;margin-top:10px;
     border-radius:8px;background:{T['hover']};">
  <span style="display:flex;color:{T['text3']};margin-top:1px;">{icon('info',15,sw=1.8)}</span>
  <span class="t12 dim">Sections marked <span class="w6">Placeholder</span> are out of scope for
    this build. They are shown so the navigation is complete.</span>
</div>"""

settings_body = f"""<div class="c" style="width:300px;flex:0 0 300px;height:100%;
     background:{T['surface']};border-right:1px solid {T['border']};padding:14px 10px;">
  <span class="t11 w6 dim2" style="padding:6px 12px 10px;letter-spacing:.4px;">SETTINGS</span>
  {nav}{placeholder_note}
</div>
<div class="c g" style="height:100%;overflow:hidden;background:{T['canvas']};">
  <div class="r" style="gap:12px;padding:16px 28px;border-bottom:1px solid {T['border']};
    background:{T['surface']};">
    <span class="t20 w6 g">Profile</span>
    <button style="all:unset;cursor:pointer;height:36px;padding:0 15px;border-radius:8px;
      background:{T['accent']};color:#fff;font-size:13px;font-weight:500;">Save changes</button>
  </div>
  <div class="c" style="gap:2px;padding:26px 28px;max-width:620px;">
    <div class="r" style="gap:18px;padding-bottom:20px;border-bottom:1px solid {T['subtle']};">
      <div style="position:relative;">{avatar("AS", 76, T)}
        <span style="position:absolute;right:-2px;bottom:-2px;width:28px;height:28px;
          border-radius:999px;background:{T['surface']};border:1px solid {T['border']};
          color:{T['text2']};display:flex;align-items:center;justify-content:center;">
          {icon('camera',15,sw=1.7)}</span></div>
      <div class="c g" style="gap:4px;">
        <span class="t16 w6">Ayush Swamy</span>
        <span class="t13 dim">@ayush · joined March 2026</span>
        <span class="t12 dim2">Your photo is visible to people you chat with.</span>
      </div>
    </div>
    {row(T, "Display name", "Shown to everyone you message.",
         f'<span class="t14 dim">Ayush Swamy</span>')}
    {row(T, "Username", "Permanent. Others find you with this.",
         f'<span class="t14 dim">@ayush</span>')}
    {row(T, "Phone number", "Hidden from everyone except your contacts.",
         f'<span class="t14 dim">+91 98••• ••210</span>')}
    {row(T, "Read receipts", "Let people see when you've read their messages.", toggle(T, True))}
    {row(T, "Show when online", "Others see a green dot and your last-seen time.", toggle(T, True))}
    <div class="c" style="gap:12px;padding:20px 0 0;">
      <span class="t14 w5">Appearance</span>
      <div class="r" style="gap:16px;">
        {theme_card(T, "Light", True)}{theme_card(T, "Dark", False, dark=True)}
        {theme_card(T, "System", False)}
      </div>
    </div>
  </div>
</div>"""
write("Settings.dc.html", f"""<div class="r" style="width:{W}px;height:{H}px;
  background:{T['canvas']};overflow:hidden;">{settings_body}</div>""")

# ---------- Profile (someone else's, from a chat) ----------
def stat(t, label, value):
    return (f'<div class="c" style="gap:2px;"><span class="t11 w6 dim2" '
            f'style="letter-spacing:.4px;">{label}</span>'
            f'<span class="t14 w5">{value}</span></div>')

prof = f"""<div class="c" style="width:400px;flex:0 0 400px;height:100%;background:{T['surface']};
     border-left:1px solid {T['border']};overflow:hidden;">
  <div class="r" style="gap:12px;padding:14px 18px;border-bottom:1px solid {T['subtle']};">
    <span class="t16 w6 g">Contact info</span>
    <button style="all:unset;cursor:pointer;color:{T['text3']};display:flex;">{icon('close',18)}</button>
  </div>
  <div class="c" style="align-items:center;gap:12px;padding:26px 18px 20px;
    border-bottom:1px solid {T['subtle']};">
    {avatar("PN", 96, T, bg=T['hover'], fg=T['text2'])}
    <div class="c" style="align-items:center;gap:4px;">
      <span class="t24 w6">Priya Nair</span>
      <span class="t13 dim">@priya</span>
      <div class="r" style="gap:6px;margin-top:2px;">
        <span style="width:7px;height:7px;border-radius:999px;background:{T['online']};"></span>
        <span class="t12" style="color:{T['online']};">Online</span>
      </div>
    </div>
    <div class="r" style="gap:8px;">
      <button style="all:unset;cursor:pointer;height:36px;padding:0 15px;border-radius:8px;
        background:{T['accent']};color:#fff;font-size:13px;font-weight:500;">Message</button>
      <button style="all:unset;cursor:pointer;height:36px;padding:0 15px;border-radius:8px;
        border:1px solid {T['border']};font-size:13px;font-weight:500;">Call</button>
    </div>
  </div>
  <div class="c" style="gap:16px;padding:18px;">
    <div class="r" style="gap:36px;">{stat(T,'PHONE','+91 98••• ••118')}
      {stat(T,'CONTACT SINCE','Feb 2026')}</div>
    <div class="c" style="gap:2px;">
      {row(T, "Mute notifications", None, toggle(T, False))}
      {row(T, "Shared groups", "Design Guild",
           f'<span style="display:flex;color:{T["text3"]};">{icon("chev",15,sw=2)}</span>')}
    </div>
    <div class="r" style="gap:11px;padding:11px 0;color:{T['danger']};">
      <span style="display:flex;">{icon('close',18)}</span>
      <span class="t14 w5">Block contact</span>
    </div>
  </div>
</div>"""
from _shell import bubble, date_sep, chat_header, composer
pthread = "".join([date_sep(T, "Today"),
                   bubble(T, "See you at 7 then", False, "09:24")])
ppanel = (chat_header(T, "PN", "Priya Nair", "Online")
          + f'<div class="c g" style="gap:6px;padding:20px 24px 12px;justify-content:flex-end;">'
            f'{pthread}</div>' + composer(T))
write("Profile.dc.html", f"""<div class="r" style="width:{W}px;height:{H}px;
  background:{T['canvas']};overflow:hidden;">{sidebar(T, active_index=0)}
  <div class="c g" style="min-width:0;height:100%;">{ppanel}</div>{prof}</div>""")

print("Settings Profile")
