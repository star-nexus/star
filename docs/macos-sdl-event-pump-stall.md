# macOS / SDL event-pump tail latency

STAR's interactive Pygame window can show rare long frames on macOS while the user is generating heavy keyboard and mouse input. This is a platform/SDL event-pump stall, not a STAR simulation or input-dispatch bottleneck.

## What happens

In affected frames, `pygame.event.pump()` can block for tens of milliseconds even when only one or a few input events are returned. Normal frames spend roughly `0.1 ms` in the pump, but stress testing has captured isolated `50–60 ms` stalls.

The issue was originally observed inside `pygame.event.get()`. STAR's profiler then split that call into three stages:

```text
pygame.event.pump()              -> input_event_pump
pygame.event.get(pump=False)     -> input_event_get_queue
STAR EventBus dispatch           -> input_dispatch
```

A representative 200-unit run on macOS with Pygame 2.6.1 / SDL 2.28.4 / Python 3.13.12 captured:

```text
frame_ms=62.75
input_event_pump=54.76ms
input_event_get_queue≈0.01ms
input_dispatch≈0.01ms
input_events=1
input_key_down=1
```

This isolates the tail to SDL/Cocoa platform-event pumping. Queue retrieval and STAR's callbacks remain negligible.

## Mitigation already applied

STAR disables SDL text input during normal gameplay with `pygame.key.stop_text_input()`. Gameplay only needs physical key state/events, mouse events, and window events. This reduced the frequency of the macOS stalls and avoids an unnecessary InputMethodKit/IME path. Future text widgets should explicitly enable text input only while focused.

Do **not** move the SDL event pump to a worker thread or stop pumping events to hide this latency. On macOS the window/event loop is expected to be serviced normally on the main thread. For benchmark-scale experiments where interactive rendering is unnecessary, prefer headless mode.

## Reproduction

1. On macOS, run an interactive profiled game, for example:

   ```bash
   uv run rotk_env/main.py --profile
   ```

2. Start a large real-time match (the issue was reproduced with a 33×33 map and 200 units).
3. Continuously pan/zoom with the keyboard while rapidly clicking units and issuing movement commands with the mouse.
4. Let the run continue for hundreds or thousands of frames.
5. Inspect `[SLOW FRAME]` blocks. Ignore startup/menu frames; the gameplay profiler epoch is reset after the match initializes.

If a slow frame is dominated by `input_event_pump` while `input_event_get_queue` and `input_dispatch` remain near zero, it is this known platform tail.

## Scope

This is tracked as a known macOS + SDL/Pygame interactive-window limitation. It should not be re-diagnosed as a STAR renderer, pathfinding, agent, or simulation regression unless the timing attribution changes.