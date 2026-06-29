from apscheduler.schedulers.background \
    import BackgroundScheduler


scheduler = BackgroundScheduler()


def get_last_db_date(

    symbol
):

    # placeholder

    return None


def update_stock(

    symbol
):

    last_date = \

        get_last_db_date(

            symbol
        )

    # fetch from last_date to today

    pass


@scheduler.scheduled_job(

    "cron",

    hour=18,

    minute=30
)

def daily_update():

    # update all stocks

    pass


scheduler.start()
