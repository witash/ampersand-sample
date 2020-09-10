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

class Base(db.Model):
    """Base model class to implement db columns and features every model should have"""
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, nullable=False)

class CreationDataMixin():
    """Allow a model to track its creation and update times"""
    date_added = db.Column(db.DateTime, default=db.func.current_timestamp())

    @declared_attr
    def creator_id(cls):
        return db.Column(db.ForeignKey('user.id'), index=True)

    #needs to have creator but haven't got this working yet
    #creator = relationship('User', lazy='select')

class ChangeData(Base):
    changed_field = db.Column(db.String(), nullable=False)
    old_value = db.Column(db.String())
    new_value = db.Column(db.String())

    model_ref = db.Column(db.String(), nullable=False, index=True)
    object_ref = db.Column(db.Integer(), nullable=False, index=True)

    @declared_attr
    def user_id(cls):
        return db.Column(db.ForeignKey('user.id'), index=True)

    #needs to have creator but haven't got this working yet
    #user = relationship('User', lazy='select')

    date_recorded = db.Column(db.DateTime, default=db.func.current_timestamp())


class ChangeDataMixin():
    @staticmethod
    def after_update(mapper, connection, target):
        inspr = db.inspect(target)
        attrs = db.class_mapper(target.__class__).column_attrs
        for attr in attrs:
            hist = getattr(inspr.attrs, attr.key).history
            if hist.has_changes():
                new_change = ChangeData(
                        changed_field = attr.key,
                        old_value = get_history(target, attr.key)[2].pop(),
                        new_value = getattr(target, attr.key),
                        model_ref = target.__tablename__,
                        object_ref = target.id
                    )
                db.session.add(new_change)
                #db.session.commit()
                #new_change.save(connection)


    @classmethod
    def __declare_last__(cls):
        pass
        #db.event.listen(cls, 'after_update', cls.after_update)

class Person(ChangeDataMixin, CreationDataMixin, Base):
    '''
    Represents a person, with a name, and a primary phone number
    '''
    name1 = db.Column(db.String(), index=True, nullable=False)
    name2 = db.Column(db.String(), index=True, default='')
    name3 = db.Column(db.String(), index=True, default='')
    # a person can have several phone numbers, but they need to have exactly one primary number
    primary_phone_number = db.Column(db.String(), index=True, nullable=False, unique=True)

    @property
    def display_name(self):
        '''
        What name order is supplied, display the name in the same order
        '''
        return ' '.join([self.name1, self.name2, self.name3])

    def set_name(self, name_str):
        '''
        Sets name fields from a single string

        Splits into tokens by whitespace, and saves the
        first and last names to name1 and name3
        and everything else to name2

        This allows indexed search on first characters of
        first and last tokens, agnostic of name ordering
        '''
        name_tokens = name_str.split()
        if len(tokens) > 0:
            self.name1 = name_tokens[0]
        if len(tokens) > 1:
            self.name3 = name_tokens[-1]
        if len(tokens) > 2:
            self.name2 = name_tokens[1:-1]


class Driver(ChangeDataMixin, CreationDataMixin, Base):
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), index=True, nullable=False)
    person = relationship(Person, lazy='joined')
    # date the person started driving
    date_started = db.Column(db.DateTime(), index=True, nullable=False)
    # date the person stopped being a driver
    date_ended = db.Column(db.DateTime(), index=True)

    # the current vehicle assigned to this driver
    # note that currently, changing vehicles is not supported
    current_vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), index=True)
    current_vehicle = relationship('Vehicle', backref='driver', uselist=False, lazy='select')

    @property
    def display_name(self):
        return self.person.display_name

class Vehicle(ChangeDataMixin, CreationDataMixin, Base):
    vin = db.Column(db.String(), index=True, nullable=False, unique=True)

    # the battery currently attached to this vehicle
    battery_id = db.Column(db.ForeignKey('battery.id'), index=True)
    battery = relationship('Battery', backref='vehicle', uselist=False, lazy='select')
    odometer_reading = db.Column(db.Integer(), default=0)

    @property
    def display_name(self):
        return self.vin

class ChargingStation(ChangeDataMixin, CreationDataMixin, Base):
    name = db.Column(db.String(), index=True, nullable=False, unique=True)
    location = db.Column(db.String())

    @property
    def display_name(self):
        return self.name


class Battery(ChangeDataMixin, CreationDataMixin, Base):
    serial = db.Column(db.String(), index=True, nullable=False, unique=True)
    capacity = db.Column(db.Integer(), nullable=False)
    voltage = db.Column(db.Integer(), nullable=False)
    charging_station_id = db.Column(db.ForeignKey('charging_station.id'), index=True)
    charging_station = relationship('ChargingStation', backref='batteries', lazy='select')
    #last_energy = db.Column(db.Integer(), default=0)

    @property
    def current_energy(self):
        '''
        Gets current energy based on last transaction in or out
        '''
        #last_transaction = BatteryTransaction.query.filter(BatteryTransaction.rejected.is_(False), 
        last_transaction = BatteryTransaction.query.filter(
                or_(
                    BatteryTransaction.battery_in == self,
                    BatteryTransaction.battery_out == self)
                )\
            .order_by(BatteryTransaction.transaction_date.desc()).first()

        if not last_transaction:
            return 0

        if last_transaction.battery_in == self:
            return last_transaction.battery_in_energy
        else:
            return last_transaction.battery_out_energy

    def get_history(self):
        '''
        Returns all transactions related to this battery
        '''
        transactions = BatteryTransaction.query.filter(BatteryTransaction.rejected.is_(False), 
                or_(
                    BatteryTransaction.battery_in == self,
                    BatteryTransaction.battery_out == self)
                )\
            .order_by(BatteryTransaction.transaction_date.desc()).all()

        return self._get_history(transactions)

    def _get_history(self, transactions):
        '''
        For batteries, we want a different format than regular transactions
        '''
        history = []
        for transaction in transactions:
            if transaction.battery_in == self:
                owner = transaction.charging_station
                energy = transaction.battery_in_energy
                distance = transaction.ride_distance
                efficiency = transaction.efficiency
                charge_amount = ''
            else:
                owner = transaction.driver
                energy = transaction.battery_out_energy
                distance = ''
                efficiency = ''
                charge_amount = transaction.charge_amount

            history.append({
                'date': transaction.transaction_date,
                'owner': owner,
                'energy': energy,
                'distance': distance,
                'efficiency': efficiency,
                'charge_amount': charge_amount
            })

        return history

class BatteryTransaction(ChangeDataMixin, CreationDataMixin, Base):
    battery_in_id = db.Column(db.Integer, db.ForeignKey('battery.id'), index=True)
    battery_in = relationship(Battery, lazy='select', foreign_keys='BatteryTransaction.battery_in_id')
    battery_out_id = db.Column(db.Integer, db.ForeignKey('battery.id'), index=True)
    battery_out = relationship(Battery, lazy='select', foreign_keys='BatteryTransaction.battery_out_id')
    
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), index=True, nullable=False)
    driver = relationship(Driver, lazy='select')

    charging_station_id = db.Column(db.ForeignKey('charging_station.id'), index=True)
    charging_station = relationship('ChargingStation', lazy='select')

    battery_in_energy = db.Column(db.Integer())
    battery_out_energy = db.Column(db.Integer())

    odometer_reading = db.Column(db.Integer())

    rejected = db.Column(db.Boolean(), default='False')

    correction_id = db.Column(db.ForeignKey('battery_transaction.id'), index=True)
    correction = relationship('BatteryTransaction', foreign_keys='BatteryTransaction.correction_id', uselist=False, lazy='select')

    last_transaction_id = db.Column(db.ForeignKey('battery_transaction.id'), index=True)
    last_transaction = relationship('BatteryTransaction', foreign_keys='BatteryTransaction.last_transaction_id', remote_side='BatteryTransaction.id')

    #note that this may be different from date_added
    transaction_date = db.Column(db.DateTime(), index=True, nullable=False)

    @property
    def efficiency(self):
        if self.energy_used > 0:
            return round(self.ride_distance / self.energy_used, 2)
        else:
            return 0

    @property
    def charge_amount(self):
        if self.last_transaction and self.battery_out and self.last_transaction.battery_in:
            return self.last_transaction.battery_in_energy - self.battery_out_energy

    @property
    def ride_distance(self):
        '''
        if this is not the first transaction for a driver, the distance traveled is
        the odometer reading for the last transaction - this transactions odometer reading
        '''
        if self.last_transaction:
            return self.odometer_reading - self.last_transaction.odometer_reading
        else:
            return 0

    @property
    def energy_used(self):
        '''
        if this is not the first transaction for a driver, and the last transaction
        had a battery out, the energy used is
        the last_transaction's battery_out_energy - this transactions battery_in_energy
        '''
        if self.last_transaction and self.last_transaction.battery_out_energy:
            return self.last_transaction.battery_out_energy - self.battery_in_energy
        else:
            return 0

    def add_transaction(self, later_transactions=None, correction=None, transaction_date=None):
        '''
        Aligns derived fields in other objects with this transactions

        If this has a correction, reverse the correction
        
        apply all the actions for this transaction

        If there are later transactions, apply each one of them
        If any later transaction's last transaction was the correction,
        set that transaction's last transaction to this one instead
        '''
        modified = []
        if not later_transactions:
            later_transactions = []
        if correction:
            correction.reverse()

        self.transaction_actions()

        for transaction in later_transactions:
            if correction and transaction.last_transaction_id == correction.id:
                transaction.last_transction = self
                modified.append(transaction)
            transaction.transaction_actions()
        return modified

    def reverse(self):
        '''
        Reverse any actions performed by this transaction

        If battery_in, put it back on the vehicle
        If battery_out, put it back in the charging station
        '''
        if self.battery_in:
            self.battery_in.charging_station = None
            vehicle = self.driver.current_vehicle
            vehicle.battery = self.battery_in

        if self.battery_out:
            self.battery_out.charging_station = self.charging_station
                
    def transaction_actions(self):
        '''
        Perform any actions associated with this transaction

        If battery_in, put it in the charging station
        If battery_out, put it on the vehicle
        '''
        if self.battery_in:
            self.battery_in.charging_station = self.charging_station

        if self.battery_out:
            self.battery_out.charging_station = None
            vehicle = self.driver.current_vehicle
            vehicle.battery = self.battery_out


class DriverSummary(Base):
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), index=True, nullable=False)
    driver = relationship(Driver, lazy='select')
    start_date = db.Column(db.DateTime(), index=True, nullable=False)
    end_date = db.Column(db.DateTime(), index=True, nullable=False)

    ride_distance = db.Column(db.Integer(), nullable=False)
    energy_used = db.Column(db.Integer(), nullable=False)

    cumulative_ride_distance = db.Column(db.Integer(), nullable=False)
    cumulative_energy_used = db.Column(db.Integer(), nullable=False)

    last_transaction_id = db.Column(db.ForeignKey('battery_transaction.id'))
    last_transaction = relationship('BatteryTransaction', foreign_keys='DriverSummary.last_transaction_id')

    def __repr__(self):
        return '<Summary {}: {}-{} for driver {}>'.format(self.id, self.start_date, self.end_date, self.driver)

    @classmethod
    def get_start_date(cls, start_date):
        return start_date.replace(hour=0,minute=0,second=0,microsecond=0)

    def apply_transaction(self, ride):
        self.ride_distance += ride.ride_distance
        self.energy_used += ride.energy_used
        self.cumulative_ride_distance += ride.ride_distance
        self.cumulative_energy_used += ride.energy_used
        self.last_transaction_id = ride.id


class User(UserMixin, Base):
    '''
    Boilerplate user model
    '''
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'],
            algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
        }
        if include_email:
            data['email'] = self.email
        return data

    def from_dict(self, data, new_user=False):
        for field in ['username', 'email']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def get_token(self, expires_in=3600):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        return user


@login.user_loader
def load_user(id):
    return User.query.get(int(id))

