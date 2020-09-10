#!/usr/bin/env python
from datetime import datetime, timedelta
import unittest
from app import create_app, db
from app.models import User, Person, Driver, Vehicle, Battery, ChargingStation, BatteryTransaction, DriverSummary
from app.controllers.summaries import _rollover
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None

class TransactionModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def add_transaction_data(self):
        '''
        Adds all test data needed for a transaction
        '''
        charging_station = ChargingStation(name='Kiryanwompo')
        battery_out = Battery(serial='B-123', voltage=12, capacity=200, charging_station=charging_station)
        battery_in = Battery(serial='C-456', voltage=12, capacity=200)
        v = Vehicle(vin='I-123', battery=battery_in)
        p = Person(name1='Ozias', primary_phone_number='+256787737792')
        driver = Driver(person=p, current_vehicle=v, date_started=datetime.utcnow())

        return driver, battery_in, battery_out, charging_station 
     
    def test_battery_swap(self):
        '''
        Test that batteries location is updated correctly
        '''
        driver, battery_in, battery_out, charging_station = self.add_transaction_data()

        #This is how we set up the data, so it shouldn't fail
        self.assertEqual(battery_in.charging_station, None)
        self.assertEqual(driver.current_vehicle.battery, battery_in)
        self.assertEqual(battery_out.charging_station, charging_station)

        transaction = BatteryTransaction(
                driver = driver,
                battery_in = battery_in,
                battery_out = battery_out,
                charging_station = charging_station,
            )

        transaction.add_transaction()

        self.assertEqual(battery_out.charging_station, None)
        self.assertEqual(driver.current_vehicle.battery, battery_out)
        self.assertEqual(battery_in.charging_station, charging_station)


    def test_driver_summary(self):
        two_days_before = datetime.utcnow() - timedelta(days=2) - timedelta(hours=1)
        one_days_before = datetime.utcnow() - timedelta(days=1) - timedelta(hours=1)
        no_days_before = datetime.utcnow() - timedelta(hours=1)

        driver = Driver(date_started=two_days_before)
        battery1 = Battery()
        battery2 = Battery()

        battery_1_energy = 500
        battery_2_energy = 600
        energy_diff = 30
        initial_odometer = 2000
        ride_distance = 40

        transaction1 = BatteryTransaction(
                transaction_date = two_days_before + timedelta(hours=1),
                battery_out = battery1,
                battery_out_energy = battery_1_energy,
                odometer_reading = initial_odometer
            )
        transaction2 = BatteryTransaction(
                transaction_date = two_days_before + timedelta(hours=2),
                battery_in = battery1,
                battery_out = battery2,
                battery_in_energy = battery_1_energy - energy_diff,
                battery_out_energy = battery_2_energy,
                odometer_reading = initial_odometer + ride_distance,
                last_transaction = transaction1
            )
        transaction3 = BatteryTransaction(
                transaction_date = no_days_before,
                battery_in = battery2,
                battery_in_energy = battery_2_energy - energy_diff,
                odometer_reading = initial_odometer + 2*ride_distance,
                last_transaction = transaction2
            )

        transactions = [transaction1, transaction2, transaction3]

        self.assertEqual(transaction2.ride_distance, ride_distance)
        self.assertEqual(transaction3.ride_distance, ride_distance)

        summaries = _rollover(driver, datetime.utcnow(), None, transactions)
        self.assertEqual(len(summaries), 3)
        #first summary should have energy diff and ride_distance from the first two transactions
        self.assertEqual(summaries[0].ride_distance, ride_distance)
        self.assertEqual(summaries[0].energy_used, energy_diff)
        #first summary should have energy diff and ride_distance 0 (no transactions)
        self.assertEqual(summaries[1].ride_distance, 0)
        self.assertEqual(summaries[1].energy_used, 0)
        #first summary should have energy diff and ride_distance from the first three transactions
        self.assertEqual(summaries[0].ride_distance, ride_distance)
        self.assertEqual(summaries[0].energy_used, energy_diff)

    def test_rollover(self):
        #create a fake summary
        driver = Driver(date_started=datetime.utcnow())

        day_before = DriverSummary.get_start_date(datetime.utcnow() - timedelta(days=1) - timedelta(hours=1))
        end_date = day_before + timedelta(days=1)
        summary = DriverSummary(
                start_date = day_before,
                end_date = end_date
            )

        new_summaries = _rollover(driver, datetime.utcnow(), summary, [])
        self.assertEqual(len(new_summaries), 2)
        self.assertEqual(new_summaries[1].start_date,summary.end_date)

    def test_correction_transaction(self):
        '''
        Test rebuilding the transaction
        '''
        two_days_before = datetime.utcnow() - timedelta(days=2) - timedelta(hours=1)
        one_days_before = datetime.utcnow() - timedelta(days=1) - timedelta(hours=1)
        no_days_before = datetime.utcnow() - timedelta(hours=1)

        v = Vehicle()
        cs = ChargingStation()
        driver = Driver(date_started=two_days_before, current_vehicle=v)
        battery1 = Battery(charging_station=cs)
        battery2 = Battery(charging_station=cs)
        battery3 = Battery(charging_station=cs)

        transaction1 = BatteryTransaction(
                driver = driver,
                battery_out = battery1,
                charging_station = cs,
            )
        transaction1.add_transaction(transaction_date = two_days_before)

        transaction2 = BatteryTransaction(
                driver = driver,
                battery_in = battery3,
                battery_out = battery2,
                charging_station = cs,
            )
        transaction2.add_transaction(transaction_date = one_days_before)

        #Whoops! actually battery three was supposed to go out in transaction 1
        transaction3 = BatteryTransaction(
                driver = driver,
                battery_out = battery3,
                charging_station = cs,
            )
        transaction3.add_transaction(later_transactions = [transaction2], correction = transaction1)

        # battery 1 should be at the charging stations, it never went out
        self.assertEqual(battery1.charging_station, cs)
        # battery 2 should be with the driver
        self.assertEqual(driver.current_vehicle.battery, battery2)
        # battery 3 should be at the charging stations also, it came back in later
        self.assertEqual(battery3.charging_station, cs)
        
        
if __name__ == '__main__':
    unittest.main(verbosity=2)
