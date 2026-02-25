import asyncio

import machine
from machine import UART, Pin

REQ_READ_CFG = "READ_CFG"
REQ_SET_TEMP = "SET_TEMP"

RELAY_OPEN = "Off"
RELAY_CLOSED = "Heating"

VALID_CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.:\n\r"


class InvalidTransitionError(Exception):
    pass


class FSM(object):

    def __init__(self, debug=False):
        self.debug = debug
        self.state = "IDLE"
        self.transitions = {
            ("IDLE", "initialize_reporting"): "STREAMING",
            ("STREAMING", "request_detected"): "STOPPING",
            ("STOPPING", "receive_down"): {
                "is_read_request": "READING_CFG",
                "is_temp_request": "SETTING_TEMP",
            },
            ("READING_CFG", "receive_down"): "NOTIFYING",
            ("SETTING_TEMP", "receive_down"): "NOTIFYING",
            ("NOTIFYING", "dispatch_result"): "STREAMING",
        }

    def trigger(self, event, model):
        target = self.transitions[(self.state, event)]
        if isinstance(target, dict):
            for k, v in target.items():
                predicate = getattr(model, k)
                if predicate():
                    self.state = v
                    if self.debug:
                        print(f"Event '{event}' -> state '{self.state}'")
                    self.handle_enter_state(model)
                    return
            msg = (
                f"No valid transition from state '{self.state}' given event '{event}'."
            )
            raise InvalidTransitionError(msg)
        self.state = target
        if self.debug:
            print(f"Event '{event}' -> state '{self.state}'")
        self.handle_enter_state(model)

    def handle_enter_state(self, model):
        handler_name = f"on_enter_{self.state}".lower()
        if self.debug:
            print(f"Looking for handler '{handler_name}' on model ...")
        if hasattr(model, handler_name):
            if self.debug:
                print("Handler exists.  Calling ...")
            handler = getattr(model, handler_name)
            handler()
            if self.debug:
                print("Handler complete.")


def clean_bytes(bstring):
    return bstring.replace(b"\xa1\xe6", b"\xe2\x84\x83")


def clean_text(text):
    """
    Sometimes the UART returns some weird bytes instead of a comma.
    If the bytes are decodable as UTF-8, this can cause a parsing issue.
    Since the set of valid characters is limited, we can correct weird characters.
    """
    chars = []
    for c in text:
        if c in VALID_CHARSET:
            chars.append(c)
        else:
            chars.append(",")
    new_text = "".join(chars)
    return new_text


class NotificationList(object):
    def __init__(self):
        self._shared_task = None
        self.subscribers = 0

    async def get_result(self, coroutine):
        self.subscribers += 1
        if self._shared_task is None:
            self._shared_task = asyncio.create_task(coroutine)
        shared_task = self._shared_task
        result = await shared_task
        if shared_task is self._shared_task:
            self.reset()
        return result

    def reset(self):
        self._shared_task = None
        self.subscribers = 0


class Xyt01SerialInterface(object):

    def __init__(self, debug=False):
        self.debug = debug
        self.uart = UART(2, baudrate=9600, tx=Pin(4), rx=Pin(5))
        self.temp_c = None
        self.relay_state = RELAY_OPEN
        self.poll_task = None
        self.down_task = None
        self.stream_task = None
        self.request_queue = []
        self.read_notification_list = NotificationList()
        self.set_temp_notification_list = NotificationList()
        self.read_result_ready_event = asyncio.Event()
        self.read_result = None
        self.set_temp_complete_event = asyncio.Event()
        self.config_lines = None
        self.do_poll = False
        self.read_report = False
        self.machine = FSM(debug=debug)
        self.machine.trigger("initialize_reporting", self)

    @classmethod
    async def create(cls, debug=False):
        instance = cls(debug=debug)
        return instance

    async def poll_for_requests(self):
        request_queue = self.request_queue
        while self.do_poll:
            requests_exist = not (len(request_queue) == 0)
            if requests_exist and self.machine.state == "STREAMING":
                self.read_result_ready_event.clear()
                self.set_temp_complete_event.clear()
                self.machine.trigger("request_detected", self)
            else:
                await asyncio.sleep(1)
        if self.debug:
            print("poll_for_requests() task has exited.")

    async def read_down_code(self):
        await asyncio.sleep_ms(10)
        lines = await self.uart_read_until_match("DOWN")
        if self.machine.state == "READING_CFG":
            self.config_lines = lines
        self.machine.trigger("receive_down", self)

    async def read_from_report(self):
        await asyncio.sleep_ms(100)
        if self.debug:
            print("Starting task to read streaming temperature data from UART ...")
        uart = self.uart
        chunks = []
        lines = []
        no_data_count = 0
        while self.read_report:
            if uart.any():
                no_data_count = 0
                chunk = uart.read()
                if chunk:
                    if self.debug:
                        print(f"read_from_report() - UART received: {chunk}")
                    chunks.append(chunk)
                    if b"\r\n" in chunk:
                        combined = b"".join(chunks)
                        chunks.clear()
                        pos = combined.rfind(b"\r\n") + 2
                        completed = combined[:pos]
                        chunks.extend(chunks[pos:])
                        text = clean_bytes(completed).decode("utf-8")
                        lines = text.split("\r\n")
                        temp_c, relay_state = self.parse_report_line(lines[-2])
                        if self.debug:
                            print(
                                f"Parsed temperature: {temp_c}, relay_state: {relay_state}"
                            )
                        if temp_c is not None:
                            self.temp_c = temp_c
                            self.relay_state = relay_state
            else:
                no_data_count += 1
                if no_data_count >= 10:
                    if self.debug:
                        print(
                            "No data for 5 seconds.  Attempting to restart report ..."
                        )
                    uart.write("stop")
                    await asyncio.sleep_ms(100)
                    uart.write("start")
                    await asyncio.sleep_ms(100)
                    no_data_count = 0
            await asyncio.sleep_ms(500)
        if self.debug:
            print("read_from_report() task has exited.")

    def parse_report_line(self, line):
        """
        Parse a report line.
        Returns celcius, relay_state.
        """
        parts = line.split(",")
        if len(parts) != 2:
            return None, None
        try:
            celsius = float(parts[0][:-1])
        except ValueError:
            if self.debug:
                print(f"Could not parse: {line}")
            return None, None
        if parts[1] == "OP":
            relay_state = RELAY_CLOSED
        else:
            relay_state = RELAY_OPEN
        return celsius, relay_state

    async def uart_read_until_match(self, match):
        uart = self.uart
        chunks = []
        lines = []
        while True:
            if uart.any():
                chunk = uart.read()
                if chunk:
                    if self.debug:
                        print(f"uart_read_until_match() - UART received: {chunk}")
                    chunks.append(chunk)
                    if b"\r\n" in chunk:
                        combined = b"".join(chunks)
                        chunks.clear()
                        pos = combined.rfind(b"\r\n") + 2
                        completed = combined[:pos]
                        chunks.extend(chunks[pos:])
                        cleaned = clean_bytes(completed)
                        # cleaned.replace(b"\x11", b",")
                        # cleaned.replace(b"\xff", b",")
                        try:
                            text = cleaned.decode("utf-8", "replace")
                        except UnicodeError:
                            print(f"Failed to decode bytes: ->{cleaned}<-")
                            print("Resetting microcontrolled to enter a valid state.")
                            machine.reset()
                        text = text.replace("\ufffd", ",")
                        text = clean_text(text)
                        lines.extend(text.split("\r\n"))
                        last_line = lines[-2]
                        if last_line == match:
                            break
            await asyncio.sleep_ms(500)
        return lines

    def is_read_request(self):
        queue = self.request_queue
        if len(queue) > 0:
            req_type, data = queue[0]
            if req_type == REQ_READ_CFG:
                return True
        return False

    def is_temp_request(self):
        queue = self.request_queue
        if len(queue) > 0:
            req_type, data = queue[0]
            if req_type == REQ_SET_TEMP:
                return True
        return False

    async def on_read_result_ready(self):
        await self.read_result_ready_event.wait()
        if self.debug:
            print("Returning 'read' result ...")
        return self.read_result

    async def on_set_temp_complete(self):
        if self.debug:
            print("Returning from temperature set request.")
        await self.set_temp_complete_event.wait()

    def on_enter_streaming(self):
        if self.debug:
            print("Entered STREAMING state.")
        self.read_result_ready_event.clear()
        self.set_temp_complete_event.clear()
        self.do_poll = True
        self.poll_task = asyncio.create_task(self.poll_for_requests())
        self.uart.write("start")
        if self.debug:
            print("Wrote 'start' to UART.")
        self.read_report = True
        self.streaming_task = asyncio.create_task(self.read_from_report())

    def on_enter_stopping(self):
        if self.debug:
            print("Entered STOPPING state.")
        self.do_poll = False
        self.read_report = False
        self.uart.write("stop")
        if self.debug:
            print("Wrote 'stop' to UART.")
        asyncio.create_task(self.read_down_code())

    def on_enter_reading_cfg(self):
        self.uart.write("read")
        if self.debug:
            print("Wrote 'read' to UART.")
        self.down_task = asyncio.create_task(self.read_down_code())

    def on_enter_setting_temp(self):
        queue = self.request_queue
        req, temp_c = queue[0]
        ftemp_c = float(temp_c)
        itemp_c = int(ftemp_c)
        if itemp_c >= -50 and itemp_c <= -1:
            stemp_c = f"{itemp_c:03d}"
        elif itemp_c >= 0 and itemp_c < 100:
            stemp_c = f"{ftemp_c:04.1f}"
        elif itemp_c >= 100 and itemp_c <= 110:
            stemp_c = f"{itemp_c}:3d"
        else:
            raise ValueError(f"'{temp_c}' is an invalid temperature setting.")
        value = f"S:{stemp_c}"
        self.uart.write(value)
        if self.debug:
            print(f"Wrote '{value}' to UART.")
        self.down_task = asyncio.create_task(self.read_down_code())

    def on_enter_notifying(self):
        queue = self.request_queue
        if self.debug:
            print("Request queue:", queue)
        if self.is_read_request():
            if self.debug:
                print("Clearing out read requests from queue.")
            keep = [req for req in queue if req[0] != REQ_READ_CFG]
            queue.clear()
            queue.extend(keep)
            self.read_result = self.parse_read_result_lines()
            self.read_result_ready_event.set()
        elif self.is_temp_request():
            if self.debug:
                print("Clearing out last set-temperature request.")
            keep = queue[1:]
            queue.clear()
            queue.extend(keep)
            self.set_temp_complete_event.set()
        if self.debug:
            print("Request queue:", queue)
        self.machine.trigger("dispatch_result", self)

    def parse_read_result_lines(self):
        lines = self.config_lines
        config = {}
        line = lines[0]
        line = line.replace("\n", ",")
        line = line.replace("\r", ",")
        fields = line.split(",")
        if len(fields) != 3:
            return {
                "mode": "???",
                "target_temperature": "???",
                "hysteresis_temperature": "???",
                "alarm_temperature": "???",
                "delay_starting_time": "???",
                "temperature_correction": "???",
            }
        config["mode"] = fields[0]
        config["target_temperature"] = fields[1]
        config["hysteresis_temperature"] = fields[2]
        fields = lines[1].split(",")
        config["alarm_temperature"] = fields[0].split(":")[1]
        config["delay_starting_time"] = fields[1].split(":")[1]
        config["temperature_correction"] = fields[2].split(":")[1]
        return config

    def get_temperature(self):
        celsius = self.temp_c
        if celsius is None:
            return None, None
        farenheit = celsius * (9 / 5) + 32
        relay_state = self.relay_state
        if self.debug:
            print(f"Temperature: {celsius:.1f} C, {farenheit:.1f} F")
            print(f"Status: {relay_state}")
            print("--------------------")
        return celsius, farenheit, relay_state

    async def request_settings(self):
        self.request_queue.append((REQ_READ_CFG, None))
        task = self.read_notification_list.get_result(self.on_read_result_ready())
        result = await task
        return result

    async def set_target_temperature(self, temp_c):
        self.request_queue.append((REQ_SET_TEMP, temp_c))
        task = self.set_temp_notification_list.get_result(self.on_set_temp_complete())
        await task
