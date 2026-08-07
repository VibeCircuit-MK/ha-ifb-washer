"""Constants for the IFB Washer integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "ifb_washer"

AUTH_BASE = "https://myifb.ifbcloud.in/api/v5/"
LOGIN_BASE = "https://mcprod.ifbappliances.com/"
APPLIANCE_BASE = "https://myifb.ifbcloud.in/api/v5/"

CONF_IDENTIFIER = "identifier"
CONF_LOGIN_TYPE = "login_type"
CONF_CALLING_CODE = "calling_code"
CONF_OAUTH_CONSUMER_KEY = "oauth_consumer_key"
CONF_OAUTH_CONSUMER_SECRET = "oauth_consumer_secret"
CONF_OAUTH_TOKEN = "oauth_token"
CONF_OAUTH_TOKEN_SECRET = "oauth_token_secret"

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
DATA_MQTT = "mqtt"

DEFAULT_CALLING_CODE = "+91"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_MQTT_HOST = "mqtt2.ifbcloud.in"
DEFAULT_MQTT_PORT = 8883
DEFAULT_APP_CLIENT_ID = "aK9uNoA8QS"

PLATFORMS = ["sensor", "binary_sensor", "select", "button"]

STATE_NAMES = {
    0: "idle",
    1: "standby",
    2: "starting",
    3: "pre_wash",
    4: "main_wash",
    5: "extra_rinse_1",
    6: "extra_rinse_2",
    7: "extra_rinse_3",
    8: "first_rinse",
    9: "second_rinse",
    10: "final_rinse",
    11: "final_spin",
    12: "anti_crease",
    13: "complete",
    14: "paused",
    15: "soak",
    16: "rinse_hold",
    17: "heating",
    18: "draining",
    19: "intermediate_spin",
    20: "delay_start",
    22: "cooling",
    35: "hot_rinse_start",
    36: "steam",
    39: "rinse_hold_child_lock",
    40: "dry",
    50: "child_lock_end",
    65: "syncing",
    118: "syncing",
}

DOOR_STATES = {
    1: "unlocked",
    2: "locked",
    3: "locking",
    4: "unlocking",
}

MODEL_PROGRAMS = {
    "8903287030116": {
        1: "Mix / Daily",
        2: "Cotton",
        3: "Synthetic",
        4: "Baby Wear",
        5: "Refresh",
        7: "Express 15'",
        8: "Bulky Beddings",
        9: "CradleWash",
        10: "Rinse + Spin",
        11: "Wool",
        12: "Sports Wear",
        13: "Dark Wash",
        14: "Tub Clean",
        15: "Inner Wear",
        16: "Jeans",
        17: "Uniform",
        18: "Shirts / Blouses",
        19: "Steam Wash",
        20: "Linen Wash",
        21: "Anti Allergen",
        22: "Express 30'",
    }
}

MODEL_PROGRAM_DURATIONS = {
    "8903287030116": {
        1: 60,
        2: 118,
        3: 118,
        4: 110,
        5: 25,
        7: 15,
        8: 79,
        9: 45,
        10: 22,
        11: 43,
        12: 74,
        13: 78,
        14: 110,
        15: 73,
        16: 186,
        17: 100,
        18: 89,
        19: 30,
        20: 66,
        21: 133,
        22: 30,
    }
}

SPIN_SPEED_OPTIONS = {
    0: "No Spin",
    1: "400",
    2: "600",
    4: "800",
    6: "1000",
    7: "1200",
}

TEMPERATURE_OPTIONS = {
    0: "Not set",
    2: "Cold",
    3: "30",
    4: "40",
    5: "60",
    6: "95",
    8: "40E",
    9: "60E",
}
