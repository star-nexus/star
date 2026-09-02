"""Scale measurement overlay for render-tail and realtime-GC diagnostics.

The stable experiment mechanics remain in ``scale_experiment_measurement_base``.
This overlay adds three orthogonal concerns:
- retain UnitRender/GC tail metrics in compact slow-frame snapshots;
- provide an explicit A/B realtime cyclic-GC policy for sustained runs;
- make large profiler-snapshot replies reliable on the harness' non-blocking UDS.

Normal behavior remains ``gc_policy=auto``. ``realtime_defer`` is opt-in until
formal A/B results establish that it should become a production realtime policy.
For fresh-process formal runs it can also be selected with
``STAR_SCALE_GC_POLICY=realtime_defer`` without changing scale_driver commands.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from framework.utils.realtime_gc_policy import (
    GC_POLICY_AUTO,
    GC_POLICY_REALTIME_DEFER,
    RealtimeGCPolicy,
    normalize_gc_policy,
)

from . import scale_experiment_measurement_base as _base

_original_compact_slow_frame = _base._compact_slow_frame

_RENDER_ENGINE_SECTIONS = (
    "render_queue_prepare",
    "render_queue_submit",
    "render_batch_pack",
    "render_batch_blits",
    "render_scalar_execute",
    "render_queue_clear",
)
for _section in _RENDER_ENGINE_SECTIONS:
    if _section not in _base._RELEVANT_SECTIONS:
        _base._RELEVANT_SECTIONS += (_section,)

_TAIL_METRICS = (
    "render_commands",
    "render_layers",
    "render_simple_blits",
    "render_blit_batches",
    "render_batch_runs",
    "render_single_plain_blits",
    "render_nonbatch_blits",
    "render_draw_commands",
    "render_other_commands",
    "render_scalar_commands",
    "render_max_batch_size",
    "render_pixel_metrics_enabled",
    "render_plain_blit_source_pixels",
    "render_plain_blit_clipped_pixels",
    "render_plain_blit_max_surface_pixels",
    "render_plain_blit_max_batch_source_pixels",
    "render_plain_blit_max_batch_clipped_pixels",
    "unit_static_groups",
    "unit_static_candidate_units",
    "unit_static_submitted_units",
    "unit_static_max_group_size",
    "unit_static_multi_groups",
    "unit_animated_draw_units",
    "unit_static_commands_added",
    "unit_animated_commands_added",
    "unit_render_commands_added",
    "unit_gc_collections",
    "unit_gc_pause_ms",
    "unit_gc_gen0_collections",
    "unit_gc_gen1_collections",
    "unit_gc_gen2_collections",
    "unit_gc_gen0_pause_ms",
    "unit_gc_gen1_pause_ms",
    "unit_gc_gen2_pause_ms",
    "unit_gc_static_draw_pause_ms",
    "unit_gc_animated_draw_pause_ms",
    "unit_gc_other_pause_ms",
    "unit_gc_collected_objects",
    "unit_gc_uncollectable_objects",
    "unit_gc_count0_start",
    "unit_gc_count0_end",
    "unit_gc_count1_start",
    "unit_gc_count1_end",
    "unit_gc_count2_start",
    "unit_gc_count2_end",
    "gc_policy_mode",
    "gc_policy_active",
    "gc_automatic_enabled",
    "gc_policy_deadline_remaining_seconds",
)


def _compact_slow_frame(snapshot):
    result = _original_compact_slow_frame(snapshot)
    if result is None or not isinstance(snapshot, dict):
        return result

    source_metrics = snapshot.get("frame_metrics", {})
    target_metrics = result.setdefault("frame_metrics", {})
    if isinstance(source_metrics, dict):
        for key in _TAIL_METRICS:
            if key in source_metrics:
                target_metrics[key] = source_metrics[key]
    return result


_base._compact_slow_frame = _compact_slow_frame


def _policy_matches(requested: str, state: Dict[str, Any]) -> bool:
    if requested == GC_POLICY_AUTO:
        return state.get("mode") == GC_POLICY_AUTO and not bool(state.get("active"))
    if requested == GC_POLICY_REALTIME_DEFER:
        return (
            state.get("mode") == GC_POLICY_REALTIME_DEFER
            and bool(state.get("active"))
            and not bool(state.get("automatic_gc_enabled"))
        )
    return False


def _requested_policy(command: Dict[str, Any]) -> str:
    value = command.get("gc_policy")
    if value is None:
        value = os.environ.get("STAR_SCALE_GC_POLICY", GC_POLICY_AUTO)
    return normalize_gc_policy(value)


def _install_reliable_socket_output(harness) -> None:
    """Replace fragile non-blocking ``sendall`` with buffered partial writes.

    ``ScaleHarnessSystem`` accepts clients in non-blocking mode. Calling
    ``sendall`` on such a socket is not guaranteed to finish a large profiler
    snapshot; ``BlockingIOError`` means "try the remaining bytes later", not
    "the peer disconnected". The legacy path treated it as disconnect and
    closed the client, which surfaced in scale_driver as:

        scale harness closed the socket before replying

    Keep command reads non-blocking, but queue response bytes per client and
    drain them with ``send`` across update ticks. Local small replies still
    normally complete immediately in one call.
    """
    if bool(getattr(harness, "_scale_reliable_socket_output_installed", False)):
        return

    original_drop = getattr(harness, "_drop_client", None)
    pending: Dict[object, bytearray] = {}
    harness._scale_pending_output = pending

    def _drop_client(client) -> None:
        pending.pop(client, None)
        if callable(original_drop):
            original_drop(client)
            return
        try:
            client.close()
        except OSError:
            pass

    def _flush_client(client) -> None:
        buffer = pending.get(client)
        if not buffer:
            pending.pop(client, None)
            return

        while buffer:
            try:
                sent = client.send(buffer)
            except BlockingIOError:
                # Socket back-pressure is expected for non-blocking clients.
                # Retain the unsent suffix and continue on the next update tick.
                return
            except (BrokenPipeError, OSError):
                _drop_client(client)
                return

            if sent <= 0:
                _drop_client(client)
                return
            del buffer[:sent]

        pending.pop(client, None)

    def _flush_all() -> None:
        for client in list(pending):
            _flush_client(client)

    def _send_response(client, response: Dict[str, Any]) -> None:
        payload = (
            json.dumps(response, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        pending.setdefault(client, bytearray()).extend(payload)
        _flush_client(client)

    harness._drop_client = _drop_client
    harness._send_response = _send_response
    harness._flush_scale_socket_output = _flush_all
    harness._scale_reliable_socket_output_installed = True


def install_scale_experiment_measurement(harness, world, profiler) -> bool:
    """Install base measurement plus bounded realtime-GC A/B control."""
    if bool(getattr(harness, "_scale_gc_policy_installed", False)):
        return True
    if not _base.install_scale_experiment_measurement(harness, world, profiler):
        return False

    _install_reliable_socket_output(harness)

    policy = RealtimeGCPolicy()
    harness._realtime_gc_policy = policy
    original_handle = harness.handle_command
    original_update = getattr(harness, "update", None)
    original_cleanup = getattr(harness, "cleanup", None)

    def _publish_policy_frame_metrics() -> Dict[str, Any]:
        state = policy.snapshot()
        metric = getattr(profiler, "set_frame_metric", None)
        if callable(metric):
            metric("gc_policy_mode", state["mode"])
            metric("gc_policy_active", int(bool(state["active"])))
            metric(
                "gc_automatic_enabled",
                int(bool(state["automatic_gc_enabled"])),
            )
            remaining = state.get("deadline_remaining_seconds")
            metric(
                "gc_policy_deadline_remaining_seconds",
                float(remaining) if remaining is not None else -1.0,
            )
        return state

    def _record_policy_metadata(state: Dict[str, Any]) -> None:
        setter = getattr(profiler, "set_metadata", None)
        if not callable(setter):
            return
        setter(
            scale_gc_policy=state["mode"],
            scale_gc_policy_active=bool(state["active"]),
            scale_gc_automatic_enabled=bool(state["automatic_gc_enabled"]),
            scale_gc_full_collect_ms=state["full_collect_ms"],
            scale_gc_full_collect_collected=state["full_collect_collected"],
        )

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()

        if op == "start_sustained_batch":
            try:
                requested_policy = _requested_policy(command)
            except ValueError as exc:
                return {
                    "ok": False,
                    "error": "invalid_gc_policy",
                    "message": str(exc),
                }

            # A manual restart should never inherit a previous deferred-GC window.
            policy.restore("restart")
            result = original_handle(command)
            if not result.get("ok"):
                return result

            # Base kickoff and plan selection are complete here, while its
            # measurement epoch reset is still deferred until the next safe frame
            # boundary. Collect now so kickoff allocation and this full collection
            # are both excluded from the formal realtime epoch.
            duration = float(
                result.get(
                    "duration_seconds", command.get("duration_seconds", 20.0)
                )
            )
            gc_state = policy.activate(requested_policy, duration)
            measurement_state = getattr(harness, "_scale_measurement_state", None)
            if isinstance(measurement_state, dict):
                measurement_state["gc_policy"] = requested_policy
                measurement_state["gc_full_collect_ms"] = gc_state["full_collect_ms"]
                measurement_state["gc_full_collect_collected"] = gc_state[
                    "full_collect_collected"
                ]

            _record_policy_metadata(gc_state)
            _publish_policy_frame_metrics()
            result.update(
                gc_policy=requested_policy,
                gc_policy_active=gc_state["active"],
                gc_automatic_enabled=gc_state["automatic_gc_enabled"],
                gc_full_collect_ms=gc_state["full_collect_ms"],
                gc_full_collect_collected=gc_state["full_collect_collected"],
            )
            return result

        if op == "profile_snapshot":
            policy.tick()
            result = original_handle(command)
            if not result.get("ok"):
                return result
            gc_state = _publish_policy_frame_metrics()
            measurement_state = getattr(harness, "_scale_measurement_state", None) or {}
            requested_policy = normalize_gc_policy(
                measurement_state.get("gc_policy", GC_POLICY_AUTO)
            )
            policy_matches = _policy_matches(requested_policy, gc_state)
            guards = result.setdefault("guards", {})
            guards.update(
                gc_policy_requested=requested_policy,
                gc_policy_mode=gc_state["mode"],
                gc_policy_active=gc_state["active"],
                gc_automatic_enabled=gc_state["automatic_gc_enabled"],
                gc_policy_matches_requested=policy_matches,
            )
            context = result.setdefault("context", {})
            context["scale_gc_policy"] = requested_policy
            context["scale_gc_full_collect_ms"] = measurement_state.get(
                "gc_full_collect_ms", gc_state["full_collect_ms"]
            )
            context["scale_gc_full_collect_collected"] = measurement_state.get(
                "gc_full_collect_collected", gc_state["full_collect_collected"]
            )
            result["gc_policy"] = gc_state
            if not policy_matches:
                result["ok"] = False
                result["error"] = "gc_policy_mismatch"
            return result

        if op in {"stop_sustained", "clear"}:
            result = original_handle(command)
            restored = policy.restore(op)
            gc_state = _publish_policy_frame_metrics()
            result.update(
                gc_policy_restored=restored,
                gc_automatic_enabled=gc_state["automatic_gc_enabled"],
            )
            return result

        return original_handle(command)

    harness.handle_command = _handle

    if callable(original_update):

        def _update(delta_time: float) -> None:
            policy.tick()
            _publish_policy_frame_metrics()
            flush = getattr(harness, "_flush_scale_socket_output", None)
            if callable(flush):
                flush()
            original_update(delta_time)
            if callable(flush):
                flush()

        harness.update = _update

    if callable(original_cleanup):

        def _cleanup() -> None:
            policy.restore("cleanup")
            original_cleanup()

        harness.cleanup = _cleanup

    harness._scale_gc_policy_installed = True
    return True


__all__ = [
    "_install_reliable_socket_output",
    "install_scale_experiment_measurement",
]
