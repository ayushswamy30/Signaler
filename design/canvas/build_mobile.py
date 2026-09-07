import sys; sys.path.insert(0, '.')
from _lib import T, D, icon, avatar, page
from _shell import (CONVS, conv_row, sidebar, bubble, date_sep, unread_sep,
                    chat_header, composer, typing_row, shell)

MW, MH = 390, 844


def mwrite(name, body, t=T):
    open(name, "w").write(page(body, t, MW, MH))


def m_conv(t, ini, name, prev, time, unread=0, muted=False):
    badge = ""
    if unread:
        badge = (f'<span style="min-width:20px;height:20px;padding:0 6px;border-radius:999px;'
                 f'background:{t["accent"]};color:#fff;font-size:11px;font-weight:600;display:flex;'
                 f'align-items:center;justify-content:center;">{unread}</span>')
    mi = (f'<span style="display:flex;color:{t["text3"]};">{icon("mute",14,sw=1.7)}</span>'
          if muted else "")
    nw = "600" if unread else "500"
    pc = t["text"] if unread else t["text2"]
    return f"""<div class="r" style="gap:13px;min-height:72px;padding:12px 16px;">
  {avatar(ini, 48, t, bg=t['hover'], fg=t['text2'])}
  <div class="c g" style="gap:3px;min-width:0;">
    <div class="r" style="gap:6px;"><span class="t16 ell" style="font-weight:{nw};">{name}</span>
      {mi}<span class="g"></span>
      <span class="t11" style="color:{t['text3']};flex:0 0 auto;">{time}</span></div>
    <div class="r" style="gap:8px;"><span class="t13 ell g" style="color:{pc};">{prev}</span>{badge}</div>
  </div>
</div>"""


# ---------- Mobile list ----------
rows = "".join([
    m_conv(T, "PN", "Priya Nair", "See you at 7 then", "09:24"),
    m_conv(T, "DG", "Design Guild", "Maya: pushed the new tokens", "08:55", unread=3),
    m_conv(T, "RM", "Rohan Mehta", "Thanks, that helps", "Yesterday", muted=True),
    m_conv(T, "AR", "Aditi Rao", "Can you check the draft?", "Yesterday", unread=1),
    m_conv(T, "FM", "Family", "Dad: Photo", "Mon"),
    m_conv(T, "KS", "Karan Singh", "Sounds good to me", "Mon"),
    m_conv(T, "NV", "Neha Verma", "Shared a link", "Sun"),
])
mlist = f"""<div class="c" style="width:{MW}px;height:{MH}px;background:{T['surface']};
     overflow:hidden;">
  <div class="r" style="gap:12px;padding:14px 16px 10px;">
    {avatar("AS", 40, T, online=True)}
    <span class="t24 w7 g" style="letter-spacing:-.3px;">Chats</span>
    <button style="all:unset;cursor:pointer;width:44px;height:44px;border-radius:999px;
      display:flex;align-items:center;justify-content:center;color:{T['text2']};">
      {icon('settings',22)}</button>
  </div>
  <div style="padding:0 16px 12px;">
    <div class="r" style="gap:9px;height:44px;padding:0 14px;border-radius:22px;
      background:{T['hover']};">
      <span style="color:{T['text3']};display:flex;">{icon('search',19)}</span>
      <span class="t14" style="color:{T['text3']};">Search</span>
    </div>
  </div>
  <div class="c g" style="overflow:hidden;">{rows}</div>
  <div style="position:absolute;right:20px;bottom:28px;">
    <button style="all:unset;cursor:pointer;width:58px;height:58px;border-radius:999px;
      background:{T['accent']};color:#fff;display:flex;align-items:center;justify-content:center;
      box-shadow:0 8px 20px rgba(44,107,237,.36);">{icon('edit',24,sw=1.8)}</button>
  </div>
</div>"""
mwrite("MobileList.dc.html", f'<div style="position:relative;width:{MW}px;height:{MH}px;">{mlist}</div>')

# ---------- Mobile chat ----------
mthread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Are we still on for dinner tonight?", False, "09:02"),
    bubble(T, "Yes — 7pm at the usual place.", True, "09:03", status="read"),
    bubble(T, "I booked a table under my name.", True, "09:04", status="delivered"),
    bubble(T, "Perfect. I'll head straight from the office.", False, "09:06"),
    bubble(T, "See you at 7 then", False, "09:24"),
    typing_row(T),
])
mchat = f"""<div class="c" style="width:{MW}px;height:{MH}px;background:{T['canvas']};
     overflow:hidden;">
  <div class="r" style="gap:10px;padding:10px 12px;background:{T['surface']};
    border-bottom:1px solid {T['border']};">
    <button style="all:unset;cursor:pointer;width:44px;height:44px;border-radius:999px;
      display:flex;align-items:center;justify-content:center;color:{T['text2']};">
      {icon('back',22,sw=1.9)}</button>
    {avatar("PN", 38, T, bg=T['hover'], fg=T['text2'])}
    <div class="c g" style="gap:1px;min-width:0;">
      <span class="t16 w6 ell">Priya Nair</span>
      <span class="t12" style="color:{T['accent']};">typing…</span>
    </div>
    <button style="all:unset;cursor:pointer;width:44px;height:44px;border-radius:999px;
      display:flex;align-items:center;justify-content:center;color:{T['text2']};">
      {icon('phone',21)}</button>
    <button style="all:unset;cursor:pointer;width:44px;height:44px;border-radius:999px;
      display:flex;align-items:center;justify-content:center;color:{T['text2']};">
      {icon('video',21)}</button>
  </div>
  <div class="c g" style="gap:6px;padding:16px 14px 10px;justify-content:flex-end;
    overflow:hidden;">{mthread}</div>
  <div style="padding:10px 12px 14px;background:{T['surface']};border-top:1px solid {T['border']};">
    <div class="r" style="gap:10px;">
      <button style="all:unset;cursor:pointer;width:44px;height:44px;border-radius:999px;
        display:flex;align-items:center;justify-content:center;color:{T['text2']};">
        {icon('clip',21)}</button>
      <div class="r g" style="gap:10px;min-height:44px;padding:0 15px;border-radius:22px;
        background:{T['hover']};border:1px solid {T['border']};">
        <span class="t14 g" style="color:{T['text3']};">Message</span>
        <span style="color:{T['text3']};display:flex;">{icon('smile',20)}</span>
      </div>
      <button style="all:unset;cursor:pointer;width:44px;height:44px;border-radius:999px;
        background:{T['hover']};color:{T['text3']};display:flex;align-items:center;
        justify-content:center;">{icon('send',20,sw=1.8)}</button>
    </div>
  </div>
</div>"""
mwrite("MobileChat.dc.html", mchat)

# ---------- Dark chat ----------
dthread = "".join([
    date_sep(D, "Today"),
    bubble(D, "Are we still on for dinner tonight?", False, "09:02"),
    bubble(D, "Yes — 7pm at the usual place.", True, "09:03", status="read", first=True, last=False),
    bubble(D, "I booked a table under my name.", True, "09:03", status="read", first=False, last=True),
    bubble(D, "Perfect. I'll head straight from the office.", False, "09:04",
           quote=("You", "Yes — 7pm at the usual place.")),
    bubble(D, "See you at 7 then", False, "09:24"),
])
dpanel = (chat_header(D, "PN", "Priya Nair", "Online")
          + f'<div class="c g" style="gap:6px;padding:20px 24px 12px;justify-content:flex-end;">'
            f'{dthread}</div>' + composer(D))
open("DarkChat.dc.html", "w").write(
    page(shell(D, sidebar(D, active_index=0), dpanel), D, 1280, 800))

print("MobileList MobileChat DarkChat")
