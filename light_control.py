import tinytuya
import json
import sys

def control_light(name, state):
    with open('tinytuya.json', 'r') as f:
        config = json.load(f)
    
    with open('tuya-raw.json', 'r') as f:
        devices = json.load(f)
    
    device_id = None
    for device in devices['result']:
        if device['name'] == name:
            device_id = device['id']
            local_key = device['local_key']
            ip = device['ip']
            break
    
    if not device_id:
        print(f"Device '{name}' not found.")
        return

    d = tinytuya.OutletDevice(device_id, ip, local_key)
    d.set_version(3.3)
    
    if state == "off":
        d.turn_off()
        print(f"Turned off {name}")
    elif state == "on":
        d.turn_on()
        print(f"Turned on {name}")

if __name__ == "__main__":
    name = sys.argv[1]
    state = sys.argv[2]
    control_light(name, state)
