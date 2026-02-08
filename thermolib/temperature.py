from time import sleep

from machine import UART, Pin

READ_TIMEOUT = 10


def init_xyt01_uart():
    """
    Initialize the XY-T01 UART.
    """
    uart = UART(2, baudrate=9600, tx=Pin(4), rx=Pin(5))
    print("Sendng 'start' command to XY-T01 ...")
    uart.write("start")
    sleep(1)
    while uart.any():
        print(uart.readline())
    return uart


def get_temperature(uart):
    """
    Stores the current temperature via the XY-T01 UART interface
    """
    celsius = None
    farenheit = None
    for line in read_uart(uart):
        print(f"Raw line: {line}", end="")
        if line.strip() == "":
            continue
        celsius, relay_state = parse_report_line(line)
        if celsius is None:
            print("Returned None, None.  Skipping ...")
            continue
        farenheit = celsius * (9 / 5) + 32
        print(f"Temperature: {celsius:.1f} C, {farenheit:.1f} F")
        print(f"Relay state: {relay_state}")
        print("--------------------")
    return celsius, farenheit


def read_complete_line_from_uart(uart):
    parts = []
    for n in range(READ_TIMEOUT):
        print(f"Attempt {n}:")
        if uart.any():
            x = uart.readline()
            print(f"Read the follwing data from the UART: {x}")
            parts.append(x)
            condition = x.endswith(b"\r\n")
            if condition:
                return b"".join(parts)
        sleep(1)
    return None


def read_uart(uart):
    """
    Read from the XY-T01 UART (serial interface).
    """
    print("Entered read_uart().")
    print(f"uart.any(): {uart.any()}")
    while uart.any():
        x = read_complete_line_from_uart(uart)
        if x is None:
            continue
        x = x.replace(b"\xa1\xe6", b"\xe2\x84\x83")
        try:
            decoded = x.decode()
        except UnicodeError:
            print(f"Could not decode to ASCII: {x}")
            return ""
        yield decoded


def parse_report_line(line):
    """
    Parse a report line.
    Returns celcius, relay_state.
    """
    line = line.strip()
    parts = line.split(",")
    if len(parts) != 2:
        return None, None
    try:
        celsius = float(parts[0][:-1])
    except ValueError:
        print(f"Could not parse: {line}")
        return None, None
    if parts[1] == "OP":
        relay_state = "CLOSED"
    else:
        relay_state = "OPEN"
    return celsius, relay_state
