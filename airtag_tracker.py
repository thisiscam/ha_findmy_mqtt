import logging
import sys
import yaml
import json
import argparse
from pathlib import Path
import time
import paho.mqtt.client as mqtt
from _login import get_account_sync
from findmy import FindMyAccessory
from findmy.reports import RemoteAnisetteProvider
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.DEBUG)

LAST_UPDATE_FILE = "last_update.json"

def get_location_report(plist_path: str, anisette_server: str):
    try:
        with Path(plist_path).open("rb") as f:
            airtag = FindMyAccessory.from_plist(f)
        
        anisette = RemoteAnisetteProvider(anisette_server)
        acc = get_account_sync(anisette)
        
        try:
            # reports = acc.fetch_last_reports(airtag, hours=12)
            end = datetime.now(tz=timezone.utc)
            start = end - timedelta(hours=12)
            reports = acc.fetch_reports(airtag, start, None)
        finally:
            acc._evt_loop.run_until_complete(acc.close())
        
        if reports:
            reports = sorted(reports, key=lambda report: (report, -report.confidence))
            latest_report = reports[-1]
            return latest_report
        else:
            logging.warning("No location reports found for %s", plist_path)
            return None
    except Exception as e:
        logging.error("Error fetching location report for %s: %s", plist_path, str(e))
        return None

def publish_location(client, topic, report):
    location = {
        "latitude": report.latitude,
        "longitude": report.longitude,
        "gps_accuracy": report.confidence,
        "last_report_time": report.timestamp,
        "broadcast_time": datetime.now()
    }
    client.publish(topic, json.dumps(location, default=str))
    logging.info("Location report published to %s: %s", topic, location)

def publish_state(client, state_topic, state):
    client.publish(state_topic, state)
    logging.info("Published '%s' to %s", state, state_topic)

def load_last_update_time():
    if Path(LAST_UPDATE_FILE).exists():
        with open(LAST_UPDATE_FILE, "r") as f:
            return json.load(f).get("last_update_time", 0)
    return 0

def save_last_update_time(last_update_time):
    with open(LAST_UPDATE_FILE, "w") as f:
        json.dump({"last_update_time": last_update_time}, f)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logging.info("Connected to MQTT Broker")
    else:
        logging.error("Failed to connect, return code %d\n", rc)

def main(config_path: str) -> int:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    anisette_server = config["anisette_server"]
    mqtt_broker = config["mqtt_broker"]
    mqtt_username = config["mqtt_username"]
    mqtt_password = config["mqtt_password"]
    mqtt_port = config["mqtt_port"]
    polling_interval = config["polling_interval"] * 60  # Convert minutes to seconds
    airtags = config["airtags"]

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.username_pw_set(mqtt_username, mqtt_password)
    # client.connect(mqtt_broker, mqtt_port, 60)

    config_dir = Path(config_path).parent
    last_update_time = load_last_update_time()

    while True:
        current_time = time.time()
        sleep_time = max(0, polling_interval - (current_time - last_update_time))

        logging.info("Sleeping for %d seconds", sleep_time)
        time.sleep(sleep_time)

        current_time = time.time()

        for airtag in airtags:
            plist_path = config_dir / airtag["plist_path"]
            ha_mqtt_id = airtag["ha_mqtt_id"]
            mqtt_topic = f"{ha_mqtt_id}/attributes"
            mqtt_availability_topic = f"{ha_mqtt_id}_gps/availability"
            
            report = get_location_report(plist_path, anisette_server)
            client.connect(mqtt_broker, mqtt_port, 60)
            if report:
                publish_location(client, mqtt_topic, report)
                publish_state(client, mqtt_availability_topic, "online")
            else:
                publish_state(client, mqtt_availability_topic, "offline")
            client.disconnect()

        last_update_time = current_time
        save_last_update_time(last_update_time)

    client.disconnect()

    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Track AirTags and publish their locations to MQTT.')
    parser.add_argument('config', type=str, help='Path to the configuration file')
    
    args = parser.parse_args()
    
    sys.exit(main(args.config))

