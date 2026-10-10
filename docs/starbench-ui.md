# STARBench window UI

The ordinary Python and Rust pygame window uses visual version `starbench-ui-v2`.
Launch commands and Agent access through star-protocol retain their existing
fields, encoding and permissions. Existing terrain and unit art is retained.

The menu displays STARBench, game mode, factions, controller and scenario. Static
slots have no automatic controller. Rust's current offline window disables the
unconnected Hub and local BOT options; this UI change does not add either backend.
The status bar reports the backend, controller, actual Hub connection and
registered Agent count (registration is not a claim that an Agent is thinking).

The battlefield has a map viewport and a separate right sidebar containing the
mini-map, selection, actions and collapsible battle log. Scroll over the sidebar
to reach its lower content; scroll over the map to zoom at the pointer. Windows
retain the 1200×800 minimum. Resizing preserves the world point at the viewport
centre. Labels use high contrast; distant/dense views prioritize selected and
hovered units. Wei uses a blue circle, Shu a red diamond and Wu a green triangle.
Blue translucent hexes indicate reachable cells. Gold outlines show geometric
attack range, not guaranteed permission to attack; enemy markers are outlines.

| Key | Action |
|---|---|
| 1 / 2 | Select a living human infantry / cavalry unit |
| 3 / 4 / 5 | Select distinct living human archers, in entity-ID order |
| M / A | Choose a move / attack target |
| W / G / C / F | Existing Wait / Garrison / Capture / Fortify actions |
| Arrows; + / − | Pan; zoom the camera |
| Shift+1 | Existing global Fog toggle |
| Shift+2 / 3 / 4 | Wei / Shu / Wu spectator view |
| Esc | Close a modal, otherwise cancel targeting, then selection |
| F1 / Tab | Help / statistics |

A missing number slot keeps the current selection. Action keys use the existing
panel availability and execution methods. Attack-target mode does not turn an
empty-ground click into movement. HUD backgrounds and modals consume clicks;
right-click on the map clears targeting and selection. F1 and CLI help derive
from the same binding table as input and action-button hints.

A scene-owned `UiContext` supplies layout, theme, input ownership and bounded
pygame caches. It lives outside authority/schema. Tactical surfaces use SRCALPHA
and are bounded to 128 entries and 32 MiB; text to 1024 entries and 8 MiB. Static panels and action rows use a separate
128-entry / 8 MiB cache keyed only by their visual content. Exit
releases these caches. Render commands snapshot nested clipping, keep painter
order and batch only adjacent blits with identical clips. SDL, fonts, painting
and screenshots run on the display thread; Rust's single authority owner and
ordered delta consumer are retained.

VLM capture uses the same complete paint path, including toolbar/action controls,
without admitting input or advancing authority. Its actual picture therefore
changes with this visual version. The pre-existing global screen/view contract,
frame encoding and protocol fields are unchanged. Record the visual version when
comparing image-based benchmark runs. This is not a new per-Agent camera policy.

Finite UI acceptance and raw evidence are recorded in STAR Lab's
`experiments/2026-10-ui-refresh`; render checks are fixed-projection regressions,
not a new throughput or capacity claim.
