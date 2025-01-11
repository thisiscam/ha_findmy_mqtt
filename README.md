# Home Assistant FindMy MQTT Bridge

This project provides a set of scripts and tools to help Home Assistant track an Apple AirTag using both GPS (based on apple's FindMy network), and nearby BLE tracking. While the setup is a bit hacky, it works effectively. You'll need a separate Linux machine with Bluetooth capabilities. 

For my setup, I run this on a dedicated Proxmox VM, but your mileage may vary (YMMV). Currently, it supports AirTags paired with devices running **iOS 17 or earlier**. You'll also need a **macOS 15 or earlier** device to extract the master private key for your AirTag. For more details, check out [FindMy.py](https://github.com/malmeloo/FindMy.py).

This setup has been tested with official Apple AirTags only. In theory, it should work with any Apple trackable device (e.g., iPhone/iPad), officially supported AirTag clones, and possibly OpenHaystack tags. However, these alternatives remain untested.

---

## Basic Setup

1. **Prepare the Decrypted Plist File:**  
   Obtain the decrypted plist file for the AirTag you want to track.  

2. **Clone the Repository:**  
   Clone this repository to your Linux machine.  

3. **Set Up Python Virtual Environment:**  
   Create a Python virtual environment and install [FindMy.py](https://github.com/malmeloo/FindMy.py).  

4. **Configure MQTT in Home Assistant:**  
   Follow the [Home Assistant MQTT Integration Guide](https://www.home-assistant.io/integrations/mqtt/) to set up MQTT.  

5. **Set Up Anisette Server:**  
   Install and run an Anisette server. For simplicity, you can run it on the same VM.

6. **Add Device Tracker Configuration to Home Assistant:**  
   Add the following configuration to your `configuration.yaml` file in Home Assistant:  
   ```yaml
   mqtt:
     - device_tracker:
         name: "My AirTag"
         unique_id: my_airtag
         state_topic: "my_airtag/state"
         json_attributes_topic: "my_airtag/attributes"
         availability:
           - topic: "my_airtag_ble/availability"
           - topic: "my_airtag_gps/availability"
         availability_mode: "any"
         source_type: "bluetooth_le"
   ```

7. **Edit the `config.json` File:**  
   Modify `config.json` to match your MQTT configuration from the step above.  

---

## Systemd Service

1. **Add Systemd Service Files:**  
   Add the `airtag_ble_tracker.service` and `airtag_gps_tracker.service` files to your systemd services directory (e.g., `/etc/systemd/system/`).  

2. **Modify the Service Files:**  
   Edit the following lines in both files to match your setup:  
   ```bash
   # airtag_ble_tracker.service
   ExecStart=/path/to/your/virtualenv/bin/python ble_scan.py config.yml
   WorkingDirectory=/path/to/your/cloned/repository
   ```
   and
   ```bash
   airtag_gps_tracker.service
   ExecStart=/path/to/your/virtualenv/bin/python airtag_tracker.py config.yml
   WorkingDirectory=/path/to/your/cloned/repository
   ```

3. **Enable and Start the Services:**  
   Activate and start the services:  
   ```bash
   sudo systemctl enable airtag_ble_tracker.service
   sudo systemctl enable airtag_gps_tracker.service
   sudo systemctl start airtag_ble_tracker.service
   sudo systemctl start airtag_gps_tracker.service
   ```
