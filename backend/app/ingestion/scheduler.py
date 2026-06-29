from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def get_last_db_date(symbol):
    return {}

def update_stock(symbol):
    last_date = get_last_db_date(symbol)
    pass

@scheduler.scheduled_job("cron", hour=18, minute=30)
def daily_update():
    pass

scheduler.start()
