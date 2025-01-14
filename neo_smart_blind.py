import logging
import socket
import time

import requests

from .const import (
    CMD_UP,
    CMD_UP2,
    CMD_DOWN,
    CMD_DOWN2,
    CMD_STOP,
    CMD_FAV,
    CMD_FAV_1,
    CMD_FAV_2,
)

_LOGGER = logging.getLogger(__name__)
LOGGER = logging.getLogger()


class NeoSmartBlind:
    def __init__(self, host, the_id, device, close_time, port, protocol, rail, percent_support):
        self._host = host
        self._port = port
        self._protocol = protocol
        self._the_id = the_id
        self._device = device
        self._close_time = int(close_time)
        self._rail = rail
        self._percent_support = percent_support
        self._current_position = 50
        if self._percent_support:
            self._fav_check = 'tilt'
        else:
            self._fav_check = 'position'

    """Adjust the blind based on the pos value send"""
    def adjust_blind(self, pos):

        """Legacy support for using position to set favorites"""
        if self._fav_check == 'position' and (pos == 50 or pos == 51):
            self.set_fav_position(pos)
            return

        """Logic for blinds that support percent positioning"""
        if self._percent_support:
            """NeoBlinds works off of percent closed, but HA works off of percent open, so need to invert the percentage"""
            closed_pos = 100 - pos
            if pos > 98:
                """Unable to send 100 to the API so assume anything greater then 98 is just an open command"""
                self.open_cover()
                return
            if pos < 2:
                """Assume anything greater less than 2 is just a close command"""
                self.close_cover()
                return
            padded_position = f'{closed_pos:02}'
            LOGGER.info('Sending ' + padded_position)
            self.send_command(padded_position)
            self._current_position = pos
            return

        """Logic for blinds that do not support percent positioning"""
        if pos >= 52:
            self.up_command()
            wait1 = (pos - 50)*2
            wait = (wait1*self._close_time)/100
            LOGGER.info(wait)
            time.sleep(wait)
            self.send_command(CMD_STOP)
            return            
        if pos <= 49:
            self.down_command()
            wait1 = (50 - pos)*2
            wait = (wait1*self._close_time)/100
            LOGGER.info(wait)
            time.sleep(wait)
            self.send_command(CMD_STOP)
            return

    """Open blinds fully"""
    def open_cover(self):
        self.up_command()
        self._current_position = 100
        return

    """Close blinds fully"""
    def close_cover(self):
        self.down_command()
        self._current_position = 0
        return

    """Send down command with rail support"""
    def down_command(self):
        if self._rail == 1:
            self.send_command(CMD_DOWN)
        elif self._rail == 2:
            self.send_command(CMD_DOWN2)
        return

    """Send up command with rail support"""
    def up_command(self):
        if self._rail == 1:
            self.send_command(CMD_UP)
        elif self._rail == 2:
            self.send_command(CMD_UP2)
        return

    def adjust_blind_tilt(self, pos):
        LOGGER.info('Tilt position set to: ' + str(pos))
        self.set_fav_position(pos)
        return

    def set_fav_position(self, pos):
        LOGGER.info('Setting fav: ' + str(pos))
        if pos <= 50:
            self.send_command(CMD_FAV)
            self._current_position = 50
            return
        if pos >= 51:
            self.send_command(CMD_FAV_2)
            self._current_position = 51
            return
        return

    def get_position(self):
        LOGGER.info('Current Position is: ' + str(self._current_position))
        return self._current_position

    def send_command(self, command):
        """Command handler to send based on correct protocol"""
        if str(self._protocol).lower() == "http":
            self.send_command_http(command)

        elif str(self._protocol).lower() == "tcp":
            self.send_command_tcp(command)

        else:
            LOGGER.error("NeoSmartBlinds, Unknown protocol: {}, please use: http or tcp".format(self._protocol))

    def send_command_tcp(self, code):
        """Command sender for TCP"""

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)

            command = self._device + "-" + code + '\r\n'
            LOGGER.info("NeoSmartBlinds, Sending command: {}".format(command))
            s.connect((self._host, self._port))
            while True:
                s.send(command)
        except socket.error:
            LOGGER.exception(socket.error.strerror)
            return

    def send_command_http(self, command):
        """Command sender for HTTP"""
        url = "http://{}:{}/neo/v1/transmit".format(self._host, self._port)

        params = {'id': self._the_id, 'command': self._device + "-" + command, 'hash': str(time.time()).strip(".")[-7:]}

        r = requests.get(url=url, params=params)

        LOGGER.info("Sent: {}".format(r.url))
        LOGGER.info("Neo Hub Responded with - {}".format(r.text))

        """Check for error code and log"""
        if r.status_code != 200:
            LOGGER.error("Status Code - {}".format(r.status_code))
