"""Optional frame capability; the caller selects and owns the actual renderer."""


def capture_observation_frame(capture=None):
    if capture is None:
        return None, 'No Agent observation frame provider configured'
    return capture()
