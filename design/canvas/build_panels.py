import sys; sys.path.insert(0, '.')
from _lib import T, icon, avatar, page
from _shell import CONVS, conv_row, sidebar, chat_header, composer, bubble, date_sep, shell

W, H = 1280, 800


def write(name, body, t=T):
    open(name, "w").write(page(body, t, W, H))


def base_shell(t=T, active=0):
    thread = "".join([
        date_sep(t, "Today"),
        bubble(t, "Are we still on for dinner tonight?", False, "09:02"),
        bubble(t, "Yes — 7pm at the usual place.", True, "09:03", status="read"),
        bubble(t, "See you at 7 then", False, "09:24"),
    ])
    panel = (chat_header(t, "PN", "Priya Nair", "Online")
             + f'<div class="c g" style="gap:6px;padding:20px 24px 12px;justify-content:flex-end;">'
               f'{thread}</div>' + composer(t))
    return sidebar(t, active_index=active), panel


def overlay(inner, t=T, active=0):
    sb, panel = base_shell(t, active)
    return f"""<div style="position:relative;width:{W}px;height:{H}px;overflow:hidden;">
  {shell(t, sb, panel)}
  <div style="position:absolute;inset:0;background:rgba(11,15,20,.42);
    display:flex;align-items:center;justify-content:center;">{inner}</div>
</div>"""


def modal(t, title, body, footer=None, width=460, subtitle=None):
    sub = (f'<span class="t13 dim">{subtitle}</span>') if subtitle else ""
    foot = (f'<div class="r" style="gap:10px;justify-content:flex-end;padding:14px 20px;'
            f'border-top:1px solid {t["subtle"]};">{footer}</div>') if footer else ""
    return f"""<div class="c" style="width:{width}px;border-radius:14px;background:{t['surface']};
     box-shadow:0 20px 48px rgba(0,0,0,.22);overflow:hidden;">
  <div class="r" style="gap:12px;padding:18px 20px 14px;">
    <div class="c g" style="gap:2px;"><span class="t16 w6">{title}</span>{sub}</div>
    <button style="all:unset;cursor:pointer;color:{t['text3']};display:flex;">{icon('close',18)}</button>
  </div>
  {body}{foot}
</div>"""


def button(t, label, kind="primary", disabled=False):
    bg = {"primary": t["accent"], "secondary": t["surface"], "ghost": "transparent"}[kind]
    fg = {"primary": "#fff", "secondary": t["text"], "ghost": t["text2"]}[kind]
    bd = f"border:1px solid {t['border']};" if kind == "secondary" else "border:none;"
    op = "opacity:.55;" if disabled else ""
    return (f'<button style="all:unset;cursor:pointer;height:38px;padding:0 16px;border-radius:8px;'
            f'background:{bg};color:{fg};{bd}{op}font-size:13px;font-weight:500;display:flex;'
            f'align-items:center;justify-content:center;">{label}</button>')


def search_field(t, value, placeholder="Search by name or username"):
    return f"""<div class="r" style="gap:9px;height:40px;padding:0 13px;border-radius:8px;
     background:{t['hover']};border:1px solid {t['accent']};">
  <span style="color:{t['text3']};display:flex;">{icon('search',18)}</span>
  <span class="t14 g" style="color:{t['text'] if value else t['text3']};">{value or placeholder}</span>
  <span style="width:1.5px;height:18px;background:{t['accent']};"></span>
</div>"""


def person(t, ini, name, handle, trailing=""):
    return f"""<div class="r" style="gap:12px;padding:9px 12px;border-radius:9px;">
  {avatar(ini, 38, t, bg=t['hover'], fg=t['text2'])}
  <div class="c g" style="gap:1px;min-width:0;">
    <span class="t14 w5 ell">{name}</span>
    <span class="t12 dim2">@{handle}</span>
  </div>{trailing}
</div>"""


def chip(t, label, tone="neutral"):
    bg = {"neutral": t["hover"], "ok": "#D8F3E5", "accent": t["accentSubtle"]}[tone]
    fg = {"neutral": t["text2"], "ok": "#17804F", "accent": t["accent"]}[tone]
    return (f'<span class="t11 w6" style="padding:4px 9px;border-radius:999px;background:{bg};'
            f'color:{fg};white-space:nowrap;">{label}</span>')


# ---------- New message ----------
results = "".join([
    person(T, "MI", "Maya Iyer", "maya", chip(T, "Already a contact", "ok")),
    person(T, "DS", "Dev Sharma", "devsharma",
           button(T, "Add", kind="secondary")),
    person(T, "TK", "Tara Kapoor", "tarak", button(T, "Add", kind="secondary")),
])
nm_body = f"""<div class="c" style="gap:14px;padding:0 20px 6px;">
  {search_field(T, "ma")}
  <div class="c" style="gap:2px;">
    <span class="t11 w6 dim2" style="padding:0 12px 4px;letter-spacing:.4px;">RESULTS</span>
    {results}
  </div>
  <div class="r" style="gap:9px;padding:10px 12px;border-radius:9px;background:{T['hover']};">
    <span style="width:14px;height:14px;border-radius:999px;border:2px solid {T['text3']};
      border-top-color:transparent;"></span>
    <span class="t12 dim">Searching the directory…</span>
  </div>
</div>"""
write("NewMessage.dc.html", overlay(modal(
    T, "New message", nm_body,
    subtitle="Find someone by username, then start a conversation.",
    footer=button(T, "Cancel", "secondary") + button(T, "Start chat", disabled=True))))

# ---------- Contact search (no results + sidebar search) ----------
no_results = f"""<div class="c" style="align-items:center;gap:10px;padding:34px 20px 26px;">
  <div style="width:56px;height:56px;border-radius:999px;background:{T['hover']};
    color:{T['text3']};display:flex;align-items:center;justify-content:center;">
    {icon('search',24,sw=1.5)}</div>
  <div class="c" style="gap:4px;align-items:center;text-align:center;">
    <span class="t14 w6">No one found for “zephyr”</span>
    <span class="t13 dim" style="max-width:280px;">Usernames are exact. Check the spelling,
      or invite them to Signaler.</span>
  </div>
  {button(T, "Invite by link", "secondary")}
</div>"""
cs_body = f"""<div class="c" style="gap:14px;padding:0 20px 6px;">
  {search_field(T, "zephyr")}{no_results}
</div>"""
sb_search = sidebar(T, search_value="pri", conv_html="".join([
    f'<span class="t11 w6 dim2" style="padding:8px 12px 6px;letter-spacing:.4px;">CONVERSATIONS</span>',
    conv_row(T, CONVS[0], active=True),
    f'<span class="t11 w6 dim2" style="padding:12px 12px 6px;letter-spacing:.4px;">CONTACTS</span>',
    conv_row(T, ("PS", "Priyanka Shah", "@priyanka", "", 0, False, False)),
    conv_row(T, ("PJ", "Pritam Joshi", "@pritamj", "", 0, False, False)),
]))
_, panel = base_shell()
write("ContactSearch.dc.html", f"""<div style="position:relative;width:{W}px;height:{H}px;
  overflow:hidden;">{shell(T, sb_search, panel)}
  <div style="position:absolute;inset:0;background:rgba(11,15,20,.42);display:flex;
    align-items:center;justify-content:center;">{modal(T, "Find people", cs_body,
    subtitle="Search across your contacts and the directory.",
    footer=button(T, "Close", "secondary"))}</div></div>""")

# ---------- Create group (steps 1 + 2 side by side) ----------
def stepper(t, active):
    out = []
    for i, name in enumerate(["Members", "Details", "Confirm"], start=1):
        on = i == active
        done = i < active
        bg = t["accent"] if on else (("#D8F3E5") if done else t["hover"])
        fg = "#fff" if on else ("#17804F" if done else t["text3"])
        mark = icon("check", 13, color="#17804F", sw=2.4) if done else str(i)
        out.append(f"""<div class="r" style="gap:7px;">
  <span style="width:22px;height:22px;border-radius:999px;background:{bg};color:{fg};
    display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;">{mark}</span>
  <span class="t12 {'w6' if on else 'w5'}" style="color:{t['text'] if on else t['text3']};">{name}</span>
</div>""")
        if i < 3:
            out.append(f'<span style="width:22px;height:1px;background:{t["border"]};"></span>')
    return ('<div class="r" style="gap:9px;padding:0 20px 12px;">' + "".join(out) + "</div>")

chips = "".join(f"""<span class="r" style="gap:6px;padding:4px 6px 4px 4px;border-radius:999px;
  background:{T['accentSubtle']};">{avatar(i, 22, T, bg='#FFFFFF', fg=T['accent'])}
  <span class="t12 w5" style="color:{T['accent']};">{n}</span>
  <span style="display:flex;color:{T['accent']};opacity:.7;cursor:pointer;">{icon('close',13,sw=2.2)}</span>
</span>""" for i, n in [("MI", "Maya"), ("DS", "Dev"), ("PN", "Priya")])

def check_row(t, ini, name, handle, checked):
    box = (f'<span style="width:20px;height:20px;border-radius:6px;background:{t["accent"]};'
           f'display:flex;align-items:center;justify-content:center;">'
           f'{icon("check",13,color="#fff",sw=2.6)}</span>' if checked else
           f'<span style="width:20px;height:20px;border-radius:6px;border:1.5px solid '
           f'{t["strong"]};"></span>')
    return person(t, ini, name, handle, box)

cg1_body = f"""{stepper(T,1)}
<div class="c" style="gap:12px;padding:0 20px 6px;">
  {search_field(T, "", "Search contacts")}
  <div class="r" style="gap:7px;flex-wrap:wrap;">{chips}</div>
  <div class="c" style="gap:1px;max-height:250px;overflow:hidden;">
    {check_row(T,"MI","Maya Iyer","maya",True)}
    {check_row(T,"DS","Dev Sharma","devsharma",True)}
    {check_row(T,"PN","Priya Nair","priya",True)}
    {check_row(T,"RM","Rohan Mehta","rohan",False)}
    {check_row(T,"AR","Aditi Rao","aditi",False)}
  </div>
</div>"""
cg2_body = f"""{stepper(T,2)}
<div class="c" style="gap:16px;padding:0 20px 6px;">
  <div class="r" style="gap:14px;align-items:center;">
    <div style="position:relative;">{avatar("DG", 60, T, bg=T['hover'], fg=T['text2'])}
      <span style="position:absolute;right:-2px;bottom:-2px;width:24px;height:24px;
        border-radius:999px;background:{T['surface']};border:1px solid {T['border']};
        color:{T['text2']};display:flex;align-items:center;justify-content:center;">
        {icon('camera',13,sw=1.7)}</span></div>
    <div class="c" style="gap:2px;"><span class="t13 w5">Group photo</span>
      <span class="t12 dim">Optional</span></div>
  </div>
  <div class="c" style="gap:6px;">
    <span class="t13 w5">Group name</span>
    <div class="r" style="gap:10px;height:42px;padding:0 13px;border-radius:8px;
      background:{T['surface']};border:2px solid {T['accent']};">
      <span class="t14 g">Design Guild</span>
      <span style="width:1.5px;height:18px;background:{T['accent']};"></span>
      <span class="t11 dim2">12/50</span>
    </div>
    <span class="t12 dim">Everyone you add can see this name.</span>
  </div>
  <div class="r" style="gap:9px;padding:10px 12px;border-radius:8px;background:{T['accentSubtle']};">
    <span style="display:flex;color:{T['accent']};">{icon('users',16,sw=1.8)}</span>
    <span class="t12" style="color:{T['accent']};">3 members selected — you'll be the admin.</span>
  </div>
</div>"""
cg = f"""<div class="r" style="gap:28px;align-items:flex-start;">
  {modal(T, "New group", cg1_body, width=420,
         footer=button(T, "Cancel", "secondary") + button(T, "Next"))}
  {modal(T, "New group", cg2_body, width=420,
         footer=button(T, "Back", "secondary") + button(T, "Create group"))}
</div>"""
write("CreateGroup.dc.html", overlay(cg, active=1))

# ---------- Group info panel ----------
def member(t, ini, name, handle, role=None, you=False):
    tr = ""
    if role == "admin":
        tr = chip(t, "Admin", "accent")
    elif you:
        tr = chip(t, "You", "neutral")
    else:
        tr = f'<span style="display:flex;color:{t["text3"]};cursor:pointer;">{icon("more",17)}</span>'
    return person(t, ini, name, handle, tr)

gi = f"""<div class="c" style="width:360px;flex:0 0 360px;height:100%;background:{T['surface']};
     border-left:1px solid {T['border']};overflow:hidden;">
  <div class="r" style="gap:12px;padding:14px 18px;border-bottom:1px solid {T['subtle']};">
    <span class="t16 w6 g">Group info</span>
    <button style="all:unset;cursor:pointer;color:{T['text3']};display:flex;">{icon('close',18)}</button>
  </div>
  <div class="c" style="align-items:center;gap:10px;padding:22px 18px 18px;
    border-bottom:1px solid {T['subtle']};">
    {avatar("DG", 84, T, bg=T['hover'], fg=T['text2'])}
    <div class="c" style="align-items:center;gap:3px;">
      <span class="t20 w6">Design Guild</span>
      <span class="t13 dim">8 members · 3 online</span>
    </div>
    <div class="r" style="gap:8px;">
      {button(T,'Edit','secondary')}{button(T,'Add member','secondary')}
    </div>
  </div>
  <div class="c" style="gap:2px;padding:14px 8px;">
    <div class="r" style="padding:0 12px 8px;">
      <span class="t11 w6 dim2 g" style="letter-spacing:.4px;">MEMBERS · 8</span>
      <span class="t12 w6" style="color:{T['accent']};cursor:pointer;">Add</span>
    </div>
    {member(T,"AS","Ayush Swamy","ayush",role="admin")}
    {member(T,"MI","Maya Iyer","maya",role="admin")}
    {member(T,"DS","Dev Sharma","devsharma")}
    {member(T,"PN","Priya Nair","priya")}
    {member(T,"RM","Rohan Mehta","rohan")}
  </div>
  <div class="c" style="gap:2px;padding:10px 8px 16px;border-top:1px solid {T['subtle']};">
    <div class="r" style="gap:11px;padding:11px 12px;border-radius:9px;color:{T['danger']};">
      <span style="display:flex;">{icon('close',18)}</span>
      <span class="t14 w5">Leave group</span>
    </div>
  </div>
</div>"""
group_thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Pushed the new tokens to the shared library.", False, "08:52", sender="Maya Iyer"),
    bubble(T, "Thanks Maya.", True, "09:10", status="delivered"),
])
gi_panel = (chat_header(T, "DG", "Design Guild", "8 members · 3 online")
            + f'<div class="c g" style="gap:6px;padding:20px 24px 12px;justify-content:flex-end;">'
              f'{group_thread}</div>' + composer(T))
write("GroupInfo.dc.html", f"""<div class="r" style="width:{W}px;height:{H}px;
  background:{T['canvas']};overflow:hidden;">
  {sidebar(T, conv_html="".join(conv_row(T, c, active=(i==1)) for i,c in enumerate(CONVS)))}
  <div class="c g" style="min-width:0;height:100%;">{gi_panel}</div>{gi}</div>""")

print("panels: NewMessage ContactSearch CreateGroup GroupInfo")
