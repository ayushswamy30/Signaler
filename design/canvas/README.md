# Signaler design canvas — source

Working files behind the published canvas
([Signaler UI Design](https://claude.ai/code/artifact/422d4189-8e9b-4028-a4c4-91580d554cef)):
a design system plus 21 screens across desktop, mobile, light and dark.

Everything derives from [`../design-tokens.md`](../design-tokens.md). No screen
hardcodes a colour, radius or type size — `_lib.py` holds the token values and
every artboard reads them from there, so changing a token changes every screen.

## Layout

| File | What it is |
| --- | --- |
| `_lib.py` | Tokens (light + dark), the icon set, page scaffold, avatar |
| `_shell.py` | App-shell parts: sidebar, conversation row, bubble, chat header, composer |
| `build_app.py` | Direct chat, Empty, Unread, Typing, Reply, Group chat |
| `build_auth.py` | Login, Registration, OTP, Loading, Error |
| `build_panels.py` | New message, Contact search, Create group, Group info |
| `build_settings.py` | Settings, Profile |
| `build_mobile.py` | Mobile list, Mobile chat, Dark chat |
| `build_ds.py` | The design system sheet |
| `canvas.json` | Artboard positions, pages, sticky notes, launch view |
| `*.dc.html` | Generated artboards — one per screen |

The seeded `signaler-ui-design.html` (~2.8 MB) is a build output and is
gitignored; rebuild it rather than editing it.

## Rebuilding

```bash
cd design/canvas
python3 build_app.py && python3 build_auth.py && python3 build_panels.py \
  && python3 build_settings.py && python3 build_mobile.py && python3 build_ds.py
```

Then re-seed and republish the canvas to the same URL. Never hand-edit a
`.dc.html` — the generators overwrite them.

## Conventions the screens hold to

- Delivery status uses a distinct glyph per state, never colour alone.
- Presence is a dot **and** a text last-seen string.
- Focus is a visible 2px ring; mobile hit targets are at least 44px.
- No fake status bars or keyboards on mobile artboards.
- Errors are inline and recoverable — no full-screen error for a retryable case.
- Placeholder settings sections are labelled `Placeholder`.
