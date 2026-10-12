"""Validation of operations result. Does not require running AYON server."""
import pytest

from ayon_api.exceptions import FailedOperations
from ayon_api.server_api import ServerAPI


@pytest.fixture
def con():
    return ServerAPI("http://localhost:0", create_session=False)


def test_failed_result_without_failed_operation_raises(con, capsys):
    result = {"success": False, "operations": [{"id": "a", "success": True}]}
    with pytest.raises(FailedOperations, match="Server response"):
        con._validate_operations_result(result, [{"id": "a"}])
    assert capsys.readouterr().out == ""


def test_failed_operation_raises_with_detail(con):
    result = {
        "success": False,
        "operations": [{"id": "a", "success": False, "detail": "Boom"}],
    }
    with pytest.raises(FailedOperations, match="Boom"):
        con._validate_operations_result(result, [{"id": "a", "type": "x"}])
