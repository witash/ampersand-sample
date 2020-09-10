from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm, EmptyForm, DriverForm, ChargingStationForm, BatteryForm, BatteryTransactionForm, BatteryTransactionEditForm
from app.models import User, Person, Driver, Vehicle, ChargingStation, Battery, BatteryTransaction, DriverSummary
from app.main import bp
from datetime import datetime, timedelta

from app.controllers.transactions import add_transaction
                
@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        db.session.commit()

@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    return redirect(url_for('main.drivers'))

@bp.route('/drivers/', methods=['GET'])
@login_required
def drivers():
    drivers = Driver.query.all()
    return render_template('drivers.html', title='Home', drivers=drivers)

'''
@bp.route('/drivers/new/', methods=['GET', 'POST'])
@login_required
def new_driver():
    form = DriverForm()
    if form.validate_on_submit():
        new_person = Person(name1=form.name1.data, name2=form.name2.data)
        db.session.add(new_person)
        db.session.flush()
        new_phone = PhoneNumber(number_e164=form.phone_number.data, owner=new_person)
        db.session.add(new_phone)
        db.session.flush()
        new_driver = Driver(person=new_person)
        db.session.add(new_driver)
        db.session.commit()
        flash('Driver added')
        return redirect(url_for('main.drivers'))
    return render_template('edit_driver.html', title='Home', form=form)

@bp.route('/drivers/edit/<int:driver_id>/', methods=['GET', 'POST'])
@login_required
def edit_driver(driver_id):
    driver = Driver.query.filter_by(id=driver_id).first_or_404()
    form = DriverForm(obj=driver)
    if form.validate_on_submit():
        db.session.add(driver)
        db.session.commit()
        return redirect(url_for('main.drivers'))
    return render_template('edit_driver.html', title='Home', form=form)
'''


@bp.route('/driver/<int:driver_id>/', methods=['GET'])
@login_required
def driver_detail(driver_id):
    driver = Driver.query.filter_by(id=driver_id).first_or_404()
    transactions = BatteryTransaction.query.filter(
            BatteryTransaction.driver == driver,
            BatteryTransaction.rejected.is_(False))\
                    .order_by(BatteryTransaction.transaction_date.asc())
    summaries = DriverSummary.query.filter_by(driver_id=driver_id)
    return render_template('driver_detail.html', driver=driver, transactions=transactions, summaries=summaries)


@bp.route('/charging_stations/', methods=['GET'])
@login_required
def charging_stations():
    charging_stations = ChargingStation.query.all()
    return render_template('charging_stations.html', title='Home', charging_stations=charging_stations)

@bp.route('/charging_station/<int:charging_station_id>/', methods=['GET'])
@login_required
def charging_station_detail(charging_station_id):
    charging_station = ChargingStation.query.filter_by(id=charging_station_id).first_or_404()
    transactions = BatteryTransaction.query.filter(
            BatteryTransaction.charging_station==charging_station,
            BatteryTransaction.rejected.is_(False))\
                    .order_by(BatteryTransaction.transaction_date.asc())
    batteries = Battery.query.filter_by(charging_station=charging_station)
    return render_template('charging_station_detail.html', charging_station=charging_station, batteries=batteries, transactions=transactions)

@bp.route('/battery/<int:battery_id>/', methods=['GET'])
@login_required
def battery_detail(battery_id):
    battery = Battery.query.filter_by(id=battery_id).first_or_404()
    battery_history = Battery.get_history(battery)
    return render_template('battery_detail.html', battery=battery, battery_history=battery_history)

@bp.route('/transactions/edit/<int:transaction_id>/', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    correction = BatteryTransaction.query.filter_by(id=transaction_id).first_or_404()
    charging_station = correction.charging_station
    form = BatteryTransactionEditForm(obj=correction)
    form.battery_out_id.choices = [(b.id, b.id) for b in Battery.query.all()]
    form.battery_in_id.choices = [(b.id, b.id) for b in Battery.query.all()]
    form.driver_id.choices = [(d.id, d.display_name) for d in Driver.query.all()]
    if form.validate_on_submit():
        driver = Driver.query.filter_by(id=form.driver_id.data).first()
        battery_out = Battery.query.filter_by(id=form.battery_out_id.data).first()
        battery_in = Battery.query.filter_by(id=form.battery_in_id.data).first()
        new_transaction = add_transaction(
                driver = driver,
                battery_in = battery_in,
                battery_out = battery_out,
                charging_station = charging_station,
                battery_in_energy = form.battery_in_energy.data,
                battery_out_energy = form.battery_out_energy.data,
                odometer_reading = form.odometer_reading.data,
                correction = correction)
        db.session.commit()
        flash('Transaction added')
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('wform.html', title='Home', form=form, next=request.path)

@bp.route('/transactions/new/<int:charging_station_id>/', methods=['GET', 'POST'])
@login_required
def new_transaction(charging_station_id):
    charging_station = ChargingStation.query.filter_by(id=charging_station_id).first_or_404()
    form = BatteryTransactionForm()
    form.battery_out_id.choices = [(b.id, b.id) for b in Battery.query.filter_by(charging_station=charging_station)]
    form.driver_id.choices = [(d.id, d.display_name) for d in Driver.query.all()]
    if form.validate_on_submit():
        driver = Driver.query.filter_by(id=form.driver_id.data).first()
        battery_out = Battery.query.filter_by(id=form.battery_out_id.data).first()
        new_transaction = add_transaction(
                driver = driver,
                battery_in = driver.current_vehicle.battery,
                battery_out = battery_out,
                charging_station = charging_station,
                battery_in_energy = form.battery_in_energy.data,
                battery_out_energy = form.battery_out_energy.data,
                odometer_reading = form.odometer_reading.data)
        db.session.commit()
        flash('Transaction added')
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('wform.html', title='Home', form=form, next=request.path)
