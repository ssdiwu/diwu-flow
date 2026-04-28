"""Stop hook: integrity checks (stub).

Scans .diwu/recording/ session files for pitfall patterns.
"""


def check(settings, tasks):
    """Run integrity checks on the current task state.

    Scans .diwu/recording/ for anomaly patterns using regex matching.

    Returns:
        list of (level, message) tuples.
    """
    return []
