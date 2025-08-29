def get_current_month():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m")

def format_date(date):
    return date.strftime("%Y-%m-%d")