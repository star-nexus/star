# STARBench UI polish — v3

Date: 2026-10-11. Branch: `codex/ui-polish`, starting at `65941ef`.

## Current picture and inherited boundary

Read the root README, `starbench-ui.md`, `window-runtime-rendering.md`,
`native-runtime.md`, `native-hub-host.md` and the performance measurement/window
workload documents before implementation. The branch includes the Rust authority,
Hub adoption, unified launcher and v2 scene-owned paint caches. The current menu
and selected/help battlefield were captured at four exact sizes before editing.

The v2 layout already separates map and sidebar and shares paint/hit rectangles.
Its slate/gold theme is coherent, but unselected menu choices float in a large
panel, the start action has little emphasis, and headings, values and actions
have similar visual weight. The selected-unit panel is mostly undifferentiated
text. Preserve the readable existing terrain/sprites, tactical meanings and
faction color/shape pairs.

The old Lab v2 captures say Rust Hub is unavailable. That is historical: the
current branch enables External Agent / Hub. The menu and connection indicators
must continue to describe the current capability and actual registration facts.

## Implementation

1. Refine the existing slate/gold palette and panel hierarchy. Give menu choices
   clear resting, selected and disabled states, use a restrained hex motif, and
   emphasize Start Game. Keep every existing hit rectangle and scenario scroll.
2. Refine the HUD brand, legend, section headers and keyboard chips. Add a visual
   strength meter alongside the existing numeric facts. Keep the same viewport,
   action availability, selection, input ownership, fonts and minimum size.
3. Keep decoration inside the bounded scene-owned widget cache. Keys contain
   current visual facts; drawing remains on the display thread. Preserve terrain
   overscan, spatial culling, incremental Fog, ordered render batching, the native
   owner, ordered display deltas and all adopted native optimizations.
4. Record `starbench-ui-v3` centrally. Existing runtime manifests and profiler
   metadata read that constant. VLM uses the same full paint path, so its pixels
   change; permissions, global view/camera policy, historical encoding/label,
   protocol fields and authority schema retain the existing contract.

## Verification and evidence

Use the existing UI/input, native session/Hub and portable performance contracts.
Capture menu/selected/help at 1200×800, 1440×900, 1920×1080 and 2480×1263. Compare
the full authority before/after pure paint, and use the existing Cocoa smoke for
both backends and Rust VLM/window pixel parity. Preserve exact-size QA separately
from real-window evidence.

Compare the same full-paint frozen Rust projection before/after (15 and 5000
resident units; 10s warmup + 30s measurement), retaining frame samples and native
extension identity. Existing finite draw guards are mean ratio ≤1.05 and P99
ratio ≤1.10. These checks do not establish active-world/network capacity or an
end-to-end latency improvement.

Implementation and verification results are recorded in `starbench-ui.md`.

## v4 follow-up: excessive startup margins

The user's actual startup screenshot exposed a gap in the v3 finite previews:
they pinned a tactical camera and did not assess the ordinary default window
and opening whole-board view. Cocoa reproduction confirmed a 2480×1235 startup
with a 2070-pixel-wide viewport. Keep the v3 evidence as history.

Use compact 1200×900 automatic startup, fit actual tile corners after sidebar
layout, and share a deep-slate clear colour between window, opaque terrain and
native screenshot paint. Fit only once; preserve user camera through resize and
native handoff. Keep rules, Fog, game/Agent controls and protocol contracts.
Record v4 and add natural opening views to exact-size QA, alongside a real Cocoa
startup reproduction, both-backend interactive smoke, pixel/authority guards,
window/framing geometry tests and existing portable performance checks.

## v5 follow-up: terrain quality regression

The user rejected the heavy black grid and map texture in v4. Reusing the UI
background for opaque terrain composition made transparent tile seams dark.
Restore the original grass clear colour across window, terrain and screenshot
paint, with UI colours independent. Keep compact startup and viewport framing.
Record v5, inspect actual Cocoa and selected-view captures, and verify terrain
pixel composition plus native VLM/window equality and authority preservation.

## v6 follow-up: missing toolbar press feedback

Connect display-only press/release/motion state to the existing cached button
painter. Darken and depress the face and label by 2 pixels, with 120 ms minimum
feedback for down/up events in the same frame. Preserve mouse-down callbacks and
shared hit rectangles; cancel stale feedback on drag-out, disabled/hidden state
or scene exit. Keep cache keys discrete and bounded. Record v6 and verify quick
click, hold/release, lifecycle, real Cocoa frames and native screenshot/authority
parity alongside UI/input/Hub/protocol/render regression checks.

## End Turn follow-up: toolbar bypassed human resource reset

Route the Python toolbar into the same TurnSystem.end_turn call used by Space;
route the native toolbar into the same LocalControls.finish_turn call. Keep the
native binary and legacy API command intact, but stop dispatching its incomplete
manager rotation from the visible UI. Test spent AP, effective movement reset,
faction/round progression, statistics/events and failure guards across Python and
native serial/threaded authority. Preserve Agent handoff/reset timing, rendering
version v6, press feedback and the no-input screenshot paint path.
