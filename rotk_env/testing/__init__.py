"""Explicit testing/scale instrumentation for STAR environments."""

from .render_presentation_ablation import install_render_presentation_ablations

# Process-scoped and opt-in. With both environment flags unset this is a no-op
# and does not import or modify production render-system classes.
install_render_presentation_ablations()
