from flask_sqlalchemy import sqlalchemy
from flask import current_app as app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship

from sqlalchemy.ext.declarative import declared_attr
from flask_login import current_user
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.sql.expression import or_

class TransacctionController():



class SummaryController():



class BatteryController():
    def __init__(battery):
        pass

