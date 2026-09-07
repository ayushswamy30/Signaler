import sys; sys.path.insert(0, '.')
from _lib import T, icon, avatar, page
from _shell import CONVS, conv_row, sidebar, chat_header, composer, bubble, date_sep, shell

W, H = 1280, 800


def wordmark(t, size=28):
    return f"""<div class="r" style="gap:10px;">
  <span style="width:{size}px;height:{size}px;border-radius:8px;background:{t['accent']};
    color:#fff;display:flex;align-items:center;justify-content:center;">
    {icon('send', int(size*0.62), sw=1.9)}</span>
  <span class="w7" style="font-size:{size-4}px;letter-spacing:-.4px;">Signaler</span>
</div>"""


def field(t, label, value=None, placeholder="", state="default", helper=None, hint_icon=None):
    border = {"default": t["border"], "focus": t["accent"],
              "error": t["danger"], "disabled": t["subtle"]}[state]
    weight = 2 if state in ("focus", "error") else 1
    col = t["text"] if value else t["text3"]
    caret = (f'<span style="width:1.5px;height:18px;background:{t["accent"]};"></span>'
             if state == "focus" else "")
    helper_col = t["danger"] if state == "error" else t["text2"]
    helper_html = ""
    if helper:
        ic = (f'<span style="display:flex;color:{t["danger"]};">{icon("warn",13,sw=2)}</span>'
              if state == "error" else "")
        helper_html = (f'<div class="r t12" style="gap:5px;color:{helper_col};margin-top:5px;">'
                       f'{ic}{helper}</div>')
    return f"""<div class="c" style="gap:6px;">
  <span class="t13 w5">{label}</span>
  <div class="r" style="gap:10px;height:42px;padding:0 13px;border-radius:8px;
    background:{t['surface']};border:{weight}px solid {border};">
    <span class="t14 g" style="color:{col};">{value or placeholder}</span>{caret}
    {hint_icon or ''}
  </div>{helper_html}
</div>"""


def btn(t, label, kind="primary", full=True, loading=False, disabled=False):
    bg = {"primary": t["accent"], "secondary": t["surface"], "ghost": "transparent"}[kind]
    fg = {"primary": "#fff", "secondary": t["text"], "ghost": t["text2"]}[kind]
    bd = f"border:1px solid {t['border']};" if kind == "secondary" else "border:none;"
    op = "opacity:.7;" if disabled else ""
    w = "width:100%;" if full else ""
    spin = ""
    if loading:
        spin = (f'<span style="width:15px;height:15px;border-radius:999px;border:2px solid '
                f'rgba(255,255,255,.45);border-top-color:#fff;"></span>')
    return f"""<button style="all:unset;cursor:pointer;box-sizing:border-box;{w}height:42px;
   border-radius:8px;background:{bg};color:{fg};{bd}{op}display:flex;align-items:center;
   justify-content:center;gap:9px;font-size:13px;font-weight:500;">{spin}{label}</button>"""


def auth_card(t, inner, width=400):
    return f"""<div class="r" style="width:{W}px;height:{H}px;background:{t['canvas']};
     align-items:center;justify-content:center;">
  <div class="c" style="width:{width}px;gap:24px;padding:36px;border-radius:16px;
    background:{t['surface']};border:1px solid {t['border']};
    box-shadow:0 8px 24px rgba(0,0,0,.06);">{inner}</div>
</div>"""


def write(name, body, t=T):
    open(name, "w").write(page(body, t, W, H))


# ---------- Login (with error state) ----------
login = f"""{wordmark(T)}
<div class="c" style="gap:4px;">
  <span class="t24 w6">Sign in</span>
  <span class="t14 dim">Use the username and password you registered with.</span>
</div>
<div class="r" style="gap:10px;padding:11px 13px;border-radius:8px;background:#FBE3E3;
  color:#B32B2B;align-items:flex-start;">
  <span style="display:flex;margin-top:1px;">{icon('warn',16,sw=1.9)}</span>
  <span class="t13 w5 g">That username and password don't match. Check both and try again.</span>
</div>
<div class="c" style="gap:16px;">
  {field(T, "Username", value="ayush", state="error")}
  {field(T, "Password", value="••••••••", state="error",
         helper="2 attempts left before a short cool-down.")}
</div>
{btn(T, "Sign in")}
<div class="r" style="gap:6px;justify-content:center;">
  <span class="t13 dim">New here?</span><a class="t13 w5" href="#">Create an account</a>
</div>"""
write("Login.dc.html", auth_card(T, login))

# ---------- Registration ----------
reg = f"""{wordmark(T)}
<div class="c" style="gap:4px;">
  <span class="t24 w6">Create your account</span>
  <span class="t14 dim">Your username is how people find you. It can't be changed later.</span>
</div>
<div class="r" style="gap:16px;align-items:center;">
  <div style="position:relative;">
    {avatar("AS", 64, T)}
    <span style="position:absolute;right:-2px;bottom:-2px;width:26px;height:26px;border-radius:999px;
      background:{T['surface']};border:1px solid {T['border']};color:{T['text2']};display:flex;
      align-items:center;justify-content:center;">{icon('camera',14,sw=1.7)}</span>
  </div>
  <div class="c" style="gap:2px;">
    <span class="t13 w5">Profile photo</span>
    <span class="t12 dim">Optional. PNG or JPG, up to 2 MB.</span>
  </div>
</div>
<div class="c" style="gap:14px;">
  {field(T, "Display name", value="Ayush Swamy")}
  {field(T, "Username", value="ayush", state="focus",
         helper="Available. Letters, numbers and underscores.",
         hint_icon='<span style="display:flex;color:#1E9E62;">'
                   + icon('check', 16, sw=2.2) + '</span>')}
  {field(T, "Phone number", value="+91 98••• ••210", helper="Optional. Used only to find friends.")}
  {field(T, "Password", value="••••••••••", helper="At least 10 characters.")}
</div>
{btn(T, "Create account")}
<div class="r" style="gap:6px;justify-content:center;">
  <span class="t13 dim">Already registered?</span><a class="t13 w5" href="#">Sign in</a>
</div>"""
write("Registration.dc.html", auth_card(T, reg, width=440))

# ---------- OTP ----------
def otp_box(t, ch, state="filled"):
    border = {"filled": t["strong"], "focus": t["accent"], "empty": t["border"],
              "error": t["danger"]}[state]
    weight = 2 if state in ("focus", "error") else 1
    caret = (f'<span style="width:1.5px;height:22px;background:{t["accent"]};"></span>'
             if state == "focus" else "")
    return (f'<div style="width:48px;height:56px;border-radius:10px;background:{t["surface"]};'
            f'border:{weight}px solid {border};display:flex;align-items:center;'
            f'justify-content:center;font-size:22px;font-weight:600;">{ch}{caret}</div>')

otp = f"""{wordmark(T)}
<div class="c" style="gap:4px;">
  <span class="t24 w6">Verify your number</span>
  <span class="t14 dim">We sent a 6-digit code to <span class="w6"
    style="color:{T['text']};">+91 98••• ••210</span>.</span>
</div>
<div class="r" style="gap:10px;">
  {otp_box(T,'4')}{otp_box(T,'9')}{otp_box(T,'2')}{otp_box(T,'7')}
  {otp_box(T,'',state='focus')}{otp_box(T,'',state='empty')}
</div>
<div class="r" style="gap:8px;padding:10px 13px;border-radius:8px;background:#FBE3E3;color:#B32B2B;">
  <span style="display:flex;">{icon('warn',16,sw=1.9)}</span>
  <span class="t13 w5">That code has expired. Request a new one below.</span>
</div>
{btn(T, "Verify")}
<div class="r" style="gap:6px;justify-content:center;">
  <span class="t13 dim">Didn't get it?</span>
  <a class="t13 w5" href="#">Resend code</a>
  <span class="t13 dim2">· in 0:24</span>
</div>"""
write("OTP.dc.html", auth_card(T, otp, width=420))

# ---------- Loading (skeletons) ----------
def sk(t, w, h, r=6, op=1.0):
    return (f'<span style="display:block;width:{w};height:{h}px;border-radius:{r}px;'
            f'background:{t["hover"]};opacity:{op};"></span>')

sk_rows = "".join(f"""<div class="r" style="gap:12px;padding:10px 12px;">
  {sk(T,'44px',44,999)}
  <div class="c g" style="gap:7px;"><div class="r" style="gap:8px;">{sk(T,'44%',11)}
    <span class="g"></span>{sk(T,'28px',9)}</div>{sk(T,'72%',10)}</div>
</div>""" for _ in range(7))

sk_sidebar = f"""<div class="c" style="width:340px;flex:0 0 340px;background:{T['surface']};
     border-right:1px solid {T['border']};height:100%;">
  <div class="r" style="gap:12px;padding:16px;border-bottom:1px solid {T['subtle']};">
    {sk(T,'36px',36,999)}<div class="c g" style="gap:6px;">{sk(T,'50%',11)}{sk(T,'32%',9)}</div>
  </div>
  <div style="padding:12px 16px;">{sk(T,'100%',36,8)}</div>
  <div class="c g" style="padding:0 8px;">{sk_rows}</div>
</div>"""

sk_msgs = "".join([
    f'<div style="display:flex;justify-content:flex-start;">{sk(T,"300px",56,14)}</div>',
    f'<div style="display:flex;justify-content:flex-end;">{sk(T,"240px",40,14)}</div>',
    f'<div style="display:flex;justify-content:flex-end;">{sk(T,"330px",56,14)}</div>',
    f'<div style="display:flex;justify-content:flex-start;">{sk(T,"270px",40,14)}</div>',
    f'<div style="display:flex;justify-content:flex-start;">{sk(T,"180px",40,14)}</div>',
])
sk_panel = f"""<div class="r" style="gap:12px;padding:12px 20px;border-bottom:1px solid {T['border']};
     background:{T['surface']};">
  {sk(T,'38px',38,999)}<div class="c g" style="gap:6px;">{sk(T,'160px',12)}{sk(T,'90px',10)}</div>
</div>
<div class="c g" style="gap:14px;padding:24px;justify-content:flex-end;">{sk_msgs}</div>
<div style="padding:12px 20px 16px;background:{T['surface']};border-top:1px solid {T['border']};">
  {sk(T,'100%',40,20)}</div>"""
write("Loading.dc.html", shell(T, sk_sidebar, sk_panel))

# ---------- Error / offline ----------
err_thread = "".join([
    date_sep(T, "Today"),
    bubble(T, "Are we still on for dinner tonight?", False, "09:02"),
    bubble(T, "Yes — 7pm at the usual place.", True, "09:03", status="read"),
])
failed = f"""<div style="display:flex;justify-content:flex-end;">
  <div class="c" style="align-items:flex-end;gap:4px;">
    <div style="max-width:460px;padding:8px 12px;border-radius:14px 14px 4px 14px;
      background:{T['outBg']};color:#fff;opacity:.55;">
      <div class="t14">I booked a table under my name.</div>
    </div>
    <div class="r" style="gap:6px;color:{T['danger']};">
      <span style="display:flex;">{icon('warn',13,sw=2)}</span>
      <span class="t11 w5">Not delivered</span>
      <span class="t11 w6" style="text-decoration:underline;cursor:pointer;">Retry</span>
    </div>
  </div>
</div>"""
banner = f"""<div class="r" style="gap:10px;padding:9px 20px;background:#FBEFD5;color:#8A5A05;
     border-bottom:1px solid #F0DDB0;">
  <span style="display:flex;">{icon('wifi',16,sw=1.8)}</span>
  <span class="t13 w5 g">You're offline. Signaler will reconnect and send queued messages
    automatically.</span>
  <span class="t12 w6" style="text-decoration:underline;cursor:pointer;">Try now</span>
</div>"""
toast = f"""<div style="position:absolute;left:50%;bottom:96px;transform:translateX(-50%);">
  <div class="r" style="gap:10px;padding:11px 15px;border-radius:10px;background:#141A21;
    color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.18);">
    <span style="display:flex;color:{T['warning']};">{icon('warn',16,sw=1.9)}</span>
    <span class="t13 w5">Couldn't reach the server. Retrying…</span>
    <span class="t12 w6" style="color:{T['accent']};cursor:pointer;">Dismiss</span>
  </div>
</div>"""
err_panel = (banner + chat_header(T, "PN", "Priya Nair", "Reconnecting…",
                                  sub_color=T["warning"])
             + f'<div class="c g" style="position:relative;gap:6px;padding:20px 24px 12px;'
               f'justify-content:flex-end;">{err_thread}{failed}{toast}</div>'
             + composer(T, error="Message failed to send. Check your connection."))
write("Error.dc.html", shell(T, sidebar(T, active_index=0), err_panel))

print("auth/state screens: Login Registration OTP Loading Error")
