from app import create_app, db
from app.models import DriverSummary
from celery import Celery

app = create_app()
app.app_context().push()


def create_celery_app(app=None): 
    """ 
    Create a new Celery object and tie together the Celery config to the app's 
    config. Wrap all tasks in the context of the application. 
 
    :param app: Flask app 
    :return: Celery app 
    """ 
    app = app or create_app() 
 
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL']) 
    celery.conf.update(app.config) 
    TaskBase = celery.Task 
 
    class ContextTask(TaskBase): 
        abstract = True 
 
        def __call__(self, *args, **kwargs): 
            with app.app_context(): 
                return TaskBase.__call__(self, *args, **kwargs) 
 
    celery.Task = ContextTask 
    return celery 

celery = create_celery_app(app)

def summary_rollver(date=None):
    if not date:
        date = datetime.utcnow()

    for driver in Driver.query.all():
        DriverSummary.rollover(driver, date) 
