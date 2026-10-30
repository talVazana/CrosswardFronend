from app.services import limits as limits_module


def test_default_limits_match_the_agreed_values(monkeypatch):
    for name in (
        "IMAGE_PARSER_TIMEOUT_SECONDS",
        "IMAGE_PROCESSING_TIMEOUT_SECONDS",
        "GEMINI_TIMEOUT_SECONDS",
        "GEMINI_MAX_ATTEMPTS",
        "MAX_GRID_SIZE",
        "MAX_CLUES",
        "MAX_CLUE_LENGTH",
        "MAX_TOTAL_CLUE_CHARS",
        "MAX_UPLOAD_BYTES",
        "MAX_IMAGE_DIMENSION",
        "GEMINI_MAX_PER_HOUR",
        "GEMINI_MAX_PER_DAY",
    ):
        monkeypatch.delenv(name, raising=False)

    limits = limits_module.get_limits()

    assert limits.parser_timeout_seconds == 30
    assert limits.image_processing_timeout_seconds == 120
    assert limits.gemini_timeout_seconds == 45
    assert limits.gemini_max_attempts == 2
    assert limits.max_grid_size == 20
    assert limits.max_clues == 500
    assert limits.max_clue_length == 500
    assert limits.max_total_clue_chars == 20000


def test_environment_overrides_are_applied(monkeypatch):
    monkeypatch.setenv("IMAGE_PARSER_TIMEOUT_SECONDS", "40")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("MAX_GRID_SIZE", "25")
    monkeypatch.setenv("MAX_CLUE_LENGTH", "700")

    limits = limits_module.get_limits()

    assert limits.parser_timeout_seconds == 40
    assert limits.gemini_timeout_seconds == 60
    assert limits.max_grid_size == 25
    assert limits.max_clue_length == 700


def test_invalid_environment_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("IMAGE_PARSER_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("MAX_GRID_SIZE", "9999")

    limits = limits_module.get_limits()

    assert limits.parser_timeout_seconds == 30
    assert limits.gemini_timeout_seconds == 45
    assert limits.max_grid_size == 20


def test_kill_switches_parse_boolean_values(monkeypatch):
    monkeypatch.setenv("IMAGE_PARSER_ENABLED", "false")
    monkeypatch.setenv("GEMINI_EXTRACTION_ENABLED", "off")
    monkeypatch.setenv("TELEGRAM_NOTIFICATIONS_ENABLED", "1")

    limits = limits_module.get_limits()

    assert limits.image_parser_enabled is False
    assert limits.gemini_extraction_enabled is False
    assert limits.telegram_notifications_enabled is True


def test_unknown_boolean_value_keeps_default(monkeypatch):
    monkeypatch.setenv("IMAGE_PARSER_ENABLED", "maybe")

    limits = limits_module.get_limits()

    assert limits.image_parser_enabled is True
