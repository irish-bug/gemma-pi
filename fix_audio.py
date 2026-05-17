import subprocess
import os
import time
import threading

def check_audio_device():
    """Checks if the Anker S500 is listed in aplay."""
    result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
    return "S500" in result.stdout

def enforce_volume():
    """Background loop to enforce volume for card 2."""
    while True:
        try:
            subprocess.run(['amixer', '-c', '2', 'sset', 'PCM', '80%'], capture_output=True)
        except Exception as e:
            print(f"Error enforcing volume: {e}")
        time.sleep(60)

def reset_usb_device(vendor_id="291a", product_id="3305"):
    """Resets the USB device by finding its bus/device path."""
    # Find the device path via lsusb
    cmd = f"lsusb -d {vendor_id}:{product_id}"
    result = subprocess.run(cmd.split(), capture_output=True, text=True)
    
    if not result.stdout:
        print("Device not found on USB bus.")
        return

    # Example output: Bus 003 Device 002: ID 291a:3305
    line = result.stdout.strip().split()
    bus = line[1]
    dev = line[3].rstrip(':')
    
    device_path = f"/dev/bus/usb/{bus}/{dev}"
    print(f"Resetting device at {device_path}")
    
    try:
        # Find the sysfs path
        # This is a bit complex, let's use a simple approach:
        # If usbutils is installed, call usbreset.
        subprocess.run(['sudo', 'usbreset', f"{bus}/{dev}"], check=True)
    except Exception as e:
        print(f"Error resetting device: {e}")

if __name__ == "__main__":
    if not check_audio_device():
        print("Anker S500 not detected. Attempting reset...")
        reset_usb_device()
    else:
        print("Anker S500 detected.")

    # Start the volume enforcement thread
    volume_thread = threading.Thread(target=enforce_volume, daemon=True)
    volume_thread.start()

    # Keep the script running
    while True:
        time.sleep(1)
