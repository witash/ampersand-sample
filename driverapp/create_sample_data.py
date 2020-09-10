#!/usr/bin/env python
from datetime import datetime, timedelta
from app import create_app, db
from app.models import Person, Driver, Vehicle, Battery, ChargingStation, BatteryTransaction, DriverSummary
from app.controllers.summaries import rollover
from app.controllers.transactions import add_transaction
from  sqlalchemy.sql.expression import func
from random import randint

first_names = [
'Gahigi',
'Gasimba',
'Gasore',
'Gatete',
'Habimana',
'Hakizimana',
'Mazimpaka',
'Mihigo',
'Mugabo',
'Mugisha',
'Mugwaneza',
'Munezero',
'Munyentwali',
'Mutanguha',
'Ngabo',
'Ndengeyingoma',
'Nsengiyumva',
'Nshimiye',
'Ntwali',
'Rusanganwa',
'Shema',
'Siboyintore',
]

last_names = [
'Uwimana',
'Ingabire',
'Habimana',
'Jean',
'Hakizimana',
'Nsengiyumva',
'Mugisha',
'Uwamahoro',
'Nshimiyimana',
'Bizimana',
'Nkurunziza',
'Rukundo',
'Mugabo',
'Kalisa',
'Uwera',
'Nsabimana',
'Muhire',
'Umutoni',
'Kwizera',
'Ndagijimana',
'Mbabazi',
'Karangwa',
'Kayitesi',
'Munyaneza',
'Kamanzi',
'Tuyisenge',
'Sibomana',
'Umuhoza',
'Uwineza',
'Gasana',
'Ishimwe',
'Hategekimana',
'Uwase',
'Niyonzima',
'Mutabazi',
'Emmanuel',
'Niyitegeka',
]

location_names = [
'Kacyiru',
'Rugenge',
'Kamukina',
'Rwampara',
'Gatare',
'Kibagabaga',
]

def create_sample_data():
    '''
    Adds all test data needed for a transaction
    '''
    for i, name in enumerate(location_names):
        charging_station = ChargingStation(name=name)
        db.session.add(charging_station)
        db.session.flush()
        for j in range(10):
            battery_out = Battery(serial='B-{}{}'.format(i,j), voltage=120, capacity=200, charging_station=charging_station)
            db.session.add(battery_out)
        v = Vehicle(vin='I-{}'.format(i))
        db.session.add(v)
        p = Person(name1=first_names[randint(0,len(first_names)-1)], 
            name3=last_names[randint(0,len(last_names)-1)], 
                primary_phone_number='+260{}'.format(randint(0,999999999)))
        driver = Driver(person=p, current_vehicle=v, date_started=datetime.utcnow()-timedelta(days=randint(1,30)))
        db.session.add(p)
        db.session.add(driver)

    date = datetime.utcnow() - timedelta(days=30)
    while date < (datetime.utcnow() - timedelta(days=1)):
        print(date)
        #get a random driver
        #get a random charging stations
        #get a random battery from that station
        current_hour = date
        for i in range(randint(0,10)):
            current_hour += timedelta(hours=1)
            charging_station = ChargingStation.query.filter().order_by(func.random()).first()
            driver = Driver.query.filter(Driver.date_started < date).order_by(func.random()).first()
            battery_out = Battery.query.filter(Battery.charging_station == charging_station).order_by(func.random()).first()
            if not driver or not battery_out:
                continue
            battery_in = driver.current_vehicle.battery

            if battery_in:
                battery_in_energy = battery_in.current_energy
                energy_used = randint(0, battery_in_energy)
                battery_in_energy -= energy_used
            else:
                energy_used = 0
                battery_in_energy = 0

            if battery_out:
                battery_out_energy = battery_out.current_energy
                battery_out_energy += randint(1, battery_out.capacity)
                battery_out_energy = min(battery_out_energy, battery_out.capacity)
            else:
                battery_out_energy = 0

            optimal_distance = int(energy_used / 3)
            distance = driver.current_vehicle.odometer_reading + randint(int(optimal_distance/2), optimal_distance)
            driver.current_vehicle.odometer_reading = distance
            db.session.add(driver.current_vehicle)

            new_transaction = add_transaction(
                    driver = driver,
                    battery_in = driver.current_vehicle.battery,
                    battery_out = battery_out,
                    charging_station = charging_station,
                    battery_in_energy = battery_in_energy,
                    battery_out_energy = battery_out_energy,
                    odometer_reading = distance,
                    transaction_date = current_hour)
            db.session.flush()
            if driver.current_vehicle.battery != battery_out:
                import pdb; pdb.set_trace()
        drivers = Driver.query.filter(Driver.date_started < date).all()
        date += timedelta(days=1)
        for driver in drivers:
            print(driver.current_vehicle.battery)
            rollover(driver, date)
    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app_context = app.app_context()
    app_context.push()
    db.create_all()

    create_sample_data()
