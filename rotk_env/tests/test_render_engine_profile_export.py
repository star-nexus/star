from rotk_env.testing import scale_experiment_measurement as measurement
from rotk_env.testing import scale_experiment_measurement_base as base


def test_render_engine_breakdown_is_exported_in_formal_scale_snapshot():
    expected_sections = {
        "render_queue_prepare",
        "render_queue_submit",
        "render_batch_pack",
        "render_batch_blits",
        "render_scalar_execute",
        "render_queue_clear",
    }
    assert expected_sections.issubset(set(base._RELEVANT_SECTIONS))

    stats = {
        "sections": {
            name: {
                "category": "render",
                "self_ms": 1.0,
                "inclusive_ms": 1.0,
                "max_self_ms": 1.5,
                "max_inclusive_ms": 1.5,
                "frame_share_pct": 5.0,
            }
            for name in expected_sections
        }
    }
    exported = base._section_subset(stats)
    assert expected_sections.issubset(set(exported))


def test_render_engine_topology_and_pixel_metrics_survive_slow_frame_compaction():
    expected_metrics = {
        "render_layers",
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
    }
    assert expected_metrics.issubset(set(measurement._TAIL_METRICS))
