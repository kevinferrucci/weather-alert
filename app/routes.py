from flask import render_template, redirect, url_for
import requests
import logging
import os
from dotenv import load_dotenv
from app.forms import UserForm
from azfunc.helpers import create_user

load_dotenv()
MY_EMAIL = os.getenv("MY_EMAIL")


def register_routes(app):

    @app.route('/', methods=["GET"])
    def home():

        user_form = UserForm()
        return render_template("index.html", form=user_form)


    @app.route('/about', methods=["GET"])
    def about():

        return render_template("about.html")


    @app.route('/register', methods=["POST"])
    def register_user():

        user_form = UserForm()

        if user_form.validate_on_submit():

            first_name = user_form.first_name.data
            email = user_form.email.data
            lat = user_form.lat.data
            lng = user_form.lng.data

            try:
                zone_ids = get_zone_ids(lat, lng, email)
                if not zone_ids:
                    logging.warning(f"No zone ID(s) returned for coordinates: ({lat}, {lng})")
                    return redirect(url_for('home'))

                create_user(first_name, email, lat, lng, ["PKZ671"])
                logging.info(f"Created new user: {email} with zone id(s): {zone_ids}")
            except requests.RequestException as e:
                logging.error(f"Error fetching zones: {e}")
            except Exception as e:
                logging.error(f"Error creating user: {e}")

        return redirect(url_for('home'))


# Get and return new user's NWS zone ID based on their coordinates
def get_zone_ids(lat, lng, email):

    headers = {
        "User-Agent": f"(KevinWeatherAlertApp, {MY_EMAIL})",
        "Accept": "application/geo+json"
    }
    get_zone_url = "https://api.weather.gov/zones"
    params = {"point": f"{lat},{lng}"}

    logging.info(f"Fetching NWS zone ID(s) for coordinates: ({lat}, {lng})")
    response = requests.get(get_zone_url, params=params, headers=headers)
    response.raise_for_status()

    zones_returned = response.json().get("features", [])
    zone_ids = list(set(zone["properties"]["id"] for zone in zones_returned))
    logging.info(f"Successfully fetched zone ID(s): {zone_ids} for {email}")

    return zone_ids