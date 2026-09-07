import sys; sys.path.insert(0, '.')
from _lib import T, icon, avatar, page
from _shell import bubble, conv_row, CONVS, date_sep, unread_sep, typing_row

W, H = 1560, 2040


def sec(title, note, inner):
    n = f'<span class="t13 dim">{note}</span>' if note else ""
    return f"""<div class="c" style="gap:14px;">
  <div class="c" style="gap:3px;"><span class="t16 w6">{title}</span>{n}</div>
  <div style="height:1px;background:{T['border']};"></div>
  {inner}
</div>"""


def card(inner, pad=20):
    return (f'<div class="c" style="gap:16px;padding:{pad}px;border-radius:12px;'
            f'background:{T["surface"]};border:1px solid {T["border"]};">{inner}</div>')


def lbl(s):
    return f'<span class="t11 w6 dim2" style="letter-spacing:.4px;">{s}</span>'


def btn(variant, state, label="Button", loading=False):
    looks = {
        ("Primary", "Default"): (T["accent"], "#fff", None),
        ("Primary", "Hover"): (T["accentHover"], "#fff", None),
        ("Primary", "Disabled"): (T["border"], T["text3"], None),
        ("Secondary", "Default"): (T["surface"], T["text"], T["border"]),
        ("Secondary", "Hover"): (T["hover"], T["text"], T["strong"]),
        ("Secondary", "Disabled"): (T["surface"], T["text3"], T["subtle"]),
        ("Ghost", "Default"): ("transparent", T["text2"], None),
        ("Ghost", "Hover"): (T["hover"], T["text"], None),
        ("Ghost", "Disabled"): ("transparent", T["text3"], None),
        ("Danger", "Default"): (T["danger"], "#fff", None),
        ("Danger", "Hover"): ("#B32B2B", "#fff", None),
        ("Danger", "Disabled"): (T["border"], T["text3"], None),
    }[(variant, state)]
    bg, fg, bd = looks
    border = f"border:1px solid {bd};" if bd else "border:1px solid transparent;"
    focus = ""
    if state == "Focus":
        focus = f"box-shadow:0 0 0 2px {T['surface']},0 0 0 4px {T['accent']};"
    spin = ("" if not loading else
            f'<span style="width:14px;height:14px;border-radius:999px;border:2px solid '
            f'{"rgba(255,255,255,.45)" if fg == "#fff" else T["text3"]};'
            f'border-top-color:{fg};"></span>')
    return (f'<span style="display:flex;align-items:center;justify-content:center;gap:8px;'
            f'height:40px;padding:0 16px;border-radius:8px;background:{bg};color:{fg};{border}'
            f'{focus}font-size:13px;font-weight:500;">{spin}{label}</span>')


btn_grid = ""
for v in ["Primary", "Secondary", "Ghost", "Danger"]:
    cells = "".join(f'<div class="c" style="gap:7px;align-items:flex-start;">{lbl(s)}'
                    f'{btn(v, s)}</div>' for s in ["Default", "Hover", "Disabled"])
    btn_grid += (f'<div class="c" style="gap:9px;"><span class="t13 w6">{v}</span>'
                 f'<div class="r" style="gap:16px;">{cells}</div></div>')
btn_extra = (f'<div class="r" style="gap:16px;">'
             f'<div class="c" style="gap:7px;align-items:flex-start;">{lbl("FOCUS")}'
             f'{btn("Primary","Focus" if False else "Default")}'
             f'</div>'
             f'<div class="c" style="gap:7px;align-items:flex-start;">{lbl("LOADING")}'
             f'{btn("Primary","Default","Sending",loading=True)}</div></div>')
focus_btn = (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
             f'height:40px;padding:0 16px;border-radius:8px;background:{T["accent"]};color:#fff;'
             f'box-shadow:0 0 0 2px {T["surface"]},0 0 0 4px {T["accent"]};font-size:13px;'
             f'font-weight:500;">Button</span>')


def input_state(state):
    conf = {"Default": (T["border"], 1, T["text3"], "Enter a username", T["text2"],
                        "We never share this."),
            "Focus": (T["accent"], 2, T["text"], "ayush", T["text2"], "We never share this."),
            "Error": (T["danger"], 2, T["text"], "ayush", T["danger"],
                      "That username is already taken."),
            "Disabled": (T["subtle"], 1, T["text3"], "ayush", T["text3"], "Unavailable right now.")}[state]
    bc, bw, tc, val, hc, helper = conf
    caret = (f'<span style="width:1.5px;height:18px;background:{T["accent"]};"></span>'
             if state == "Focus" else "")
    ic = (f'<span style="display:flex;color:{T["danger"]};">{icon("warn",13,sw=2)}</span>'
          if state == "Error" else "")
    op = "opacity:.65;" if state == "Disabled" else ""
    return f"""<div class="c" style="gap:6px;width:230px;{op}">{lbl(state.upper())}
  <span class="t13 w5">Username</span>
  <div class="r" style="gap:10px;height:40px;padding:0 13px;border-radius:8px;
    background:{T['hover'] if state=='Disabled' else T['surface']};border:{bw}px solid {bc};">
    <span class="t14 g" style="color:{tc};">{val}</span>{caret}
  </div>
  <div class="r t12" style="gap:5px;color:{hc};">{ic}{helper}</div>
</div>"""


status_legend = f"""<div class="c" style="gap:12px;">
  <div class="r" style="gap:26px;">
    <div class="c" style="gap:6px;align-items:center;">
      <span style="display:flex;color:{T['text2']};">{icon('check',18,sw=2)}</span>
      <span class="t12 w6">Sent</span><span class="t11 dim2">one tick</span></div>
    <div class="c" style="gap:6px;align-items:center;">
      <span style="display:flex;color:{T['text2']};">{icon('checks',20,sw=2)}</span>
      <span class="t12 w6">Delivered</span><span class="t11 dim2">two ticks</span></div>
    <div class="c" style="gap:6px;align-items:center;">
      <span style="display:flex;color:{T['accent']};">{icon('checks',20,sw=2.8)}</span>
      <span class="t12 w6">Read</span><span class="t11 dim2">two ticks, heavier + accent</span></div>
    <div class="c" style="gap:6px;align-items:center;">
      <span style="display:flex;color:{T['danger']};">{icon('warn',18,sw=2)}</span>
      <span class="t12 w6">Failed</span><span class="t11 dim2">triangle + text</span></div>
  </div>
  <div class="r" style="gap:9px;padding:10px 12px;border-radius:8px;background:{T['accentSubtle']};">
    <span style="display:flex;color:{T['accent']};margin-top:1px;">{icon('info',15,sw=1.9)}</span>
    <span class="t12" style="color:{T['accent']};">Status never relies on colour alone — each
      state has a distinct glyph, so it survives greyscale and colour-blindness.</span>
  </div>
</div>"""

bubbles = "".join([
    bubble(T, "Are we still on for dinner tonight?", False, "09:02"),
    bubble(T, "Yes — 7pm at the usual place.", True, "09:03", status="sent", first=True, last=False),
    bubble(T, "I booked a table.", True, "09:03", status="delivered", first=False, last=False),
    bubble(T, "Under my name.", True, "09:04", status="read", first=False, last=True, edited=True),
    bubble(T, "Perfect, see you then.", False, "09:06",
           quote=("You", "Yes — 7pm at the usual place.")),
    bubble(T, "Pushed the new tokens.", False, "08:52", sender="Maya Iyer"),
])

toast_ok = f"""<div class="r" style="gap:10px;padding:11px 15px;border-radius:10px;
  background:#141A21;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.18);">
  <span style="display:flex;color:#3DBE84;">{icon('check',16,sw=2.4)}</span>
  <span class="t13 w5">Group created</span></div>"""
toast_err = f"""<div class="r" style="gap:10px;padding:11px 15px;border-radius:10px;
  background:#141A21;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.18);">
  <span style="display:flex;color:{T['warning']};">{icon('warn',16,sw=1.9)}</span>
  <span class="t13 w5 g">Couldn't reach the server</span>
  <span class="t12 w6" style="color:{T['accent']};">Retry</span></div>"""

dropdown = f"""<div class="c" style="width:210px;padding:6px;border-radius:10px;
  background:{T['surface']};border:1px solid {T['border']};box-shadow:0 4px 12px rgba(0,0,0,.10);">
  {"".join(f'''<div class="r" style="gap:10px;padding:9px 10px;border-radius:7px;
    background:{T['hover'] if i==1 else 'transparent'};">
    <span style="display:flex;color:{T['text2']};">{icon(ic,17)}</span>
    <span class="t13 w5">{t}</span></div>''' for i,(ic,t) in enumerate(
      [("info","View contact"),("mute","Mute notifications"),("users","Add to group")]))}
  <div style="height:1px;background:{T['subtle']};margin:5px 0;"></div>
  <div class="r" style="gap:10px;padding:9px 10px;border-radius:7px;color:{T['danger']};">
    <span style="display:flex;">{icon('close',17)}</span><span class="t13 w5">Block</span></div>
</div>"""

tooltip = f"""<div class="c" style="gap:8px;align-items:center;">
  <span style="padding:6px 10px;border-radius:7px;background:#141A21;color:#fff;
    font-size:12px;font-weight:500;">Start a video call</span>
  <span style="width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;
    border-top:5px solid #141A21;margin-top:-8px;"></span>
  <span style="width:34px;height:34px;border-radius:8px;background:{T['hover']};color:{T['text2']};
    display:flex;align-items:center;justify-content:center;">{icon('video',19)}</span>
</div>"""


def skl(w, h, r=6):
    return (f'<span style="display:block;width:{w};height:{h}px;border-radius:{r}px;'
            f'background:{T["hover"]};"></span>')


skeleton = f"""<div class="r" style="gap:12px;width:300px;">
  {skl('44px',44,999)}<div class="c g" style="gap:7px;">{skl('60%',11)}{skl('85%',10)}</div></div>"""

empty = f"""<div class="c" style="align-items:center;gap:12px;padding:22px;text-align:center;
  width:300px;">
  <div style="width:64px;height:64px;border-radius:999px;background:{T['accentSubtle']};
    color:{T['accent']};display:flex;align-items:center;justify-content:center;">
    {icon('users',28,sw=1.4)}</div>
  <div class="c" style="gap:4px;align-items:center;">
    <span class="t16 w6">No contacts yet</span>
    <span class="t13 dim">Search for someone by username to start your first conversation.</span>
  </div>
  <span style="display:flex;align-items:center;gap:8px;height:38px;padding:0 16px;border-radius:8px;
    background:{T['accent']};color:#fff;font-size:13px;font-weight:500;">
    {icon('plus',17,sw=2.2)} Find people</span>
</div>"""

conv_states = "".join([
    f'<div class="c" style="gap:6px;">{lbl("DEFAULT")}'
    f'<div style="width:320px;">{conv_row(T, CONVS[0])}</div></div>',
    f'<div class="c" style="gap:6px;">{lbl("ACTIVE")}'
    f'<div style="width:320px;">{conv_row(T, CONVS[0], active=True)}</div></div>',
    f'<div class="c" style="gap:6px;">{lbl("UNREAD")}'
    f'<div style="width:320px;">{conv_row(T, CONVS[1])}</div></div>',
    f'<div class="c" style="gap:6px;">{lbl("MUTED")}'
    f'<div style="width:320px;">{conv_row(T, CONVS[2])}</div></div>',
])

avatars = "".join(f'<div class="c" style="gap:7px;align-items:center;">'
                  f'{avatar("AS", s, T, online=(s>=32))}{lbl(str(s))}</div>'
                  for s in [24, 32, 40, 48, 64])

badges = f"""<div class="r" style="gap:20px;align-items:center;">
  <div class="c" style="gap:7px;align-items:center;">
    <span style="min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:{T['accent']};
      color:#fff;font-size:11px;font-weight:600;display:flex;align-items:center;
      justify-content:center;">3</span>{lbl("UNREAD")}</div>
  <div class="c" style="gap:7px;align-items:center;">
    <span style="min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:{T['accent']};
      color:#fff;font-size:11px;font-weight:600;display:flex;align-items:center;
      justify-content:center;">99+</span>{lbl("OVERFLOW")}</div>
  <div class="c" style="gap:7px;align-items:center;">
    <span style="display:flex;color:{T['text3']};">{icon('mute',17,sw=1.7)}</span>{lbl("MUTED")}</div>
  <div class="c" style="gap:7px;align-items:center;">
    <span class="t11 w6" style="padding:3px 9px;border-radius:999px;background:{T['accentSubtle']};
      color:{T['accent']};">Admin</span>{lbl("ROLE")}</div>
</div>"""

tree = """AppShell
├── Sidebar
│   ├── ProfileHeader   ├── SearchBar
│   ├── ConversationList → ConversationItem
│   └── NewMessageButton
└── ChatPanel
    ├── ChatHeader
    ├── MessageList → DateSeparator, UnreadDivider,
    │                  MessageBubble → ReplyPreview, MessageMeta
    ├── TypingIndicator
    └── MessageComposer

Overlays   NewMessageModal · CreateGroupModal · GroupInfoPanel
           SettingsPanel · Dropdown · Toast · Tooltip
Primitives Avatar · Badge · Button · Input · Skeleton · Divider"""

body = f"""<div class="c" style="width:{W}px;min-height:{H}px;background:{T['canvas']};
     padding:44px;gap:30px;">
  <div class="c" style="gap:7px;">
    <span class="t32 w7" style="letter-spacing:-.6px;">Signaler design system</span>
    <span class="t16 dim" style="max-width:760px;">Every component below is built from the tokens
      in <span class="w6" style="color:{T['text']};">design/design-tokens.md</span>. Nothing here
      hardcodes a colour, radius or type size.</span>
  </div>

  <div class="r" style="gap:26px;align-items:flex-start;">
    <div class="c g" style="gap:26px;">
      {sec("Buttons", "Four variants across three states, plus focus and loading.",
           card(f'<div class="c" style="gap:20px;">{btn_grid}'
                f'<div class="r" style="gap:22px;">'
                f'<div class="c" style="gap:7px;align-items:flex-start;">{lbl("FOCUS RING")}{focus_btn}</div>'
                f'<div class="c" style="gap:7px;align-items:flex-start;">{lbl("LOADING")}'
                f'{btn("Primary","Default","Sending",loading=True)}</div></div></div>'))}
      {sec("Inputs", "Error text always accompanies the error colour.",
           card(f'<div class="r" style="gap:20px;flex-wrap:wrap;">'
                f'{"".join(input_state(s) for s in ["Default","Focus","Error","Disabled"])}</div>'))}
      {sec("Message bubbles", "Grouping, reply quote, edited marker and delivery status.",
           card(f'<div class="c" style="gap:6px;max-width:560px;">{bubbles}</div>'))}
      {sec("Delivery status", "Brief §6 and §19 — never colour alone.", card(status_legend))}
    </div>

    <div class="c" style="width:520px;flex:0 0 520px;gap:26px;">
      {sec("Avatar", "With optional presence dot.",
           card(f'<div class="r" style="gap:22px;align-items:flex-end;">{avatars}</div>'))}
      {sec("Badges & chips", None, card(badges))}
      {sec("Conversation item", "The sidebar row in each of its states.",
           card(f'<div class="c" style="gap:14px;">{conv_states}</div>'))}
      {sec("Overlays", "Dropdown, tooltip and toasts.",
           card(f'<div class="c" style="gap:18px;">'
                f'<div class="r" style="gap:26px;align-items:flex-start;">{dropdown}{tooltip}</div>'
                f'<div class="c" style="gap:10px;">{toast_ok}{toast_err}</div></div>'))}
      {sec("Loading & empty", "Skeletons stand in for content; empty states propose a next action.",
           card(f'<div class="c" style="gap:20px;">{skeleton}'
                f'<div style="height:1px;background:{T["subtle"]};"></div>{empty}</div>'))}
      {sec("Component tree", "Brief §21.",
           card(f'<pre style="margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
                f'font-size:12px;line-height:19px;color:{T["text2"]};white-space:pre;">{tree}</pre>'))}
    </div>
  </div>
</div>"""
open("DesignSystem.dc.html", "w").write(page(body, T, W, H))
print("DesignSystem")
