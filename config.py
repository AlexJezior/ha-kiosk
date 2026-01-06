import os
from datetime import datetime


def load_env():
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def get_env_int(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_str(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value

def get_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
