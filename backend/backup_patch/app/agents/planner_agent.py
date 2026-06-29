import pandas as pd
def generate_tasks(sector):

    tasks = []

    if sector == "Power":

        tasks.append("Analyze transformer companies")

        tasks.append("Read recent power sector filings")

        tasks.append("Track capex announcements")

    return tasks
