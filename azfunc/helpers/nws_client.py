import requests
import os

MY_EMAIL = os.getenv("MY_EMAIL")


def get_active_alerts():

    nws_api_url = "https://api.weather.gov/alerts/active"
    headers = {
        "User-Agent": f"(KevinWeatherAlertApp, {MY_EMAIL})",
        "Accept": "application/geo+json"
    }
    params = {"status": ["actual"]}
    response = requests.get(nws_api_url, params=params, headers=headers)
    response.raise_for_status()
    return response.json().get("features", [])