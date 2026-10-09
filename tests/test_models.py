from incident_copilot.domain.models import LogLevel


def test_log_level_severity_follows_meaning_not_alphabet() -> None:
    # Alphabetically CRITICAL < DEBUG and ERROR < INFO; severity must say the opposite.
    assert LogLevel.CRITICAL.severity > LogLevel.DEBUG.severity
    assert LogLevel.ERROR.severity > LogLevel.INFO.severity
    assert [level.severity for level in LogLevel] == sorted(
        level.severity for level in LogLevel
    )
