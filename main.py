#! /usr/bin/env python

import asyncio
import json
import sys
from time import sleep

import machine
import network
import utime
from microdot import Microdot, redirect
from utemplate import source

from wificonfig import passwd as wifi_passwd
from wificonfig import ssid
from xyt01 import Xyt01SerialInterface

target_temperature = 30.0


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
loader = source.Loader("__main__", "templates")


# Routes
@app.route("/")
async def index(request):
    global target_temperature
    temp_c, temp_f, relay_state = uart.get_temperature()
    if temp_c is None:
        return "Could not determine temperature."
    render = loader.load("index.tpl")
    stemp_c = f"{temp_c:.1f}"
    stemp_f = f"{temp_f:.1f}"
    submit = request.args.get("submit")
    reset = request.args.get("reset")
    if reset is not None:
        target_c = float(target_temperature)
    else:
        target_c = float(request.args.get("target_temperature", target_temperature))
    adj = request.args.get("adj")
    if adj == "up":
        target_c += 1.0
        target_c = round(target_c)
    elif adj == "down":
        target_c -= 1.0
        target_c = round(target_c)
    starget_c = f"{target_c:.1f}"
    starget_f = f"{target_c * (9/5) + 32:.1f}"
    if submit is not None:
        await uart.set_target_temperature(target_c)
        target_temperature = target_c
        await asyncio.sleep(1)
        return redirect(request.path)
    html = render(stemp_c, stemp_f, relay_state, starget_c, starget_f)
    return (
        html,
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@app.route("/style.css")
async def style(request):
    with open("/www/style.css", "r") as f:
        css = f.read()
    return (css, 200, {"Content-Type": "text/css; charset=utf-8"})


@app.route("/settings")
async def settings(request):
    print("REQUESTING CONFIG")
    config = await uart.request_settings()
    print(f"CONFIG: {json.dumps(config)}")
    render = loader.load("settings.tpl")
    firmware = sys.version
    rssi = nic.status("rssi")
    hysteresis = config["hysteresis_temperature"]
    alarm_temperature = config["alarm_temperature"]
    delay = config["delay_starting_time"]
    correction = config["temperature_correction"]
    uptime = utime.ticks_ms() // 1000
    html = render(
        firmware,
        uptime,
        rssi,
        ip_addr,
        hysteresis,
        alarm_temperature,
        delay,
        correction,
    )
    return (
        html,
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


@app.route("/reboot", methods=["GET"])
async def reboot(request):
    asyncio.create_task(one_time_reboot())
    print(f"UART config lines: {uart.config_lines}")
    return redirect("/")


@app.route("/reset-xyt01", methods=["GET"])
async def reset_xyt01(request):
    await uart.reset_xyt01()
    return redirect("/")


@app.route("/debug")
async def debug(request):
    uart_command = request.args.get("uart")
    if uart_command is not None:
        uart.uart.write(uart_command)
    print(f"Wrote '{uart_command}' to UART.")
    return redirect("/")


# Scheduled tasks


async def get_current_target_temperature():
    global target_temperature
    while True:
        config = await uart.request_settings()
        target_temperature = config["target_temperature"]
        await asyncio.sleep(120)


async def one_time_reboot():
    await asyncio.sleep(10)
    print("Rebooting ...")
    machine.reset()


async def periodic_reboot():
    await asyncio.sleep(3600)
    print("Rebooting ...")
    machine.reset()


async def main():
    """
    Start the web server in asyncio mode.
    """
    global uart
    debug = True
    uart = await Xyt01SerialInterface.create(debug=debug)
    asyncio.create_task(get_current_target_temperature())
    # asyncio.create_task(periodic_reboot())
    await app.start_server(port=80, debug=True)


asyncio.run(main())
