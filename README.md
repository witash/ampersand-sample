# Ampersand Sample

## Running
Building and running a development copy locally requires docker and docker-compose
````
docker-compose build
docker-compose up
````

Will build a complete environment including
- A flask web server
- A PostgreSQL database
- Celery workers
- A Redis server (for celery broker, key/value data and session store; not currently working)

The main application can be built by running
````
cd driverapp
docker build
````
Two environment variables are required: DATABASE_URI and CELERY_BROKER_URL

For any commands or interaction with the environment, the preferred method is to run a container and then execute commands against it, e.g. 
````
docker-compose build
docker-compose up
docker exec ampersandsample_web_1 [command]
````

## Migrations and sample data
Alembic and Flask-migrate are used to set up the database structure. Currently there is only one version. On a blank database, this can be applied by running
````
docker exec ampersandsample_web_1 flask db upgrade
````

After changing `driverapp/app/models.py` a new Alembic version can be created by running
````
docker exec ampersandsample_web_1 flask db migrate
docker exec ampersandsample_web_1 flask db upgrade
````

Sample data can be created by running
````
docker exec ampersandsample_web_1 python create_sample_data.py
````
Units are not realistic and there is a bug where the same battery is recorded as being swapped in multiple times, resulting in negative energy used.

## Tests

Unit tests can be run using 
````
docker exec ampersandsample_web_1 python create_sample_data.py
````
A test database is not required; unit tests work only on objects in memory

## Features

This application tracks three models; charging stations, batteries and drivers. There are pages for each of these models showing the current state and history of each model. 

The main (only) interaction supported is adding or editing BatteryTransactions, which represent a driver returning to a charging station, and exchanging the battery in his current vehicle for a new one from the charging station.

Adding new transactions is available from the charging station page. Driver, battery out, odometer readings and energy of the outgoing and incoming battery is required.

## Data Model

### Transactions and Corrections
Transactions are modeled according to the "Event Sourcing" pattern. All changes to the state of Battery, Driver, and ChargingStation models are captured as events in the BatteryTransaction model. These events are strictly immutable; if the data included in a transaction are incorrect, rather than edit the transaction directly, a new transaction is added, and the old transaction is marked as "rejected" or incorrect. The old transaction is reversed, and any later transactions affecting the same objects are reapplied, saving the affected objects at the end, to capture the now correct current state.

### Summaries

Driver summaries are saved to capture the ride distance and energy usage for each active driver for a given time period (in the current version, can only be daily). These values are stored in the database but are not part of the domain model; they are stored only to avoid having to recalculate metrics from the transaction history.

After every transaction, it is applied to the summary for the current period, creating the summary and any other missing summaries if they do not yet exist.

A nightly task create new blank summaries for every active driver on the current date. 

This is the purpose of the celery workers; to create these summaries in a separate tasks after a transaction is created. Celery-beat can also be used a simple scheduler for the nightly task. But this is not yet set up.

A similar summary table could also be created for batteries; in this version, these summaries are not saved but are only calculated in memory when requested. 
