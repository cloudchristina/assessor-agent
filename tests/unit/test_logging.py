import json
from src.shared.logging import get_logger


def test_logger_emits_json(capsys):
    log = get_logger("test-service")
    log.info("hello", extra={"correlation_id": "run_x", "event": "boot"})
    captured = capsys.readouterr().out
    obj = json.loads(captured.strip().splitlines()[-1])
    assert obj["service"] == "test-service"
    assert obj["correlation_id"] == "run_x"
    assert obj["event"] == "boot"
    assert obj["message"] == "hello"
