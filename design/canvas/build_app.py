import sys; sys.path.insert(0, '.')
from _lib import T, D, icon, avatar, page
from _shell import (CONVS, conv_row, sidebar, bubble, date_sep, unread_sep,
                    chat_header, composer, typing_row, shell)

W, H = 1280, 800


def msgs(inner, pad_top=20):
    return (f'<div class="c g" style="gap:6px;padding:{pad_top}px 24px 12px;'
            f'overflow:hidden;justify-content:flex-end;">{inner}</div>')


def write(name, body, t=T, w=W, h=H):
    open(name, "w").write(page(body, t, w, h))
    return name


# ---------- Main = Direct chat ----------
thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Are we still on for dinner tonight?", False, "09:02", first=True, last=True),
    bubble(T, "Yes — 7pm at the usual place.", True, "09:03", status="read", first=True, last=False),
    bubble(T, "I booked a table under my name.", True, "09:03", status="read", first=False, last=True),
    bubble(T, "Perfect. I'll head straight from the office.", False, "09:04"),
    bubble(T, "See you at 7 then", False, "09:24"),
])
write("Main.dc.html", shell(
    T,
    sidebar(T, active_index=0),
    chat_header(T, "PN", "Priya Nair", "Online")
    + msgs(thread)
    + composer(T)))

# ---------- Unread ----------
unread_thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Did the new tokens land?", True, "08:40", status="read"),
    unread_sep(T, 3),
    bubble(T, "Pushed the new tokens to the shared library.", False, "08:52",
           sender="Maya Iyer", first=True, last=False),
    bubble(T, "Light and dark both covered.", False, "08:53", sender=None, first=False, last=True),
    bubble(T, "Nice — I'll rebind the components this afternoon.", False, "08:55",
           sender="Dev Sharma"),
])
scroll_pill = f"""<div style="display:flex;justify-content:center;margin-top:-6px;">
  <div class="r" style="gap:6px;padding:6px 12px;border-radius:999px;background:{T['accent']};
    color:#fff;box-shadow:0 4px 12px rgba(0,0,0,.14);">
    <span style="display:flex;">{icon('arrowdown',14,sw=2)}</span>
    <span class="t12 w6">3 new messages</span>
  </div>
</div>"""
convs_unread = "\n".join(
    conv_row(T, c, active=(i == 1)) for i, c in enumerate(CONVS))
write("Unread.dc.html", shell(
    T,
    sidebar(T, conv_html=convs_unread),
    chat_header(T, "DG", "Design Guild", "8 members · 3 online")
    + msgs(unread_thread + scroll_pill)
    + composer(T)))

# ---------- Typing ----------
typing_thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Are we still on for dinner tonight?", False, "09:02"),
    bubble(T, "Yes — 7pm at the usual place.", True, "09:03", status="read"),
    bubble(T, "See you at 7 then", False, "09:24"),
    typing_row(T),
])
write("Typing.dc.html", shell(
    T,
    sidebar(T, active_index=0),
    chat_header(T, "PN", "Priya Nair", "typing…", sub_color=T["accent"])
    + msgs(typing_thread)
    + composer(T)))

# ---------- Reply ----------
reply_thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Are we still on for dinner tonight?", False, "09:02"),
    bubble(T, "Yes — 7pm at the usual place.", True, "09:03", status="read"),
    bubble(T, "I booked a table under my name.", True, "09:04", status="delivered", edited=True),
    bubble(T, "Perfect. I'll head straight from the office.", False, "09:06",
           quote=("You", "Yes — 7pm at the usual place.")),
])
write("Reply.dc.html", shell(
    T,
    sidebar(T, active_index=0),
    chat_header(T, "PN", "Priya Nair", "Online")
    + msgs(reply_thread)
    + composer(T, value="Bringing Aditi along, hope that's fine",
               reply=("Priya Nair", "Perfect. I'll head straight from the office."))))

# ---------- Group chat ----------
group_thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Pushed the new tokens to the shared library.", False, "08:52",
           sender="Maya Iyer", first=True, last=False),
    bubble(T, "Light and dark both covered.", False, "08:53", first=False, last=True),
    bubble(T, "Nice — I'll rebind the components this afternoon.", False, "08:55",
           sender="Dev Sharma"),
    bubble(T, "Thanks Maya. Can you drop the changelog in here?", True, "09:10",
           status="delivered"),
    bubble(T, "Done — see the pinned message.", False, "09:12", sender="Maya Iyer",
           quote=("You", "Can you drop the changelog in here?")),
])
write("GroupChat.dc.html", shell(
    T,
    sidebar(T, conv_html="\n".join(conv_row(T, c, active=(i == 1)) for i, c in enumerate(CONVS))),
    chat_header(T, "DG", "Design Guild", "8 members · 3 online")
    + msgs(group_thread)
    + composer(T)))

# ---------- Empty state ----------
empty_panel = f"""<div class="c g" style="align-items:center;justify-content:center;gap:16px;
     padding:40px;text-align:center;">
  <div style="width:88px;height:88px;border-radius:999px;background:{T['accentSubtle']};
    color:{T['accent']};display:flex;align-items:center;justify-content:center;">
    {icon('edit', 38, sw=1.4)}
  </div>
  <div class="c" style="gap:6px;align-items:center;">
    <span class="t20 w6">No conversation selected</span>
    <span class="t14 dim" style="max-width:380px;">Pick a conversation from the list, or start
      a new one. Messages you send stay in sync across your devices.</span>
  </div>
  <button style="all:unset;cursor:pointer;display:flex;align-items:center;gap:8px;height:40px;
    padding:0 18px;border-radius:8px;background:{T['accent']};color:#fff;font-size:13px;
    font-weight:500;">{icon('plus',18,sw=2)} New message</button>
</div>"""
convs_none = "\n".join(conv_row(T, c) for c in CONVS)
write("Empty.dc.html", shell(T, sidebar(T, conv_html=convs_none), empty_panel))

print("app screens:", ["Main", "Unread", "Typing", "Reply", "GroupChat", "Empty"])
