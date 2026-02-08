import asyncio

from machine import UART, Pin

temp_reporting_mode = False
last_report_line = ""


def init_xyt01_uart():
    """
    Initialize the XY-T01 UART.
    """
    uart = UART(2, baudrate=9600, tx=Pin(4), rx=Pin(5))
    return uart


def start_temperature_report(uart):
    global temp_reporting_mode
    uart.write("start")
    temp_reporting_mode = True


def stop_temperature_reporting_mode(uart):
    global temp_reporting_mode
    uart.write("stop")
    temp_reporting_mode = False


async def read_from_uart(uart):
    global last_report_line
    chunks = []
    while True:
        if uart.any():
            chunk = uart.read()
            if chunk:
                print(f"UART received: {chunk}")
                chunks.append(chunk)
                if b"\r\n" in chunk:
                    combined = b"".join(chunks)
                    chunks.clear()
                    lines = combined.split(b"\r\n")
                    # Change weird celsius symbol encoding to UTF-8.
                    last_report_line = (
                        lines[-2].replace(b"\xa1\xe6", b"\xe2\x84\x83").decode("utf-8")
                    )
                    last_chunk = lines[-1]
                    if last_chunk != b"":
                        chunks.append(last_chunk)
        await asyncio.sleep_ms(10)


def get_temperature():
    """
    Get the last reported temperature.
    """
    if not temp_reporting_mode:
        print("Must start temperature report before reading temperature!")
        return None, None
    celsius = None
    farenheit = None
    celsius, relay_state = parse_report_line()
    if celsius is None:
        print("Returned None, None.  Skipping ...")
        return None, None
    farenheit = celsius * (9 / 5) + 32
    print(f"Temperature: {celsius:.1f} C, {farenheit:.1f} F")
    print(f"Relay state: {relay_state}")
    print("--------------------")
    return celsius, farenheit


def parse_report_line():
    """
    Parse a report line.
    Returns celcius, relay_state.
    """
    parts = last_report_line.split(",")
    if len(parts) != 2:
        return None, None
    try:
        celsius = float(parts[0][:-1])
    except ValueError:
        print(f"Could not parse: {last_report_line}")
        return None, None
    if parts[1] == "OP":
        relay_state = "CLOSED"
    else:
        relay_state = "OPEN"
    return celsius, relay_state
