import pytest
import requests
from app import create_app
from azfunc.helpers import nws_client


@pytest.fixture
def client():

    app = create_app(test_config={"TESTING": True})
    with app.test_client() as client:
        yield client


#================================= Test get_active_alerts() =================================

@pytest.mark.parametrize("fake_alerts, expected", [
    ({"features": [{"id": "alert1"}, {"id": "alert2"}]}, [{"id": "alert1"}, {"id": "alert2"}]), # Normal API response
    ({"features": []}, []) # API response is empty
])
def test_get_active_alerts(monkeypatch, fake_alerts, expected):

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return fake_alerts

    monkeypatch.setattr("azfunc.helpers.nws_client.requests.get", lambda *args, **kwargs: FakeResp())
    alerts = nws_client.get_active_alerts()

    # Assertions
    assert alerts == expected


# Simulates an HTTP failure and ensures exception is raised
def test_get_active_alerts_http_error(monkeypatch):

    class FakeResp:
        def raise_for_status(self): raise requests.HTTPError("API down")

    monkeypatch.setattr("azfunc.helpers.nws_client.requests.get", lambda *args, **kwargs: FakeResp())

    # Assertions
    with pytest.raises(requests.HTTPError):
        nws_client.get_active_alerts()
