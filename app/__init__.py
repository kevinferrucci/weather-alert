from flask import Flask
from flask_bootstrap import Bootstrap5
import logging
import os
from dotenv import load_dotenv

load_dotenv()


def create_app(test_config=None):

    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
    Bootstrap5(app)

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Silence Azure/Cosmos debug chatter
    logging.getLogger("azure.cosmos").setLevel(logging.ERROR)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

    if test_config:
        app.config.update(test_config)

    from app.routes import register_routes
    register_routes(app)

    return app