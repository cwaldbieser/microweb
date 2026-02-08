#! /usr/bin/env python

import asyncio
from time import sleep

import network
from microdot import Microdot

from thermolib.temperature import (get_temperature, init_xyt01_uart,
                                   read_from_uart, start_temperature_report)
from wificonfig import passwd as wifi_passwd
from wificonfig import ssid

# network configuration
new_hostname = "thermostat01"
nic = network.WLAN(network.STA_IF)
nic.active(True)
try:
    nic.config(hostname=new_hostname, pm=network.WLAN.PM_NONE)
except TypeError:
    print(
        "Setting hostname via config() not supported on this port."
        " Default hostname will be used."
    )
print(f"Constant for no power management: {network.WLAN.PM_NONE}")
print(f"NIC power management: {nic.config('pm')}")
nic.connect(ssid, wifi_passwd)
print("Waiting for connection...")
while not nic.isconnected():
    sleep(1)
ip_addr = nic.ifconfig()[0]
print("Connected! IP address:", ip_addr)
print(f"Device should be reachable at http://{new_hostname}.local")

# Start UART reporting
uart = init_xyt01_uart()
print("UART initialized.")
start_temperature_report(uart)
print("Started temperature reporting mode.")

# Web server
app = Microdot()


# Routes
@app.route("/")
async def index(request):
    temp_c, temp_f = get_temperature()
    if temp_c is None:
        return "Could not determine temperature."
    return (
        (
            "<html><head><meta http-equiv='refresh' content='60'></head><body>"
            "<h1 style='font-size: 48px;'>"
            f"Temperature {temp_c:.1f} ℃ ({temp_f:.1f} ℉) </h1></body>"
        ),
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


async def main():
    """
    Start the web server in asyncio mode.
    """
    asyncio.create_task(read_from_uart(uart))
    await app.start_server(port=80, debug=True)


asyncio.run(main())
