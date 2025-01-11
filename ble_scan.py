import datetime
import pytz
import findmy
import findmy.scanner
import findmy.scanner.scanner
import asyncio
import logging
import time
import dataclasses
import yaml
import json
import os
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)

@dataclasses.dataclass(eq=False)
class AirTag:
    ha_mqtt_id: str
    accessory: findmy.accessory.FindMyAccessory
    last_seen: datetime.datetime
    is_home: bool = True

def publish_state(client, state_topic, state, **kwargs):
    client.publish(state_topic, state, **kwargs)
    logging.info("Published '%s' to %s", state, state_topic)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT Broker!")
    else:
        logging.error("Failed to connect, return code %d\n", rc)

def create_mqtt_client(config):

    mqtt_username = config["mqtt_username"]
    mqtt_password = config["mqtt_password"]

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.username_pw_set(mqtt_username, mqtt_password)
    return client

async def scan(config, airtags) -> None:
    scanner = await findmy.scanner.OfflineFindingScanner.create()
    
    client = create_mqtt_client(config)
    mqtt_broker = config["mqtt_broker"]
    mqtt_port = config["mqtt_port"]

    while True:
        client.connect(mqtt_broker, mqtt_port, 60)
        unseen_airtags = set(airtags)
        async for device in scanner.scan_for(config["ble_scan_duration"],  extend_timeout=True):
            found = False
            for airtag in airtags:
                if device.is_from(airtag.accessory):
                    found = True
                    break
            if not found:
                continue
            state_topic = f"{airtag.ha_mqtt_id}/state"
            publish_state(client, state_topic, "home")
            airtag.last_seen = device.detected_at  # Update the last seen time for this airtag
            airtag.is_home = True  # Mark the AirTag as home
            unseen_airtags.remove(airtag)
            if not unseen_airtags:
                break
        client.disconnect()
        await asyncio.sleep(config["ble_scan_interval"])


async def check_unseen(config, airtags) -> None:
    await asyncio.sleep(config["unseen_threshold"])

    unseen_threshold = datetime.timedelta(seconds=config["unseen_threshold"])
    
    client = create_mqtt_client(config)
    mqtt_broker = config["mqtt_broker"]
    mqtt_port = config["mqtt_port"]

    while True:
        now = datetime.datetime.now(pytz.timezone("UTC"))
        client.connect(mqtt_broker, mqtt_port, 60)
        for airtag in airtags:
            # print(airtag)
            if now - airtag.last_seen > unseen_threshold:
                mqtt_topic = f"{airtag.ha_mqtt_id}/state"
                publish_state(client, mqtt_topic, "not_home")
                airtag.is_home = False  # Mark the AirTag as away
        client.disconnect()
        await asyncio.sleep(config["ble_scan_interval"])

def has_consecutive_four_byte_match(bytes1, bytes2):
    length1 = len(bytes1)
    length2 = len(bytes2)
    
    if length1 < 4 or length2 < 4:
        return False
    
    for i in range(length1 - 3):
        four_bytes1 = bytes1[i:i+4]
        for j in range(length2 - 3):
            four_bytes2 = bytes2[j:j+4]
            if four_bytes1 == four_bytes2:
                return True
                

def update_availability(config, airtags, avail="online"):
    client = create_mqtt_client(config)
    mqtt_broker = config["mqtt_broker"]
    mqtt_port = config["mqtt_port"]
    client.connect(mqtt_broker, mqtt_port, 60)

    for airtag in airtags:
        mqtt_topic = f"{airtag.ha_mqtt_id}_ble/availability"
        publish_state(client, mqtt_topic, avail, retain=True)
    client.disconnect()


async def main():
    config_path = "config.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    now = datetime.datetime.now(pytz.timezone("UTC"))
    airtags = [
        AirTag(
            airtag["ha_mqtt_id"],
            findmy.accessory.FindMyAccessory.from_plist(open(airtag["plist_path"], "rb")),
            now,
            is_home=None
        )
        for airtag in config["airtags"]
    ]

    update_availability(config, airtags, "online")

    await asyncio.gather(
        scan(config, airtags),
        check_unseen(config, airtags)
    )

if __name__ == "__main__":
    asyncio.run(main())

