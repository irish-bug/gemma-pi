# Home Assistant & Device Routing Policy

## 🎯 Core Principle
When asked to control lights, fans, or appliances, use the local `kasa` CLI tool. Always specify the IP address and device type explicitly to bypass network discovery timeouts. Edit to replace your tool/s of choice if not Kasa. 

## 📋 Device IP Mappings
- **Night Light:** `192.168.X.XXX` (Type: `plug`)
- **Fan:** `192.168.X.XXX` (Type: `plug`)
- **Bathroom Heater:** `192.168.X.XXX` (Type: `plug`)
- **Cat Massager:** `192.168.X.XXX` (Type: `plug`)

## 🛠 Execution Protocol
1. **Command Structure:** Never run raw `kasa discover`. Always target the host directly using the absolute path to the binary:
   `/home/<USERNAME>/<PATH_TO_PROJECT>/gemma_stable_env/bin/kasa --host <IP_ADDRESS> --type <type> <on|off|state>`
2. **Execution Example:** To turn off the [Device Name], the literal terminal execution must be:
   `/home/<USERNAME>/<PATH_TO_PROJECT>/gemma_stable_env/bin/kasa --host <IP_ADDRESS> --type plug off`