import pytest
import requests
import logging
from app import create_app, routes


@pytest.fixture
def client():

    app = create_app(test_config={"TESTING": True, "WTF_CSRF_ENABLED": False})
    with app.test_client() as client:
        yield client


#================================= Home and About route tests =================================

# Test the home route
def test_home_route(client):

    response = client.get("/")
    assert response.status_code == 200
    assert b"Stay safe, stay informed." in response.data


# Test the About page
def test_about(client):

    response = client.get("/about")
    assert response.status_code == 200
    assert b"About Weather Alert" in response.data


#================================= Helper fakes =================================

# Factory that returns a fake get_zone_ids with optional behavior
def fake_get_zone_ids_factory(zone_ids, called_flag=None, raise_exc=False):

    def fake_get_zone_ids(lat, lng, email):
        if called_flag is not None:
            called_flag["get_zone_ids"] = True
        if raise_exc:
            raise requests.RequestException("NWS API down")
        return zone_ids
    return fake_get_zone_ids


# Factory that returns a fake create_user
def fake_create_user_factory(user_store):

    def fake_create_user(first_name, email, lat, lng, zone_ids):
        user_store.update({
            "first_name": first_name,
            "email": email,
            "lat": lat,
            "lng": lng,
            "zone_ids": zone_ids
        })
    return fake_create_user


#================================= Test the register route =================================

# Test the register route when everything works like it should
def test_register_user_success(client, monkeypatch):

    user = {}
    monkeypatch.setattr(routes, "get_zone_ids", fake_get_zone_ids_factory(["ABC123"]))
    monkeypatch.setattr(routes, "create_user", fake_create_user_factory(user))

    response = client.post(
        "/register",
        data={
            "first_name": "John",
            "email": "john@smith.com",
            "lat": "0.0000",
            "lng": "0.0000",
            "consent": "y"
        }
    )

    # Assert that the user is redirected to the home page and all their info was passed correctly
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert user["first_name"] == "John"
    assert user["email"] == "john@smith.com"
    assert user["lat"] == "0.0000"
    assert user["lng"] == "0.0000"
    assert user["zone_ids"] == ["ABC123"]


# Test the register route when the form is missing a field
def test_register_user_invalid(client, monkeypatch):

    # Track if get_zone_ids() or create_user() are called
    called = {"get_zone_ids": False, "create_user": False}
    monkeypatch.setattr(routes, "get_zone_ids", fake_get_zone_ids_factory(["ABC123"], called_flag=called))
    monkeypatch.setattr(routes, "create_user", lambda *args, **kwargs: called.update({"create_user": True}))

    response = client.post("/register", data={"first_name": "John", "lat": "0.0000", "lng": "0.0000", "consent": "y"})

    # Assert redirect still happens and that create_user() and get_zone_ids() were not called
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert called["get_zone_ids"] == False
    assert called["create_user"] == False


# Test the register route if no zone ids are returned
def test_register_user_no_zone_ids(client, monkeypatch, caplog):

    called = {"get_zone_ids": False, "create_user": False}
    monkeypatch.setattr(routes, "get_zone_ids", fake_get_zone_ids_factory([], called_flag=called))
    monkeypatch.setattr(routes, "create_user", lambda *args, **kwargs: called.update({"create_user": True}))

    with caplog.at_level(logging.WARNING):
        response = client.post("/register", data={
            "first_name": "John",
            "email": "john@smith.com",
            "lat": "0.0000",
            "lng": "0.0000",
            "consent": "y"
        })

    # Assert redirect still happens and that get_zone_ids() was called but create_user() was not
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert called["get_zone_ids"] == True
    assert called["create_user"] == False
    assert "No zone ID(s) returned for coordinates" in caplog.text


# Test the register route when the API request fails
def test_register_user_api_failure(client, monkeypatch, caplog):

    called = {"get_zone_ids": False, "create_user": False}
    monkeypatch.setattr(routes, "get_zone_ids", fake_get_zone_ids_factory([], called_flag=called, raise_exc=True))
    monkeypatch.setattr(routes, "create_user", lambda *args, **kwargs: called.update({"create_user": True}))

    with caplog.at_level(logging.WARNING):
        response = client.post("/register", data={
            "first_name": "John",
            "email": "john@smith.com",
            "lat": "0.0000",
            "lng": "0.0000",
            "consent": "y"
        })

    # Assert redirect still happens and that get_zone_ids() was called but create_user() was not
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert called["get_zone_ids"] == True
    assert called["create_user"] == False
    assert "Error fetching zones" in caplog.text


#================================= Test get_zone_ids() =================================

"""Test get_zone_ids() for the successful case when everything works as expected 
and for when no zone ids are returned"""

@pytest.mark.parametrize("fake_features, expected", [
    ([{"properties": {"id": "ABC123"}}, {"properties": {"id": "DEF456"}}], {"ABC123", "DEF456"}),
    ([], set())
])
def test_get_zone_ids(monkeypatch, fake_features, expected):

    fake_response = {"features": fake_features}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return fake_response

    monkeypatch.setattr("app.routes.requests.get", lambda *args, **kwargs: FakeResp())
    result = routes.get_zone_ids("41.88266194873884", "-87.6233049031518", "john@smith.com")
    assert set(result) == expected