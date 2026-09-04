"""Window resource recovery using the shared scheduled recovery policy."""

from __future__ import annotations

from .resource_recovery_system import ResourceRecoverySystem as _BaseResourceRecoverySystem


class ResourceRecoverySystem(_BaseResourceRecoverySystem):
    """Scheduled recovery shared with headless and window environments."""
