import pytest
from unittest.mock import MagicMock, AsyncMock
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosHttpResponseError
from requests import RequestException
from azfunc import alert_worker


def make_alert(alert_id, zones):

    return [{
        "properties": {
            "id": alert_id,
            "areaDesc": "Volusia, FL",
            "geocode": {"UGC": zones},
            "sent": "2025-10-22T00:00:00Z",
            "effective": "2025-10-22T01:00:00Z",
            "severity": "Severe",
            "certainty": "Likely",
            "urgency": "Immediate",
            "event": "Flood Warning",
            "senderName": "NWS Melbourne FL",
            "headline": "Flood Warning in Effect",
            "description": "Seek shelter now.",
            "instruction": "Find high ground.",
            "response": "Avoid",
            "web": "http://www.weather.gov",
        }
    }]


# Tests get_alerts() in case the API raises a RequestException
def test_get_alerts_api_failure(monkeypatch, caplog):

    # Fake get_active_alerts to raise RequestException
    def raise_request_exception(*args, **kwargs):
        raise RequestException("API down!")

    monkeypatch.setattr(alert_worker, "get_active_alerts", raise_request_exception)

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("ERROR"):
        result = alert_worker.get_alerts()

    # Assertions
    assert result is None                           # returned early
    assert mock_send.call_count == 0                # nothing sent
    assert "Failed to fetch NWS alerts: API down!" in caplog.text


# Tests get_alerts() in case the API returns no zones affected
def test_get_alerts_no_affected_zones(monkeypatch, caplog):

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert(alert_id="123", zones=[]))

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("INFO"):
        result = alert_worker.get_alerts()

    # Assertions
    assert result is None                               # returned early
    mock_send.assert_not_called()                       # nothing sent
    assert "No affected zones in current NWS alerts." in caplog.text


# Tests get_alerts() in case get_zone_to_users() raises an exception
def test_get_alerts_get_zone_to_users_exception(monkeypatch, caplog):

    def raise_exception(*args, **kwargs):
        raise Exception("DB error!")

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert(alert_id="123", zones=["FLC127"]))
    monkeypatch.setattr(alert_worker, "get_zone_to_users", raise_exception)

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("ERROR"):
        result = alert_worker.get_alerts()

    # Assertions
    assert result is None                                   # returned early
    mock_send.assert_not_called()                           # nothing sent
    assert "Failed to query zone subscriptions: DB error!" in caplog.text


# Tests get_alerts() in case get_user_emails() raises an exception
def test_get_alerts_get_user_emails(monkeypatch, caplog):

    def raise_exception(*args, **kwargs):
        raise Exception("DB error!")

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert(alert_id="123", zones=["FLC127"]))
    monkeypatch.setattr(alert_worker, "get_user_emails", raise_exception)

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("ERROR"):
        result = alert_worker.get_alerts()

    # Assertions
    assert result is None                           # returned early
    mock_send.assert_not_called()                   # nothing sent
    assert "Failed to query user emails: DB error!" in caplog.text


# Tests get_alerts() doesn't send a message when user_email_list is missing an email
def test_get_alerts_no_emails(monkeypatch):

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert(alert_id="123", zones=["FLC127"]))
    monkeypatch.setattr(alert_worker, "get_zone_to_users", lambda *args, **kwargs: {"FLC127": ["user1"]})
    monkeypatch.setattr(alert_worker, "get_user_emails", lambda *args, **kwargs: {})

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    result = alert_worker.get_alerts()

    # Assertions
    assert result is None           # returned early
    mock_send.assert_not_called()   # nothing sent


# Tests get_alerts() to see if seen_alerts set catches a duplicate alert
def test_get_alerts_seen_alerts_set(monkeypatch, caplog):

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert(alert_id="123", zones=["FLC127", "FLC127"]))
    monkeypatch.setattr(alert_worker, "get_zone_to_users", lambda *args, **kwargs: {"FLC127": ["user1"]})
    monkeypatch.setattr(alert_worker, "get_user_emails", lambda *args, **kwargs: {"user1": "user1@example.com"})
    monkeypatch.setattr(alert_worker, "alert_check", lambda *args, **kwargs: None)

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("INFO"):
        result = alert_worker.get_alerts()

    # Assertions
    sent_messages = mock_send.call_args.args[0]
    count = len(sent_messages)
    assert count == 1
    msg = sent_messages[0]
    assert msg["user_id"] == "user1"
    assert msg["email"] == "user1@example.com"
    assert msg["alert_id"] == "123"
    assert msg["zone_id"] == "FLC127"
    assert f"Queued {count} messages successfully." in caplog.text


# Tests get_alerts() for the 3 Cosmos exception branches
@pytest.mark.parametrize("exception_cls, log_prefix", [
    (CosmosResourceExistsError, None),
    (CosmosHttpResponseError, "Cosmos DB error when processing alert"),
    (Exception, "Unexpected error when processing alert")
])
def test_get_alerts_exceptions(monkeypatch, caplog, exception_cls, log_prefix):

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert(alert_id="123", zones=["FLC127"]))
    monkeypatch.setattr(alert_worker, "get_zone_to_users", lambda *args, **kwargs: {"FLC127": ["user1"]})
    monkeypatch.setattr(alert_worker, "get_user_emails", lambda *args, **kwargs: {"user1": "user1@example.com"})

    mock_alert_check = MagicMock()
    mock_alert_check.side_effect = exception_cls
    monkeypatch.setattr(alert_worker, "alert_check", mock_alert_check)

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("ERROR"):
        result = alert_worker.get_alerts()

    alert_id = mock_alert_check.call_args.args[0]["alert_id"]
    user_id = mock_alert_check.call_args.args[0]["user_id"]

    # Assertions
    mock_alert_check.assert_called_once()   # check that alert_check gets called
    assert result is None                   # returned early
    mock_send.assert_not_called()           # nothing sent

    if log_prefix:
        assert f"{log_prefix} {alert_id} for user {user_id}" in caplog.text
    else:
        assert caplog.text == ""


# Tests get_alerts() in the successful case: alerts -> zones -> users -> emails -> messages -> queue
def test_get_alerts_success(monkeypatch, caplog):

    alerts = make_alert("123", ["FLC069"]) + make_alert("456", ["FLC127"])
    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: alerts)
    monkeypatch.setattr(alert_worker, "get_zone_to_users", lambda *args, **kwargs: {"FLC069": ["user1"], "FLC127": ["user2"]})
    monkeypatch.setattr(alert_worker, "get_user_emails", lambda *args, **kwargs: {"user1": "user1@example.com", "user2": "user2@example.com"})
    monkeypatch.setattr(alert_worker, "alert_check", lambda *args, **kwargs: None)

    mock_send = AsyncMock()
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("INFO"):
        result = alert_worker.get_alerts()

    expected = [
        {"user_id": "user1", "email": "user1@example.com", "alert_id": "123", "zone_id": "FLC069"},
        {"user_id": "user2", "email": "user2@example.com", "alert_id": "456", "zone_id": "FLC127"},
    ]

    # Assertions
    sent_messages = mock_send.call_args.args[0]
    count = len(sent_messages)
    assert count == 2
    assert f"Queued {count} messages successfully." in caplog.text
    for exp in expected:
        assert any(exp.items() <= msg.items() for msg in sent_messages)


# Tests get_alerts() when send_messages_to_queue() raises an exception
def test_get_alerts_send_messages_exception(monkeypatch, caplog):

    monkeypatch.setattr(alert_worker, "get_active_alerts", lambda: make_alert("456", ["FLC127"]))
    monkeypatch.setattr(alert_worker, "get_zone_to_users", lambda *args, **kwargs: {"FLC069": ["user1"], "FLC127": ["user2"]})
    monkeypatch.setattr(alert_worker, "get_user_emails", lambda *args, **kwargs: {"user1": "user1@example.com", "user2": "user2@example.com"})
    monkeypatch.setattr(alert_worker, "alert_check", lambda *args, **kwargs: None)

    mock_send = AsyncMock()
    mock_send.side_effect = Exception("Service Bus error")
    monkeypatch.setattr(alert_worker, "send_messages_to_queue", mock_send)

    with caplog.at_level("ERROR"):
        result = alert_worker.get_alerts()

    # Assertions
    assert result is None               # returned early
    mock_send.assert_called_once()      # called once and failed
    assert f"Failed to queue messages: Service Bus error" in caplog.text



