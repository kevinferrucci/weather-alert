import pytest
import uuid
from datetime import datetime, timezone
from azure.cosmos import exceptions
from app import create_app
from azfunc.helpers import cosmos_helpers


@pytest.fixture
def client():

    app = create_app(test_config={"TESTING": True})
    with app.test_client() as client:
        yield client


#================================= Test create_user() =================================

def test_create_user(monkeypatch):

    # Track that user was created and zones updated
    created_items = []
    updated_zones = []

    # Fake users_container
    class FakeUsersContainer:
        def create_item(self, body):
            created_items.append(body)

    # Fake update_zone_subscriptions()
    def fake_update_zone_subscriptions(zone_id, user_id):
        updated_zones.append({
            "id": zone_id,
            "user_ids": [user_id]
        })

    monkeypatch.setattr(cosmos_helpers, "users_container", FakeUsersContainer())
    monkeypatch.setattr(cosmos_helpers, "update_zone_subscriptions", fake_update_zone_subscriptions)

    cosmos_helpers.create_user(
        first_name="John",
        email="john@smith.com",
        lat="0.0000",
        lng="0.0000",
        zone_ids=["ABC123", "DEF456"]
    )

    # Assertions
    assert len(created_items) == 1
    user_doc = created_items[0]
    uuid.UUID(user_doc["id"])
    assert user_doc["first_name"] == "John"
    assert user_doc["email"] == "john@smith.com"
    assert user_doc["lat"] == "0.0000"
    assert user_doc["lng"] == "0.0000"
    assert user_doc["zone_ids"] == ["ABC123", "DEF456"]
    datetime.fromisoformat(user_doc["registered_at"])
    # Assert that zone_subscriptions was updated with the new user
    assert updated_zones == [
        {"id": "ABC123", "user_ids": [user_doc["id"]]},
        {"id": "DEF456", "user_ids": [user_doc["id"]]}
    ]


#================================= Test update_zone_subscriptions() =================================

@pytest.mark.parametrize(
    "updated_zones, zone_id, user_id, expected, expected_replace, expected_create", [
        # Case 1: Existing zone id, new user added
        ({"ABC123": {"id": "ABC123", "user_ids": ["user1"]}, "DEF456": {"id": "DEF456", "user_ids": ["user1", "user2"]}},
         "ABC123", "user3", {"id": "ABC123", "user_ids": ["user1", "user3"]}, True, False),
        # Case 2: New zone id created
        ({"ABC123": {"id": "ABC123", "user_ids": ["user1"]}}, "DEF456", "user2", {"id": "DEF456", "user_ids": ["user2"]}, False, True),
        # Case 3: User already present in the zone id (no-op)
        ({"ABC123": {"id": "ABC123", "user_ids": ["user1"]}}, "ABC123", "user1", {"id": "ABC123", "user_ids": ["user1"]}, False, False)
    ]
)
def test_update_zone_subscriptions(monkeypatch, updated_zones, zone_id, user_id, expected, expected_replace, expected_create):

    # Track method calls
    called = {"replace": False, "create": False}

    # Fake users_container
    class FakeZonesContainer:
        def read_item(self, item, partition_key):
            if item in updated_zones:
                return updated_zones[item]
            raise exceptions.CosmosResourceNotFoundError()

        def create_item(self, body):
            called["create"] = True
            updated_zones[body["id"]] = body

        def replace_item(self, item, body):
            called["replace"] = True
            updated_zones[item] = body

    monkeypatch.setattr(cosmos_helpers, "zones_container", FakeZonesContainer())
    cosmos_helpers.update_zone_subscriptions(zone_id, user_id)

    # Assertions
    assert updated_zones[zone_id] == expected
    assert called["replace"] == expected_replace
    assert called["create"] == expected_create


#================================= Test get_zone_to_users() =================================

@pytest.mark.parametrize("zone_subscriptions, affected_zone_ids, expected", [
    # Case 1: one zone look up
    ({"ABC123": {"id": "ABC123", "user_ids": ["user1"]},"DEF456": {"id": "DEF456", "user_ids": ["user1", "user2"]}},
     ["DEF456"], {"DEF456": ["user1", "user2"]}),
    # Case 2: multiple zones look up
    ({"ABC123": {"id": "ABC123", "user_ids": ["user1"]},"DEF456": {"id": "DEF456", "user_ids": ["user1", "user2"]}},
     ["ABC123", "DEF456"], {"ABC123": ["user1"], "DEF456": ["user1", "user2"]})
])
def test_get_zone_to_users(monkeypatch, zone_subscriptions, affected_zone_ids, expected):

    # Fake users_container
    class FakeZonesContainer:
        def query_items(self, query, parameters, enable_cross_partition_query=True):
            requested_ids = parameters[0]["value"]
            return [zone_subscriptions[zone_id] for zone_id in requested_ids if zone_id in zone_subscriptions]

    monkeypatch.setattr(cosmos_helpers, "zones_container", FakeZonesContainer())
    results = cosmos_helpers.get_zone_to_users(affected_zone_ids)

    # Assertions
    assert results == expected


#================================= Test get_user_emails() =================================

def test_get_user_emails(monkeypatch):

    all_user_ids = {"user1", "user3"}
    users = {"user1": {"id": "user1", "email": "user1@email.com"}, "user2": {"id": "user2", "email": "user2@email.com"},
             "user3": {"id": "user3", "email": "user3@email.com"}}

    class FakeUsersContainer:
        def query_items(self, query, parameters, enable_cross_partition_query=True):
            # Going through parameters more closely simulates how the real query would happen
            requested_ids = set(parameters[0]["value"])
            return [users[user] for user in requested_ids if user in users]

    monkeypatch.setattr(cosmos_helpers, "users_container", FakeUsersContainer())
    results = cosmos_helpers.get_user_emails(all_user_ids)

    # Assertions
    assert results == {"user1": "user1@email.com", "user3": "user3@email.com"}


#================================= Test alert_check() =================================

def test_alert_check(monkeypatch):

    alert_sent_details = {
        "alert_id": "alert1",
        "user_id": "user1",
        "email": "user1@example.com",
        "created_at": "2025-10-21T18:02:13.782936+00:00",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "zone_id": "zone1",
        "event": "Special Weather Statement",
        "link": "http://www.weather.gov"
    }
    created_items = {}

    class FakeAlertsContainer():
         def create_item(self, body):
             created_items[body["id"]] = body

    monkeypatch.setattr(cosmos_helpers, "alerts_container", FakeAlertsContainer())
    cosmos_helpers.alert_check(alert_sent_details)

    alert_id = f"{alert_sent_details["alert_id"]}-{alert_sent_details["user_id"]}"
    expected_doc = {
        "id": alert_id,
        **alert_sent_details
    }

    # Assertions
    assert created_items[alert_id] == expected_doc