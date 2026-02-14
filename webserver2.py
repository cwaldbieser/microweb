#! /usr/bin/env python

import asyncio
import json
from time import sleep

import network
from microdot import Microdot

from wificonfig import passwd as wifi_passwd
from wificonfig import ssid
from xyt01 import Xyt01SerialInterface

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

# XT01 serial interface
uart = None

# Web server
app = Microdot()


# Routes
@app.route("/")
async def index(request):
    temp_c, temp_f = uart.get_temperature()
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


@app.route("/settings")
async def settings(request):
    print("REQUESTING CONFIG")
    config = await uart.request_settings()
    print(f"CONFIG: {json.dumps(config)}")
    return (
        (
            "<html>"
            "<head></head>"
            "<body>"
            "<table style='font-size: 48px; text-align: right;'>"
            "<thead><td>Setting</td><td>Value</td></thead>"
            "<tbody>"
            "<tr><td>Mode</td>"
            f"<td>{config['mode']}</td></tr>"
            "<tr><td>Target Temperature</td>"
            f"<td>{config['target_temperature']}</td></tr>"
            "<tr><td>Hysteresis Temperature</td>"
            f"<td>{config['hysteresis_temperature']}</td></tr>"
            "<tr><td>Alarm Temperature</td>"
            f"<td>{config['alarm_temperature']}</td></tr>"
            "<tr><td>Delay Starting Time</td>"
            f"<td>{config['delay_starting_time']}</td></tr>"
            "<tr><td>Temperature Correction</td>"
            f"<td>{config['temperature_correction']}</td></tr>"
            "</tbody>"
            "</table>"
            "</body>"
            "</html>"
        ),
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@app.route("/set-temperature", methods=["GET", "POST"])
async def set_temperature(request):
    if request.method == "GET":
        return (
            (
                "<html>"
                "<head>"
                "<title>Set Target Temperature</title>"
                "</head>"
                "<body>"
                "<form method='POST' action=''>"
                "   <div style='display: block; font-size:40pt;'>"
                "   <label for='temperature'>Target Temperature</label>"
                "   <input name='temperature' type='number' step='0.1' value='30' "
                "       style='font-size:40pt;' />"
                "   <label for='unit'>Unit</label>"
                "   <input name='unit' type='radio' value='C' checked"
                "       style='font-size:40pt;'>℃"
                "   <input name='unit' type='radio' value='F'"
                "       style='font-size:40pt;'>℉"
                "   </div>"
                "   <button type='submit'>Submit</button>"
                "</form>"
                "</body>"
                "</html>"
            ),
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )
    elif request.method == "POST":
        temperature = request.form.get("temperature")
        unit = request.form.get("unit")
        if unit == "F":
            temperature = round((float(temperature) - 32) * (5 / 9), 1)
        await uart.set_target_temperature(temperature)
        return (
            (
                "<html>"
                "<head>"
                "<title>Set Target Temperature</title>"
                "</head>"
                "<body style='font-size:40pt;'>"
                f"Target temperature set to {temperature} {unit}"
                "</body>"
                "</html>"
            ),
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )


async def main():
    """
    Start the web server in asyncio mode.
    """
    global uart
    debug = True
    uart = await Xyt01SerialInterface.create(debug=debug)
    await app.start_server(port=80, debug=True)


asyncio.run(main())
