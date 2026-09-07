# Signaler — Design Tokens

The token contract behind the Figma file
([Signaler — UI/UX Design](https://www.figma.com/design/rG45dZ6H9uONU856BWleL8)).
Every value below exists as a Figma variable with WEB code syntax already set, so
`var(--color-bg-surface)` in CSS and the Figma variable are the same token.

Nothing in the UI should hardcode a colour, radius, space or type size. If a value
is needed that isn't here, add a token rather than a literal.

## Themes

Figma's Starter plan allows only one mode per variable collection, so light and dark
are **two collections with identical variable names** — `Color Light` and `Color Dark`.
A component binds to a token name; swapping the collection reskins the theme. In CSS this
maps to one `:root` block and one `[data-theme="dark"]` block over the same custom
property names.

## Semantic colour tokens

35 tokens, defined in both themes. Light and dark values are aliases onto the
primitive palette — no raw hex is repeated in the semantic layer.

| Token | CSS variable | Light | Dark |
| --- | --- | --- | --- |
| `bg/canvas` | `--color-bg-canvas` | gray/50 `#F7F8FA` | gray/950 `#0B0F14` |
| `bg/surface` | `--color-bg-surface` | white `#FFFFFF` | gray/900 `#141A21` |
| `bg/surface-raised` | `--color-bg-surface-raised` | white `#FFFFFF` | gray/850 `#182029` |
| `bg/sidebar` | `--color-bg-sidebar` | white `#FFFFFF` | gray/900 `#141A21` |
| `bg/hover` | `--color-bg-hover` | gray/100 `#EEF0F4` | gray/850 `#182029` |
| `bg/active` | `--color-bg-active` | blue/50 `#EAF2FF` | gray/800 `#1F262F` |
| `bg/inverse` | `--color-bg-inverse` | gray/900 | white |
| `bg/overlay` | `--color-bg-overlay` | gray/900 | black |
| `text/primary` | `--color-text-primary` | gray/900 `#141A21` | gray/50 `#F7F8FA` |
| `text/secondary` | `--color-text-secondary` | gray/500 `#6B7683` | gray/400 `#9AA4B2` |
| `text/tertiary` | `--color-text-tertiary` | gray/400 `#9AA4B2` | gray/500 `#6B7683` |
| `text/inverse` | `--color-text-inverse` | white | gray/900 |
| `text/link` | `--color-text-link` | blue/600 `#1E55C9` | blue/300 `#7BAAFF` |
| `text/danger` | `--color-text-danger` | red/500 `#D93A3A` | red/400 `#E76A6A` |
| `text/on-accent` | `--color-text-on-accent` | white | white |
| `border/subtle` | `--color-border-subtle` | gray/100 | gray/850 |
| `border/default` | `--color-border-default` | gray/200 `#E1E5EB` | gray/800 `#1F262F` |
| `border/strong` | `--color-border-strong` | gray/300 `#C9D0DA` | gray/700 `#333C49` |
| `border/focus` | `--color-border-focus` | blue/500 `#2C6BED` | blue/400 `#4B8BFF` |
| `accent/default` | `--color-accent-default` | blue/500 `#2C6BED` | blue/400 `#4B8BFF` |
| `accent/hover` | `--color-accent-hover` | blue/600 `#1E55C9` | blue/300 `#7BAAFF` |
| `accent/pressed` | `--color-accent-pressed` | blue/700 `#17429C` | blue/500 `#2C6BED` |
| `accent/subtle` | `--color-accent-subtle` | blue/50 `#EAF2FF` | blue/900 `#0D2450` |
| `bubble/outgoing-bg` | `--color-bubble-outgoing-bg` | blue/500 | blue/600 |
| `bubble/outgoing-text` | `--color-bubble-outgoing-text` | white | white |
| `bubble/incoming-bg` | `--color-bubble-incoming-bg` | gray/100 | gray/800 |
| `bubble/incoming-text` | `--color-bubble-incoming-text` | gray/900 | gray/50 |
| `bubble/quote-bg` | `--color-bubble-quote-bg` | gray/200 | gray/700 |
| `bubble/quote-border` | `--color-bubble-quote-border` | blue/500 | blue/300 |
| `status/online` | `--color-status-online` | green/500 `#1E9E62` | green/400 `#3DBE84` |
| `status/success` | `--color-status-success` | green/500 | green/400 |
| `status/danger` | `--color-status-danger` | red/500 `#D93A3A` | red/400 `#E76A6A` |
| `status/warning` | `--color-status-warning` | amber/500 `#D98B0A` | amber/400 `#EBAA3A` |
| `status/unread-bg` | `--color-status-unread-bg` | blue/500 | blue/400 |
| `status/unread-text` | `--color-status-unread-text` | white | gray/950 |

## Primitive palette

Raw values only. Scoped out of Figma's property pickers so nobody binds a component
straight to a primitive — always go through a semantic token.

- **Neutral** `gray/50 #F7F8FA` · `100 #EEF0F4` · `200 #E1E5EB` · `300 #C9D0DA` · `400 #9AA4B2` · `500 #6B7683` · `600 #4A5563` · `700 #333C49` · `800 #1F262F` · `850 #182029` · `900 #141A21` · `950 #0B0F14`
- **Brand blue** `50 #EAF2FF` · `100 #D2E3FF` · `200 #A8C8FF` · `300 #7BAAFF` · `400 #4B8BFF` · `500 #2C6BED` · `600 #1E55C9` · `700 #17429C` · `800 #12336F` · `900 #0D2450`
- **Green** `100 #D8F3E5` · `400 #3DBE84` · `500 #1E9E62` · `600 #17804F`
- **Red** `100 #FBE3E3` · `400 #E76A6A` · `500 #D93A3A` · `600 #B32B2B`
- **Amber** `100 #FBEFD5` · `400 #EBAA3A` · `500 #D98B0A`
- **Base** `white #FFFFFF` · `black #000000`

## Spacing

`--space-*` — a 4px-based scale with a 2px step for tight metadata rows.

| Token | px | Typical use |
| --- | --- | --- |
| `spacing/2xs` | 2 | Icon-to-label nudges |
| `spacing/xs` | 4 | Timestamp to status tick |
| `spacing/sm` | 8 | Inside buttons, chips |
| `spacing/md` | 12 | Field padding, list row gaps |
| `spacing/lg` | 16 | Card padding, bubble padding |
| `spacing/xl` | 24 | Section spacing |
| `spacing/2xl` | 32 | Panel padding |
| `spacing/3xl` | 48 | Empty-state blocks |
| `spacing/4xl` | 64 | Page gutters |

## Radius

`--radius-*`: `none 0` · `sm 4` · `md 8` · `lg 12` · `xl 16` · `2xl 20` · `full 999`

Message bubbles use `lg`; the corner nearest the sender collapses to `sm` to point at
the author. Avatars and unread pills use `full`.

## Typography

Inter throughout. Sizes and line heights are variables (`--font-size-*`,
`--line-height-*`) and the 13 text styles below bind to them, so changing the scale
changes every style.

| Style | Weight | Size / line height | Use |
| --- | --- | --- | --- |
| `Display/Large` | Bold | 32 / 32 | Auth screen wordmark |
| `Heading/XL` | Semi Bold | 24 / 32 | Page titles |
| `Heading/L` | Semi Bold | 20 / 24 | Panel titles |
| `Heading/M` | Semi Bold | 16 / 24 | Section headers, chat name |
| `Body/Large` | Regular | 16 / 24 | Long-form copy |
| `Body/Default` | Regular | 14 / 20 | Message text, inputs |
| `Body/Default Medium` | Medium | 14 / 20 | Conversation names |
| `Body/Small` | Regular | 13 / 18 | Message previews |
| `Label/Default` | Medium | 13 / 18 | Buttons, field labels |
| `Label/Small` | Medium | 12 / 16 | Chips, badges |
| `Caption` | Regular | 12 / 16 | Helper text |
| `Meta/Timestamp` | Regular | 11 / 16 | Timestamps |
| `Meta/Timestamp Strong` | Medium | 11 / 16 | Unread timestamps |

## Elevation

| Style | Shadow | Use |
| --- | --- | --- |
| `Elevation/XS` | `0 1 2 rgba(0,0,0,.06)` | Resting cards |
| `Elevation/SM` | `0 2 6 rgba(0,0,0,.08)` | Composer, sticky headers |
| `Elevation/MD` | `0 4 12 rgba(0,0,0,.10)` | Dropdowns, popovers |
| `Elevation/LG` | `0 8 24 rgba(0,0,0,.14)` | Modals |

## Rules that are not negotiable

1. **No colour-only status.** `SENT` / `DELIVERED` / `READ` must differ by glyph
   (single tick, double tick, filled double tick), not just hue — brief §6, §19.
2. **Focus is always visible.** 2px `border/focus` ring on every interactive element.
3. **Contrast.** Body text on its background meets 4.5:1; `text/secondary` on
   `bg/surface` and `text/tertiary` on `bg/canvas` were chosen against that bar.
4. **Presence is never inferred.** `status/online` renders a dot *and* a text
   last-seen string, so it survives greyscale.
