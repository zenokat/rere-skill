"""Privacy helpers for eval result evidence.

The eval harness keeps agent trajectories useful for debugging while making the
public result bundle safe to commit.  The helpers in this package centralize
redaction rules so runners, tests, and maintenance scripts use the same policy.
"""

