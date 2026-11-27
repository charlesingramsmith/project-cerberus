"""Hand-drawn icons in the style of the logo (a pencil sketch), used instead of emoji.

Each icon is a few pencil strokes on a 24x24 grid. `svg()` gives an inline picture for
HTML the app writes itself (life list, badges, Social posts), coloured by the text
around it. `data_uri()` gives a standalone copy for CSS, where it's used as a mask so
the icon takes the colour of whatever it's on (the bottom tab bar, the photo button).

To add an icon: add its strokes to SKETCHES (stroke="currentColor" and fill="none" are
set for you; give solid bits fill="currentColor"). Every icon is drawn twice, the second
time lighter and slightly shifted, which is what makes it look sketched in pencil.
"""
from __future__ import annotations

import base64

# The logo's dachshund head (assets/logo.svg), shrunk to fit the 24x24 grid.
_DOG = (
    '<svg x="1" y="0.5" width="22" height="23" viewBox="0 0 180 200">'
    '<path stroke-width="10" d="M158 192 C160 160 168 128 160 100 C154 78 140 60 118 56 '
    "C100 53 86 60 78 72 C66 80 46 86 26 92 C16 95 12 104 18 110 C26 118 44 120 62 122 "
    'C76 124 88 132 96 142 C104 156 108 174 108 192"/>'
    '<path stroke-width="9.5" d="M112 70 C128 66 142 78 144 98 C147 122 142 146 130 156 '
    'C120 164 106 158 104 146 C101 128 104 104 110 84"/>'
    '<ellipse cx="74" cy="88" rx="9" ry="8" fill="currentColor" stroke="none"/>'
    '<ellipse cx="20" cy="100" rx="13" ry="11" fill="currentColor" stroke="none"/>'
    "</svg>"
)


def _paw(x: float, y: float, scale: float) -> str:
    return (
        f'<g transform="translate({x} {y}) scale({scale})">'
        '<ellipse cx="12" cy="15.5" rx="4.2" ry="3.4"/>'
        '<circle cx="6.8" cy="10" r="1.7"/><circle cx="10" cy="6.8" r="1.8"/>'
        '<circle cx="14" cy="6.8" r="1.8"/><circle cx="17.2" cy="10" r="1.7"/></g>'
    )


SKETCHES: dict[str, str] = {
    # --- the bottom tab bar ---
    "binoculars": (  # Spotted!
        '<circle cx="7.4" cy="15" r="3.6"/><circle cx="16.6" cy="15" r="3.6"/>'
        '<path d="M4.4 12.6 L6 5.5 h3.2 L10.6 12"/><path d="M13.4 12 L14.8 5.5 h3.2 L19.6 12.6"/>'
        '<path d="M10.8 13.4 h2.4"/>'
    ),
    "notebook": (  # Life list
        '<path d="M6 3.5 h11 a1.5 1.5 0 0 1 1.5 1.5 v14 a1.5 1.5 0 0 1 -1.5 1.5 h-11 z"/>'
        '<path d="M8.6 3.6 v16.8"/><path d="M11 8.2 l1.3 1.4 L15.4 6.4"/>'
        '<path d="M11 13 h5"/><path d="M11 16.5 h3.8"/>'
    ),
    "person": (  # Profile
        '<circle cx="12" cy="8" r="3.6"/><path d="M5 20.2 c.6-4 3.4-6.2 7-6.2 s6.4 2.2 7 6.2"/>'
    ),
    "people": (  # Social
        '<circle cx="9" cy="8.6" r="3"/><path d="M3.4 19.6 c.5-3.5 2.8-5.2 5.6-5.2 s5.1 1.7 5.6 5.2"/>'
        '<circle cx="16.6" cy="9.4" r="2.4"/><path d="M15.4 14.4 c2.6-.2 4.8 1.4 5.3 4.6"/>'
    ),
    "sliders": (  # Settings
        '<path d="M4 7 h16"/><path d="M4 12 h16"/><path d="M4 17 h16"/>'
        '<circle cx="9" cy="7" r="1.9" fill="currentColor"/>'
        '<circle cx="15.5" cy="12" r="1.9" fill="currentColor"/>'
        '<circle cx="7" cy="17" r="1.9" fill="currentColor"/>'
    ),
    # --- around the app ---
    "dog": _DOG,
    "camera": (
        '<path d="M3.5 8.5 a1.5 1.5 0 0 1 1.5-1.5 h2.6 l1.5-2.1 h5.8 l1.5 2.1 h2.6 '
        'a1.5 1.5 0 0 1 1.5 1.5 v9.2 a1.5 1.5 0 0 1 -1.5 1.5 h-14 a1.5 1.5 0 0 1 -1.5-1.5 z"/>'
        '<circle cx="12" cy="12.8" r="3.4"/>'
    ),
    "swap": (
        '<path d="M5 10.5 a7 7 0 0 1 12.4-3.6"/><path d="M17.8 3.4 v3.8 h-3.8"/>'
        '<path d="M19 13.5 a7 7 0 0 1 -12.4 3.6"/><path d="M6.2 20.6 v-3.8 h3.8"/>'
    ),
    "check": '<path d="M5 12.6 l4.2 4.4 L19 6.6"/>',
    "magnifier": '<circle cx="10.4" cy="10.4" r="5.8"/><path d="M14.7 14.7 L20.2 20.2"/>',
    "sparkle": (
        '<path d="M12 3.5 c.7 4.4 2.1 5.8 6.5 6.5 c-4.4 .7-5.8 2.1-6.5 6.5 '
        'c-.7-4.4-2.1-5.8-6.5-6.5 c4.4-.7 5.8-2.1 6.5-6.5 z"/><path d="M18.5 16.5 v4"/>'
        '<path d="M16.5 18.5 h4"/>'
    ),
    "bulb": (
        '<path d="M9 15.6 c-2-1.4-3-3.3-3-5.6 a6 6 0 0 1 12 0 c0 2.3-1 4.2-3 5.6 v2.2 h-6 z"/>'
        '<path d="M9.6 20.6 h4.8"/>'
    ),
    "heart": (
        '<path d="M12 19.6 C5 14.6 3.4 11 4.4 8 c1-3 5-3.8 7.6-.5 '
        'c2.6-3.3 6.6-2.5 7.6.5 c1 3-.6 6.6-7.6 11.6 z"/>'
    ),
    "pin": (
        '<path d="M12 21 c-4-5-6-8-6-11.2 a6 6 0 0 1 12 0 c0 3.2-2 6.2-6 11.2 z"/>'
        '<circle cx="12" cy="9.8" r="2.2"/>'
    ),
    "pencil": (
        '<path d="M4.5 19.5 l1-4.6 L15.4 5 a2.1 2.1 0 0 1 3 3 L8.6 18 z"/>'
        '<path d="M13.4 7 l3 3"/>'
    ),
    "plus": '<path d="M12 5 v14"/><path d="M5 12 h14"/>',
    "bin": (
        '<path d="M5 7 h14"/><path d="M9.6 7 V4.6 h4.8 V7"/>'
        '<path d="M6.6 7 l1 12.6 h8.8 l1-12.6"/><path d="M10.2 10.6 v6"/><path d="M13.8 10.6 v6"/>'
    ),
    "warning": (
        '<path d="M12 4 L21 19.6 H3 Z"/><path d="M12 10 v4.6"/>'
        '<circle cx="12" cy="17.2" r=".9" fill="currentColor"/>'
    ),
    # --- badges (logic.BADGES) ---
    "paw": _paw(0, 0, 1),
    "bone": (
        '<path d="M8.6 7.3 L16.7 15.4"/><path d="M7.3 8.6 L15.4 16.7"/>'
        '<circle cx="5.6" cy="7.6" r="1.9"/><circle cx="7.6" cy="5.6" r="1.9"/>'
        '<circle cx="16.4" cy="18.4" r="1.9"/><circle cx="18.4" cy="16.4" r="1.9"/>'
    ),
    "lead": (
        '<path d="M6 3.6 c-3.2 0-3.2 6.2 0 6.2 c3.2 0 3.2-6.2 0-6.2"/>'
        '<path d="M7.4 9.2 C9.8 14.4 14 12 16.2 16.6"/><circle cx="17" cy="18.4" r="1.8"/>'
    ),
    "frisbee": (
        '<ellipse cx="13" cy="14" rx="8" ry="3.6"/><ellipse cx="13" cy="13.4" rx="4.4" ry="1.7"/>'
        '<path d="M2.6 8 h4.4"/><path d="M4.6 5 h4.4"/>'
    ),
    "ball": (
        '<circle cx="12" cy="12" r="7.6"/><path d="M5.2 8.6 c3.2 1.2 4 5.2 1.4 8.6"/>'
        '<path d="M18.8 15.4 c-3.2-1.2-4-5.2-1.4-8.6"/>'
    ),
    "sun": (
        '<circle cx="12" cy="12" r="4"/><path d="M12 2.8 v2.4"/><path d="M12 18.8 v2.4"/>'
        '<path d="M2.8 12 h2.4"/><path d="M18.8 12 h2.4"/><path d="M5.5 5.5 l1.7 1.7"/>'
        '<path d="M16.8 16.8 l1.7 1.7"/><path d="M5.5 18.5 l1.7-1.7"/><path d="M16.8 7.2 l1.7-1.7"/>'
    ),
    "nose": (
        '<path d="M5.6 9.6 c0-3.2 12.8-3.2 12.8 0 c0 3.2-3.4 6-6.4 6 s-6.4-2.8-6.4-6 z"/>'
        '<ellipse cx="9.6" cy="10.4" rx="1.2" ry=".8" fill="currentColor"/>'
        '<ellipse cx="14.4" cy="10.4" rx="1.2" ry=".8" fill="currentColor"/>'
        '<path d="M12 15.6 v2.8"/><path d="M8.8 19.4 c1.6 1.1 4.8 1.1 6.4 0"/>'
    ),
    "tracks": _paw(1, 11, .5) + _paw(5.5, 5.5, .5) + _paw(11, 9.5, .5) + _paw(13.5, 1.5, .5),
    "zoom": (
        '<path d="M2.6 8 h7"/><path d="M4.6 12 h6"/><path d="M2.6 16 h7"/>'
        '<circle cx="16.6" cy="12" r="3.8"/>'
    ),
    "medal": (
        '<path d="M8.4 3 l3 7"/><path d="M15.6 3 l-3 7"/><circle cx="12" cy="15.2" r="5"/>'
        '<circle cx="12" cy="15.2" r="2.4"/>'
    ),
    "rosette": (
        '<circle cx="12" cy="9" r="5.4"/><circle cx="12" cy="9" r="2.6"/>'
        '<path d="M9.4 13.8 L8 21 L10.4 19.6 L11.6 14.4"/><path d="M14.6 13.8 L16 21 L13.6 19.6 L12.4 14.4"/>'
    ),
    "moon": (
        '<path d="M14.6 4 a8 8 0 1 0 5.6 12.6 a6.6 6.6 0 1 1 -5.6 -12.6 z"/>'
        '<path d="M19 4 v3"/><path d="M17.5 5.5 h3"/>'
    ),
    "compass": (
        '<circle cx="12" cy="12" r="8.4"/><path d="M12 6.4 L14.2 12 L12 17.6 L9.8 12 Z"/>'
        '<path d="M12 6.4 L14.2 12 H9.8 Z" fill="currentColor"/>'
    ),
    "kennel": (
        '<path d="M3.6 11.4 L12 4.4 L20.4 11.4"/><path d="M5.6 9.8 v9.8 h12.8 V9.8"/>'
        '<path d="M9.4 19.6 v-3.6 a2.6 2.6 0 0 1 5.2 0 v3.6"/>'
    ),
    "tail": (
        '<path d="M4.4 18.6 C9 18.6 12 15.4 13 10.4 C14 6.2 16.8 4 19.6 5"/>'
        '<path d="M17 9.6 c1.2.4 2 1.4 2.3 2.6"/><path d="M20 8 c.8.6 1.3 1.4 1.4 2.2"/>'
    ),
    "star": (
        '<path d="M12 3.4 l2.6 5.5 6 .8 -4.4 4.1 1.1 5.9 L12 16.8 6.7 19.7 l1.1-5.9 '
        '-4.4-4.1 6-.8 z"/>'
    ),
    "target": (
        '<circle cx="11" cy="13" r="7.6"/><circle cx="11" cy="13" r="4.4"/>'
        '<circle cx="11" cy="13" r="1.4" fill="currentColor"/>'
        '<path d="M12.4 11.6 L20.4 3.6"/><path d="M17.2 3.6 h3.2 v3.2"/>'
    ),
    "dogstar": (
        '<path d="M4.6 17 L9.6 9.6 L15 12.6 L19.4 4.8"/>'
        '<circle cx="4.6" cy="17" r="1.5" fill="currentColor"/>'
        '<circle cx="9.6" cy="9.6" r="1.5" fill="currentColor"/>'
        '<circle cx="15" cy="12.6" r="1.5" fill="currentColor"/>'
        '<circle cx="19.4" cy="4.8" r="1.5" fill="currentColor"/><path d="M15 17 l2 2.4"/>'
    ),
    "first": (
        '<path d="M8.4 3 l2.8 6.4"/><path d="M15.6 3 l-2.8 6.4"/><circle cx="12" cy="14.8" r="5.6"/>'
        '<path d="M10.8 13.4 l1.6-1.4 v5.8"/>'
    ),
    "trophy": (
        '<path d="M7.4 4 h9.2 v4.6 a4.6 4.6 0 0 1 -9.2 0 z"/>'
        '<path d="M7.4 6 h-2 a2.2 2.2 0 0 0 2.2 4"/><path d="M16.6 6 h2 a2.2 2.2 0 0 1 -2.2 4"/>'
        '<path d="M12 13.2 v3.4"/><path d="M9.4 16.6 h5.2 v3.4 h-5.2 z"/><path d="M8 20 h8"/>'
    ),
    "suitcase": (
        '<path d="M4 8.4 h16 v10.4 a1.4 1.4 0 0 1 -1.4 1.4 h-13.2 a1.4 1.4 0 0 1 -1.4-1.4 z"/>'
        '<path d="M9 8.4 V5.4 h6 v3"/><path d="M8 8.6 v11.4"/><path d="M16 8.6 v11.4"/>'
    ),
    "map": (
        '<path d="M3.6 6.4 L9 4.2 L15 6.6 L20.4 4.4 v13.2 L15 19.8 L9 17.4 L3.6 19.6 z"/>'
        '<path d="M9 4.4 v13"/><path d="M15 6.8 v13"/>'
    ),
    "telescope": (
        '<path d="M4 13.6 L16.8 6.4 l1.8 3.2 L5.8 16.8 z"/><path d="M18.6 9.6 l2-1.1"/>'
        '<path d="M16.6 6.6 l2-1.1"/><path d="M11 13.4 L8.4 20.4"/><path d="M11 13.4 L14.4 20.4"/>'
    ),
    "gem": (
        '<path d="M7 4.6 h10 l3.4 4.6 L12 20 L3.6 9.2 z"/><path d="M3.6 9.2 h16.8"/>'
        '<path d="M9.6 4.8 L8.4 9.2 L12 20 L15.6 9.2 L14.4 4.8"/>'
    ),
    "crown": (
        '<path d="M3.6 17.6 L2.8 7.6 L8 11.6 L12 5 L16 11.6 L21.2 7.6 L20.4 17.6 z"/>'
        '<path d="M4 20.2 h16"/>'
    ),
}


# A slight wobble in every line, as if drawn by hand (the logo's "pencil" filter, scaled
# down to icon size). Every inline icon carries its own copy under the same id; they're
# identical, so it doesn't matter which one the browser uses.
_WOBBLE = ('<filter id="cerb-wobble" x="-10%" y="-10%" width="120%" height="120%">'
           '<feTurbulence type="fractalNoise" baseFrequency="0.22" numOctaves="2" seed="3"/>'
           '<feDisplacementMap in="SourceGraphic" scale="0.9" xChannelSelector="R" '
           'yChannelSelector="G"/></filter>')


def _strokes(name: str) -> str:
    """The icon drawn twice: once firmly, once lighter and a fraction off, like pencil."""
    body = SKETCHES[name]
    return (f'<defs>{_WOBBLE}</defs><g filter="url(#cerb-wobble)">'
            f'<g stroke-width="1.45">{body}</g>'
            f'<g stroke-width=".75" opacity=".45" transform="translate(.6 -.45)">{body}</g></g>')


def svg(name: str, css: str = "sketch") -> str:
    """An inline sketch for the app's own HTML. It takes the colour of the text around it
    and is 1.2em square unless the class `css` says otherwise (see MOBILE_CSS)."""
    return (f'<svg class="{css}" viewBox="0 0 24 24" aria-hidden="true" fill="none" '
            f'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">'
            f"{_strokes(name)}</svg>")


def data_uri(name: str) -> str:
    """A standalone black copy as a base64 data URI, for CSS `mask-image` (base64, so the
    stylesheet has no "<" in it: st.html drops a stylesheet that does)."""
    picture = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               f'stroke="black" stroke-linecap="round" stroke-linejoin="round" color="black">'
               f"{_strokes(name)}</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(picture.encode()).decode()
