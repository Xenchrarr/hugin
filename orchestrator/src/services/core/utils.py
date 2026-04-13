import json
from datetime import datetime, timedelta

import pytz

from src.api.TeamsBot.TeamsBotMessageSender import send_message
from src.persistence.DatabaseLogger import DatabaseLogger
from src.services.core.threading_service import add_value_to_thread



def can_parse_to_date(date_string:str, date_format:str):

    if date_string is None:
        return False
    if date_format is None:
        return False
    try:
        # Try to parse the date string with the given format
        datetime.strptime(date_string, date_format)
        return True
    except ValueError:
        # If ValueError is raised, it means the string is not a valid date
        return False

def check_date_or_use_today(date:str, logger:DatabaseLogger):

    if can_parse_to_date(date, "%Y-%m-%d") is False:
        logger.log_warning("Date is not in correct format", "")
        date = datetime.now().strftime("%Y-%m-%d")
        logger.log_info(f"Using todays date: {date}")
    return date


def comma_separated_params_to_list(param:str) -> list[str]:

    result = []
    for val in param.split(','):
        if val:
            result.append(val)
    return result



def get_time_range(json_string:str, logger:DatabaseLogger):

    date = ""
    time = None

    try:
        data = json.loads(json_string)
        date = data.get("date")
        time = data.get("time")
    except Exception as e:
        logger.log_error("Error parsing json string", str(e))

    hour = 1
    minute = 0
    date = check_date_or_use_today(date, logger)

    # Set the timezone to UTC
    utc_tz = pytz.timezone('UTC')

    try:
        # Localize the date to UTC timezone (midnight that day)
        datetime_object = utc_tz.localize(datetime.strptime(date, '%Y-%m-%d'))
    except Exception as e:
        logger.log_error("Error parsing or localizing date", str(e))
        return None, None

    use_whole_day = False

    if not time or not isinstance(time, dict) or json_string in ["", "0", None]:
        logger.log_warning("No time in json string")
        logger.log_warning("Using entire day")
        use_whole_day = True
    else:
        try:
            hour = int(time.get("hour", 1))
            minute = int(time.get("minute", 0))
        except Exception as e:
            logger.log_error("Error parsing time values", str(e))
            use_whole_day = True

    if use_whole_day:
        start_time = datetime_object.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime_object.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        now = datetime.now(utc_tz)
        # Apply current UTC time to the specified date
        start_time = datetime_object.replace(hour=now.hour, minute=now.minute,
                                             second=now.second, microsecond=now.microsecond)
        end_time = start_time - timedelta(hours=hour, minutes=minute)

    start_time_string = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_time_string = end_time.strftime("%Y-%m-%dT%H:%M:%S")

    return end_time_string, start_time_string




def get_date_from_json(json_string:str) -> str:

    try:
        data = json.loads(json_string)
        date = data.get("date")
        return date
    except Exception as e:
        raise Exception("Error json string. Could not find date in json string: " + json_string + " | " + str(e))

def get_num_days_between_two_date_strings(date1: str, date2: str):

    date1 = datetime.strptime(date1, "%Y-%m-%dT%H:%M:%S")
    date2 = datetime.strptime(date2, "%Y-%m-%dT%H:%M:%S")
    return abs((date2 - date1).days)


def check_errors_and_set_status(errors: list[str], items:list, logger: DatabaseLogger, job_name: str):

    if len(errors) > 0:
        logger.log_error(f"Errors when running: {job_name}", json.dumps(errors))
        send_message(f"Errors when running {job_name}: {json.dumps(errors)}")
        if len(errors) == len(items):
            add_value_to_thread(key="job_status", value="Error")
        else:
            add_value_to_thread(key="job_status", value="Partial")

