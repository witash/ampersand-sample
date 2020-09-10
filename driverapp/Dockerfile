FROM python:3.6-alpine

#gross but needed for psycopg2
RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev

RUN adduser -D ampersand

WORKDIR /home/ampersand

COPY --chown=ampersand:ampersand requirements.txt requirements.txt 
RUN pip install -r requirements.txt
RUN pip install gunicorn pymysql

COPY --chown=ampersand:ampersand app app
COPY --chown=ampersand:ampersand tests.py tests.py
COPY --chown=ampersand:ampersand create_sample_data.py create_sample_data.py 
COPY --chown=ampersand:ampersand migrations migrations
COPY --chown=ampersand:ampersand driverapp.py config.py ./ 

ENV FLASK_APP driverapp.py

USER ampersand

EXPOSE 5000

CMD exec gunicorn -b :5000 --access-logfile - --error-logfile - driverapp:app
