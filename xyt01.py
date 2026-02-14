import asyncio

from machine import UART, Pin

MODE_UNINITIALIZED = -1
MODE_START_REPORTING = 0
MODE_STOP_REPORTING = 1
MODE_READ_CONFIGURATION = 2
debug = False
uart_mode = MODE_UNINITIALIZED
last_report_line = ""
next_mode = None
xyt01_config = {}


def init_xyt01_uart():
    """
    Initialize the XY-T01 UART.
    """
    uart = UART(2, baudrate=9600, tx=Pin(4), rx=Pin(5))
    return uart


def start_temperature_report():
    global uart_mode
    uart_mode = MODE_START_REPORTING


def stop_temperature_report():
    global uart_mode
    global next_mode
    uart_mode = MODE_STOP_REPORTING
    next_mode = MODE_UNINITIALIZED


async def request_config(uart):
    global uart_mode
    global next_mode
    uart.write("stop")
    uart_mode = MODE_STOP_REPORTING
    next_mode = MODE_READ_CONFIGURATION
    xyt01_config.clear()
    while uart_mode != MODE_START_REPORTING:
        await asyncio.sleep(1)
    return dict(xyt01_config)


async def read_from_uart(uart):
    global uart_mode
    while True:
        if uart_mode == MODE_START_REPORTING:
            await asyncio.create_task(read_temperature_report_from_uart(uart))
        elif uart_mode == MODE_STOP_REPORTING:
            await asyncio.create_task(read_until_down_code_from_uart(uart))
            if next_mode:
                uart_mode = next_mode
            else:
                uart_mode = MODE_UNINITIALIZED
        elif uart_mode == MODE_READ_CONFIGURATION:
            await asyncio.sleep(1)
            await asyncio.create_task(read_configuration_from_uart(uart))
            uart_mode = MODE_START_REPORTING
        else:
            await asyncio.sleep_ms(10)


async def read_configuration_from_uart(uart):
    uart.write("read")
    chunks = []
    while uart_mode == MODE_READ_CONFIGURATION:
        if uart.any():
            chunk = uart.read()
            if chunk:
                if debug:
                    print(f"UART received: {chunk}")
                chunks.append(chunk)
                if b"\r\n" in chunk:
                    combined = b"".join(chunks)
                    lines = combined.split(b"\r\n")
                    # Change weird celsius symbol encoding to UTF-8.
                    last_line = (
                        lines[-2].replace(b"\xa1\xe6", b"\xe2\x84\x83").decode("utf-8")
                    )
                    if last_line == "DOWN":
                        break
        await asyncio.sleep(1)
    bstring = b"".join(chunks)
    text = bstring.replace(b"\xa1\xe6", b"\xe2\x84\x83").decode("utf-8")
    lines = text.split("\r\n")
    xyt01_config.clear()
    if len(lines) != 4:
        return
    fields = lines[0].split(",")
    xyt01_config["mode"] = fields[0]
    xyt01_config["target_temperature"] = fields[1]
    xyt01_config["hysteresis_temperature"] = fields[2]
    fields = lines[1].split(",")
    xyt01_config["alarm_temperature"] = fields[0].split(":")[1]
    xyt01_config["delay_starting_time"] = fields[1].split(":")[1]
    xyt01_config["temperature_correction"] = fields[2].split(":")[1]


async def read_until_down_code_from_uart(uart):
    uart.write("stop")
    await asyncio.sleep(1)
    chunks = []
    while uart_mode == MODE_STOP_REPORTING:
        if uart.any():
            chunk = uart.read()
            if chunk:
                if debug:
                    print(f"UART received: {chunk}")
                chunks.append(chunk)
                if b"\r\n" in chunk:
                    combined = b"".join(chunks)
                    chunks.clear()
                    lines = combined.split(b"\r\n")
                    # Change weird celsius symbol encoding to UTF-8.
                    last_line = (
                        lines[-2].replace(b"\xa1\xe6", b"\xe2\x84\x83").decode("utf-8")
                    )
                    if last_line == "DOWN":
                        break
                    last_chunk = lines[-1]
                    if last_chunk != b"":
                        chunks.append(last_chunk)
        await asyncio.sleep_ms(10)


async def read_temperature_report_from_uart(uart):
    uart.write("start")
    await asyncio.sleep(1)
    global last_report_line
    chunks = []
    while uart_mode == MODE_START_REPORTING:
        if uart.any():
            chunk = uart.read()
            if chunk:
                if debug:
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
    if uart_mode != MODE_START_REPORTING:
        print("Must start temperature report before reading temperature!")
        return None, None
    celsius = None
    farenheit = None
    celsius, relay_state = parse_report_line()
    if celsius is None:
        return None, None
    farenheit = celsius * (9 / 5) + 32
    if debug:
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
        if debug:
            print(f"Could not parse: {last_report_line}")
        return None, None
    if parts[1] == "OP":
        relay_state = "CLOSED"
    else:
        relay_state = "OPEN"
    return celsius, relay_state
