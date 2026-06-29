from apscheduler.schedulers.background import BackgroundScheduler


scheduler = BackgroundScheduler()


@scheduler.scheduled_job(

    "interval",

    days=90

)

def retrain_model():

    pass


scheduler.start()
