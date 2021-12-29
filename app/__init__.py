# app/__init__.py
from flask import Flask

from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os



cache = Cache(config={'CACHE_TYPE': 'simple'})
# Initialize the app
app = Flask(__name__, instance_relative_config=True)
# Load the database
#
app.config['SECRET_KEY'] = 'bigdickmonkakey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+os.path.abspath(os.getcwd())+'/database/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# cache.init_app(app)

from app.database import database
# database.init_db()
# exit()
db_session = database.db_session

# Load the views
from app import views

# Load the config file
app.config.from_object('config')


from .views import auth

app.register_blueprint(auth)

    # blueprint for non-auth parts of app
from .views import main
app.register_blueprint(main)





from app import models

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return models.User.query.get(int(user_id))

