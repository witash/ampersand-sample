from app.models import BatteryTransaction, DriverSummary, Driver
from app import db
from datetime import datetime, timedelta
from sqlalchemy.sql.expression import or_

import celery

# for now, set summary interval to one day
# because they store both start and end times, summaries
# can actually support different time intervals, but for now they don't
SUMMARY_INTERVAL = timedelta(days=1)

def get_start_date(start_date):
    '''
    get the nearest midnight before the given date
    needs to be refactored to include timezone and different summary_intervals
    '''
    return start_date.replace(hour=0,minute=0,second=0,microsecond=0)


def rebuild(driver, start_date, end_date=None):
    '''
    Deletes all summaries between two dates.
    Then rebuilds from scratch
    '''
    db.session.flush()
    end_date = end_date or datetime.utcnow()
    bad_summaries = DriverSummary.query.filter(DriverSummary.driver == driver, DriverSummary.end_date >= start_date).delete(synchronize_session='fetch')
    return rollover(driver, end_date)


def rollover(driver, date):
    '''
    Updates all summaries for driver, 
    starts from the last summary, and updates up to and including date

    Fetches all transactiosn in that time range, and reapplies

    If any new summaries need to be created, create them
    '''
    last_summary = DriverSummary.query.filter(DriverSummary.driver == driver)\
            .order_by(DriverSummary.start_date.desc()).first()
    if last_summary:
        # we only want to apply transactions that have not yet been applied
        if last_summary.last_transaction:
            last_date = last_summary.last_transaction.transaction_date
        else:
            last_date = last_summary.start_date

        transactions = BatteryTransaction.query.filter(
                BatteryTransaction.rejected.is_(False),
                BatteryTransaction.driver == driver,
                BatteryTransaction.transaction_date > last_date,
                BatteryTransaction.transaction_date <= date)\
                        .order_by(BatteryTransaction.transaction_date.asc()).all()
    else:
        transactions = BatteryTransaction.query.filter(
                BatteryTransaction.rejected.is_(False),
                BatteryTransaction.driver == driver,
                BatteryTransaction.transaction_date <= date)\
                        .order_by(BatteryTransaction.transaction_date.asc()).all()

    return _rollover(driver, date, last_summary, transactions)


def _rollover(driver, end_date, last_summary, transactions):
    '''
    Function to actually apply the rollover
    Has a lot of preconditions, so not intended to be called directly; 
    use rollver() instead

    Given a list of transaction in ascending order of transaction date
    and the last summary
    apply all the transactins, creating new summary objects for any dates < end_date
    assumes that all the transactions have not yet been applied, 
    and are in the correct date rande
    '''
    new_summaries = []

    if len(transactions) > 0:
        end_date = max(transactions[-1].transaction_date, end_date)
        next_transaction = transactions[0]
        transactions = transactions[1:]
    else:
        next_transaction = None

    # if no last summary, create one when the driver started
    if not last_summary:
        start_date  = get_start_date(driver.date_started)
        last_summary = DriverSummary(driver = driver,
                start_date = start_date,
                end_date = start_date + SUMMARY_INTERVAL,
                ride_distance = 0,
                energy_used = 0,
                cumulative_ride_distance = 0,
                cumulative_energy_used = 0)

    current_summary = last_summary

    current_date = current_summary.start_date

    # until we are past the specified end date, create new summaries for each time interval
    # (if they don't exist)
    # and apply any unapplied transactions to them
    while (current_date < end_date):
        # if the current date is beyond the end_date of the current summary, create a new summary
        if current_summary.end_date <= current_date:
            new_summary = DriverSummary(driver = driver,
                    start_date = current_summary.end_date,
                    end_date = current_summary.end_date + SUMMARY_INTERVAL,
                    ride_distance = 0,
                    energy_used = 0,
                    cumulative_ride_distance = current_summary.cumulative_ride_distance,
                    cumulative_energy_used = current_summary.cumulative_energy_used)
            current_summary = new_summary
        # apply transactions until there are either no more transaction or
        # the next transaction is out of the date range for the current summary
        while(next_transaction and \
                next_transaction.transaction_date >= current_summary.start_date and \
                next_transaction.transaction_date < current_summary.end_date):
            current_summary.apply_transaction(next_transaction)
            if len(transactions) == 0:
                next_transaction = None
            else:
                next_transaction = transactions[0]
                transactions = transactions[1:]
        # every iteration, SOMETHING happend
        new_summaries.append(current_summary)
        current_date += SUMMARY_INTERVAL

    return new_summaries

def rollover_all():
    '''
    Rolls over all summaries for currently active drivers to a new date
    '''
    now = datetime.utcnow()
    drivers = Driver.query.filter(Driver.date_started < now, 
            _or(Driver.date_ended is None, Driver.date_ended > now))\
                    .all()

    for driver in drivers:
        rollover(driver, now)

def update_summaries(transaction):
    '''
    Updates summaries for a transaction

    If a correction or backdated transaction, rebuilds from the correction date

    Otherwise, just rollover up to the current transaction date 
    '''
    if transaction.correction:
        summaries = rebuild(transaction.driver, transaction.correction.transaction_date)
        if transaction.correction.driver != transaction.driver:
            summaries += rebuild(transaction.correction.driver, transaction.correction.transaction_date)
    else:
        summaries = rollover(transaction.driver, transaction.transaction_date)
    for summary in summaries:
        db.session.add(summary)
    db.session.flush()
