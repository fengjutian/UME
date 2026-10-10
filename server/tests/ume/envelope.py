"""Envelope assertions shared by the API tests.

Kept in a module rather than duplicated so every test file asserts the same
contract from section 9.2.
"""


def envelope_ok(response, expected_status=200):
    """Assert a success envelope and return its `data`."""
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert set(body) == {"data", "request_id"}, body
    assert body["request_id"], "every response must carry a request id"
    return body["data"]


def envelope_error(response, code, expected_status):
    """Assert an error envelope and return its `error` object."""
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert set(body) == {"error", "request_id"}, body
    assert set(body["error"]) == {"code", "message", "details"}, body
    assert body["error"]["code"] == code, body
    assert body["error"]["message"], "an error must carry a message"
    return body["error"]
