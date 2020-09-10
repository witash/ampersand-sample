from app.models import BatteryTransaction, DriverSummary
from app import db, login
from datetime import datetime, timedelta
from sqlalchemy.sql.expression import or_

from app.controllers.summaries import update_summaries

def add_transaction(
        driver=None, 
        battery_in=None, 
        battery_out=None, 
        charging_station=None,
        battery_in_energy=0, 
        battery_out_energy=0, 
        odometer_reading=0, 
        correction=None, 
        transaction_date=None):
    '''
    Adds a battery transaction

    Finds the last transaction and any later transactions
    which may have affected the obejcts in this transaction

    Then applies the transaction, which may modify any 
    objects in this transaction, or its correction. It
    then these objects and anything else the transaction
    application returned as modified

    finally, it updates the summaries.
    This could be done in a background task. if that was working
    '''

    if not transaction_date:
        # a correction has the same transaction date
        if correction:
            transaction_date = correction.transaction_date
        else:
            transaction_date = datetime.utcnow()

    # the last transaction which is not rejected, and has the same driver
    last_transaction = BatteryTransaction.query.filter(
            BatteryTransaction.rejected.is_(False),
            BatteryTransaction.driver_id == driver.id,
            BatteryTransaction.transaction_date < transaction_date)\
                    .order_by(BatteryTransaction.transaction_date.desc())\
                    .first()

    new_transaction = BatteryTransaction(
            driver = driver,
            battery_in = battery_in,
            battery_out = battery_out,
            charging_station = charging_station,
            battery_in_energy = battery_in_energy,
            battery_out_energy = battery_out_energy,
            odometer_reading = odometer_reading,
            last_transaction = last_transaction,
            transaction_date = transaction_date,
            correction = correction)

    db.session.add(new_transaction)

    # mark the correction as rejected
    if correction:
        correction.rejected = True
        db.session.add(correction)

        drivers = (driver, correction.driver)
        batteries = [b for b in (battery_in, battery_out, correction.battery_in, correction.battery_out) if b]
    else:
        drivers = (driver,)
        batteries = [b for b in (battery_in, battery_out) if b]
    db.session.flush()

    # for any transactions with a transactio date later than this one, 
    # if they apply to the same objects as this transaction or its correction
    # they may need to be reapplied to get the correct current state
    later_transactions = BatteryTransaction.query.filter(BatteryTransaction.rejected.is_(False),
                or_(
                    BatteryTransaction.driver_id.in_([d.id for d in drivers]), 
                    BatteryTransaction.battery_in_id.in_([b.id for b in batteries]),
                    BatteryTransaction.battery_out_id.in_([b.id for b in batteries]),
                    BatteryTransaction.transaction_date > transaction_date)
                ).order_by(BatteryTransaction.transaction_date.asc()).all()

    # save any modified objects
    modified = new_transaction.add_transaction(later_transactions, correction)

    for m in modified:
        db.session.add(m)
    for driver in drivers:
        db.session.add(driver.current_vehicle)
    for battery in batteries:
        db.session.add(battery)
    db.session.flush()

    # finally, update summaries
    update_summaries(new_transaction)

