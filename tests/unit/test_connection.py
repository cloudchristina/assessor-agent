from unittest.mock import patch
import pytest
from src.extract_uar.connection import get_connection, TlsRequiredError


def test_get_connection_passes_tls_settings_through_to_pymssql():
    with patch("src.extract_uar.connection.pymssql.connect") as mock_connect:
        mock_connect.return_value = object()
        conn = get_connection("h", 1433, "u", "p", database="d")
        mock_connect.assert_called_once()
        kwargs = mock_connect.call_args.kwargs
        assert kwargs["encrypt"] == "strict"
        assert kwargs["tds_version"] == "7.4"
        assert kwargs["server"] == "h"
        assert conn is mock_connect.return_value


def test_get_connection_refuses_to_bypass_tls():
    with pytest.raises(TlsRequiredError):
        get_connection("h", 1433, "u", "p", encrypt="off")


def test_get_connection_retries_on_transient_operational_error():
    import pymssql

    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise pymssql.OperationalError("transient")
        return object()

    with patch("src.extract_uar.connection.pymssql.connect", side_effect=flaky):
        conn = get_connection("h", 1433, "u", "p")
        assert conn is not None
        assert calls["n"] == 2
