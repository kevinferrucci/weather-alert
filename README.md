# 🌩 Weather Alert App
Weather Alert is a full-stack Flask application that delivers real-time severe weather alerts from the National Weather Service (NWS) directly to registered users’ inboxes.
The project demonstrates production-ready cloud architecture by integrating Azure Cosmos DB, Azure Service Bus, and Azure Communication Services (email) while maintaining a clean Flask web interface.

## 🚀 Features
- Register with your email & location (auto-fetched from browser geolocation).
- Automatic lookup of your NWS forecast zone ID.
- Fetches active alerts from the NWS API every 2 minutes.
- Uses Azure Cosmos DB to store users, zone subscriptions, and sent alerts.
- Uses Azure Service Bus to queue messages for scalability.
- Sends email notifications via Azure Communication Services (Email API).
- Includes unit tests with both hand-rolled fakes and unittest.mock for real-world testing practices.

## 🛠 Tech Stack
- **Backend:** Flask (Python)
- **Frontend:** Bootstrap 5, HTML, CSS
- **Database:** Azure Cosmos DB (NoSQL)
- **Messaging Queue:** Azure Service Bus (async)
- **Email Service:** Azure Communication Services (Email API)
- **Testing:** Pytest, unittest.mock, hand-built fakes
- **Deployment:** Azure (Function Apps + Web App)

## 📂 Project Structure
```
weather-alert/
│
├── app/                         # Flask app
│   ├── __init__.py              # Flask factory (with logging tweaks)
│   ├── forms.py
│   ├── routes.py
│   ├── static/
│   │   ├── assets/
│   │   │   └── images/
│   │   └── css/
│   │       └── style.css
│   └── templates/
│       ├── about.html
│       ├── base.html
│       └── index.html
│
├── azfunc/                      # Helper code for Azure Functions
│   ├── __init__.py
│   ├── alert_worker.py
│   ├── function_app.py          # Main app logic
│   └── helpers/
│       ├── __init__.py
│       ├── cosmos_helpers.py
│       ├── email_sender.py
│       ├── nws_client.py
│       └── service_bus_sender.py
│
├── tests/                       # Unit tests (kept in GitHub, ignored in deploy)
│   ├── __init__.py
│   ├── test_alert_worker.py
│   ├── test_cosmos_helpers.py
│   ├── test_email_sender.py
│   ├── test_nws_client.py
│   ├── test_routes.py
│   └── test_service_bus_sender.py
│
├── function_app.py              # Stub entry point for Azure Functions (imports azfunc.function_app.app)
├── run.py                       # Flask dev runner (for local web UI)
├── host.json                    # Azure Functions host config
├── local.settings.json          # Local-only secrets (gitignored, not deployed)
├── .env                         # Local-only secrets (gitignored, not deployed)
├── .gitignore                   # GitHub ignore rules
├── .funcignore                  # Azure deployment ignore rules
├── requirements.txt             # Dependencies for Azure + Flask
├── LICENSE.txt                  # Standard MIT license
└── README.md
```

## ⚡️ Quick Start
1. **Clone the repo**
```
git clone https://github.com/<your-username>/weather-alert.git
cd weather-alert
```

2. **Create virtual environment**
```
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
.venv\Scripts\activate      # Windows
```

3. **Install dependencies**
```
pip install -r requirements.txt
```

4. **Set up environment variables**

Create a .env file in the project root for secrets used by Flask when running locally:
```
SECRET_KEY=
MY_EMAIL=
# Cosmos secrets
AZURE_ENDPOINT=
AZURE_KEY=
# ACS secrets
ACS_CONNECTION_STRING=
```
Create a local.settings.json file in the project root and set up env. variables.

Used by Azure Functions Core Tools and deployed to Azure:
```
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "",
    "ServiceBusConnection": "",
    "AZURE_ENDPOINT": "",
    "AZURE_KEY": "",
    "ACS_CONNECTION_STRING": "",
    "ACS_SENDER_EMAIL": "",
    "MY_EMAIL": "",
    "NAMESPACE_CONNECTION_STR": "",
    "QUEUE_NAME": ""
  }
}
```

5. **Run the app**
```
python run.py
```
Navigate to http://127.0.0.1:5000/

## ☁️ Deploy to Azure
1. **Login to Azure**
```
az login
```

2. **Publish Function App**

Make sure your requirements.txt is up to date before deploying.
```
func azure functionapp publish &lt;YourFunctionAppName&gt;
```

## 🧪 Testing
This project demonstrates two approaches to mocking:
- **Hand-rolled fakes** → used for Cosmos DB (cosmos_helpers) to clearly model NoSQL CRUD operations.
- **unittest.mock** → Used MagicMock for some tests and AsyncMock for Service Bus sender, showing industry-standard sync and async mocking.

Run tests:
```
pytest -v
```

## 📌 Example Unit Test (Cosmos DB Fake)
```python
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
```

## 📌 Example Unit Test (Service Bus AsyncMock)
```python
@pytest.fixture
def mock_servicebus():
    
    # ServiceBusClient is synchronous → use MagicMock
    # Sender is async (context manager + async send_messages) → use AsyncMock

    with patch("azfunc.helpers.service_bus_sender.ServiceBusClient.from_connection_string",
               new_callable=MagicMock) as mock_client_cls:
        mock_client = MagicMock()
        mock_sender = AsyncMock()

        # Make get_queue_sender return a fake sender
        mock_client.get_queue_sender.return_value = mock_sender

        # Teach the client to work as an async context manager
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_cls.return_value = mock_client

        # Same for sender (nested async context manager)
        mock_sender.__aenter__.return_value = mock_sender
        mock_sender.__aexit__.return_value = None

        yield mock_client, mock_sender


@pytest.mark.asyncio
async def test_send_messages_to_queue_calls_send_messages(mock_servicebus):

    mock_client, mock_sender = mock_servicebus
    messages = [{"id": 1}, {"id": 2}]

    await service_bus_sender.send_messages_to_queue(messages)
    
    # Ensure each message was sent
    assert mock_sender.send_messages.call_count == len(messages)
```

## 📝 Notes
- The Service Bus sender uses async/await for high-throughput message publishing, while the rest of the app remains synchronous because Cosmos DB and NWS API clients are sync. This design balances performance with simplicity.

## 📈 Future Improvements
- Add user authentication (Flask-Login or Azure AD).
- User dashboard with past alerts.
- Dockerize the app for easier deployment.
- CI/CD with GitHub Actions.

## 👨‍💻 Author
**Kevin Ferrucci**
- [GitHub](https://github.com/kevinferrucci "GitHub")
- [LinkedIn](https://www.linkedin.com/in/kevin-ferrucci/ "LinkedIn")

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.