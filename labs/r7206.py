#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Test Script.
To run this lab:
* Start GNS3 by executing "./gn3_run.sh" in a Terminal window.
* Select Lab00 from the Projects library.
* Start all devices.

If Lab00 does not exist, follow the instructions in DEMO.md to create the lab.

Project: Automation

Requirements:
- Python 2.7.5
"""
from __future__ import print_function

import argparse
import difflib
import logging
import os
import shlex
import socket
import subprocess
import sys
import telnetlib
import time

import pexpect

from labs import CiscoRouter  # Super class!

# Enable error and exception logging
logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.NOTSET,
                    filename="labs.log",
                    format="%(asctime)sUTC: %(levelname)s:%(name)s:%(message)s")

TFTP_DIR = "/var/lib/tftpboot"


class Ramon7206(CiscoRouter):
    @property
    def config_file_path(self):
        return self._config_file_path

    @property
    def device_ip_address(self):
        return self._device_ip_address

    @property
    def subnet_mask(self):
        return self._subnet_mask

    @property
    def host_ip_address(self):
        return self._host_ip_address

    def __init__(self, config_file_path, device_ip_address, subnet_mask, host_ip_address):
        self._device_ip_address = Utilities.validate_ip_address(device_ip_address)
        self._subnet_mask = Utilities.validate_subnet_mask(subnet_mask)
        self._config_file_path = Utilities.validate_file_path(config_file_path)
        self._host_ip_address = Utilities.validate_ip_address(host_ip_address)

    def run(self, ui_messenger, **kwargs):
        try:
            ui_messenger.info("Hello from Cisco Ramon!")
            child = self._connect_to_device(ui_messenger, **kwargs)
            self._transfer_files(child, ui_messenger, **kwargs)
            self._disconnect_from_device(child, ui_messenger, **kwargs)
        except pexpect.exceptions.ExceptionPexpect:
            ex_type, ex_value, ex_traceback = sys.exc_info()
            ui_messenger.error("Type {0}: {1} in {2} at line {3}.".format(
                ex_type.__name__,
                ex_value,
                ex_traceback.tb_frame.f_code.co_filename,
                ex_traceback.tb_lineno))
        finally:
            ui_messenger.info("Good-bye from Cisco Ramon.")

    def _setup_host(self):
        pass

    def _connect_to_device(self, ui_messenger, **kwargs):
        child = pexpect.spawn("telnet {0}".format(self._device_ip_address))
        return child

    def _setup_device(self):
        pass

    def _transfer_files(self, child, ui_messenger, **kwargs):
        try:
            utility = Utilities()
            utility.enable_tftp(ui_messenger)
        finally:
            utility.disable_tftp(ui_messenger)

    def _verify_device_configuration(self):
        pass

    def _disconnect_from_device(self, child, ui_messenger, **kwargs):
        child.close()


class Utilities(object):
    # Function return values
    SUCCESS = 0
    FAIL = 1
    ERROR = 2

    @staticmethod
    def validate_file_path(file_path):
        """Checks that the file exists. The private method double_check() takes into account
        misspelled or incorrectly formatted file paths, such as var/lib/tftpbootc7206-config.cfg

        :param file_path: The path to the file.
        :type file_path: str

        :return: The valid file path.
        :rtype: str

        :raises ValueError: If the argument is invalid, or the file permissions are
            incorrect and cannot be reset.
        """
        if file_path is not None and file_path.strip():
            file_path = file_path.strip()
            # Hide stdout, but show stderr; use os.devnull instead of
            # subprocess.DEVNULL in Python 2.7.
            with open(os.devnull, "w") as quiet:
                # Check if file exists
                cmd = "ls {0}".format(file_path)
                retcode = subprocess.call(shlex.split(cmd), stdout=quiet, stderr=quiet)
                if retcode == 0:
                    pass
                else:
                    # Double check using ML if the file does not exist
                    best_match = Utilities._double_check(file_path)
                    if best_match is None:
                        raise ValueError("{0} does not exist.".format(file_path))
                    else:
                        file_path = best_match

            # Check the file's permissions
            try:
                cmd = "stat -c %a {0}".format(file_path)
                result = subprocess.check_output(shlex.split(cmd))
                if int(result) < 644:
                    cmd = "sudo chmod 644 {0}".format(file_path)
                    retcode = subprocess.call(shlex.split(cmd))
                    if retcode == 0:
                        pass
                    else:
                        raise RuntimeError("Cannot change permissions for {0}.".format(
                            file_path))
            except subprocess.CalledProcessError as cpe:
                raise RuntimeError(
                    "Unable to check permissions for {0}: {1}".format(file_path, cpe.output))
            return file_path
        else:
            raise ValueError("Invalid file path: {0}.".format(file_path))

    @staticmethod
    def _double_check(file_path):
        """Looks for file paths that may have been misspelled or incorrectly
        formatted, such as var/lib/tftpbootc7206-config.cfg

        :param file_path: The path to the file.
        :type file_path: str

        :return: The valid file path or None if not found.
        :rtype: str

        :raises IndexError: If the file type cannot be identified.
        """
        # Get the extension of the file and create a wildcard
        try:
            file_type = "*.{0}".format(file_path.rsplit(".", 1)[1])
        except IndexError:
            return None
        # Create a pool of files with the same extension
        args = shlex.split("find / -name '{0}'".format(file_type))
        p1 = subprocess.Popen(args, stdout=subprocess.PIPE,
                              stderr=open(os.devnull, "w"))
        p2 = subprocess.Popen(["grep", "-v", "Permission denied"], stdin=p1.stdout,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        possibilities, err = p2.communicate()
        # Find the best match to the file name within the pool, if any
        if possibilities:
            return difflib.get_close_matches(file_path, possibilities.decode("utf-8").splitlines(), n=1)[0]

    @staticmethod
    def validate_ip_address(ip_address, ipv4_only=True):
        """Checks that the argument is a valid IP address.

        :param ip_address: The IP address to check.
        :type ip_address: str
        :param ipv4_only: If the method should only validate for IPv4-type
            addresses.
        :type ipv4_only: bool

        :return: The valid IP address.
        :rtype: str

        :raises ValueError: If the argument is invalid.
        """
        if ip_address is not None and ip_address.strip():
            # Check if the IP address is valid (AF_INET for IPv4, AF_INET6 for
            # IPv6); raise an exception if invalid.
            ip_address = ip_address.strip()
            try:
                socket.inet_pton(socket.AF_INET, ip_address)
                return ip_address
            except socket.error:
                if ipv4_only:
                    raise ValueError(
                        "Argument contains an invalid IPv4 address: {0}".format(
                            ip_address))
                else:
                    try:
                        socket.inet_pton(socket.AF_INET6, ip_address)
                        return ip_address
                    except socket.error:
                        raise ValueError(
                            "Argument contains an invalid IP address: {0}".format(
                                ip_address))
        else:
            raise ValueError(
                "Argument contains an invalid IP address: {0}".format(ip_address))

    @staticmethod
    def validate_subnet_mask(subnet_mask):
        """Checks that the argument is a valid subnet mask.

        :param subnet_mask: The subnet mask to check.
        :type subnet_mask: str

        :return: The valid subnet mask.
        :rtype: str

        :raises ValueError: if the argument is invalid.

        .. seealso::
            https://codereview.stackexchange.com/questions/209243/verify-a-subnet-mask-for-validity-in-python
        """
        if subnet_mask is not None and subnet_mask.strip():
            a, b, c, d = (int(octet) for octet in subnet_mask.split("."))
            mask = a << 24 | b << 16 | c << 8 | d
            if mask == 0:
                raise ValueError("Invalid subnet mask: {0}".format(subnet_mask))
            else:
                # Count the number of consecutive 0 bits at the right.
                # https://wiki.python.org/moin/BitManipulation#lowestSet.28.29
                m = mask & -mask
                right0bits = -1
                while m:
                    m >>= 1
                    right0bits += 1
                # Verify that all the bits to the left are 1"s
                if mask | ((1 << right0bits) - 1) != 0xffffffff:
                    raise ValueError(
                        "Invalid subnet mask: {0}".format(subnet_mask))
            return subnet_mask
        else:
            raise ValueError("Invalid subnet mask: {0}.".format(subnet_mask))

    def enable_tftp(self, ui_messenger, **kwargs):
        """This function:

        * Verifies the default TFTP directory exists (/var/lib/tftpboot) and it
          has the correct permissions
        * Enables the TFTP service, opens the firewall, and starts the TFTP server.

        :returns: True if the function succeeded or raises a RuntimeError.
        :rtype: bool

        :raises RuntimeError: If unable to enable the TFTP service.
        """
        cmd = retcode = dir_permissions = None
        rval = self.FAIL
        try:
            ui_messenger.info("Checking if the tftpboot directory exists...")
            dir_exists = os.path.isdir(TFTP_DIR)
            if not dir_exists:
                ui_messenger.warning("tftpboot directory does not exist. Creating...")
                cmd = "sudo mkdir -p -m755 {0}".format(TFTP_DIR)
                retcode = subprocess.call(shlex.split(cmd))
                if retcode == 0:
                    ui_messenger.info("tftpboot directory created.")
                else:
                    raise RuntimeError("Unable to create tftpboot directory.")
            else:
                ui_messenger.info("Directory exists: Good to go...")

            ui_messenger.info(
                "Checking that the tftpboot directory has the correct permissions (i.e., 755+)...")
            try:
                dir_permissions = subprocess.check_output(["stat", "-c", "%a", TFTP_DIR])
                if int(dir_permissions) < 755:
                    ui_messenger.warning(
                        "Incorrect permissions for tftpboot directory: Correcting...")
                    cmd = "sudo chmod 755 {0}".format(TFTP_DIR)
                    retcode = subprocess.call(shlex.split(cmd))
                    if retcode == 0:
                        ui_messenger.info("tftpboot directory permissions corrected.")
                    else:
                        raise RuntimeError("Unable to correct tftpboot directory permissions.")
                else:
                    ui_messenger.info("Permissions correct: Good to go...")
            except subprocess.CalledProcessError as cpe:
                raise RuntimeError(
                    "Unable to check tftpboot directory permission: {0}".format(cpe.output))

            """
            ui_messenger.info(
                "Checking that the TFTP service configuration file has the correct permissions (i.e., 666+)...")
            try:
                dir_permissions = subprocess.check_output(["stat", "-c", "%a", "/etc/xinetd.d/tftp"])
                if int(dir_permissions) < 666:
                    ui_messenger.warning(
                        "Incorrect permissions for TFTP service configuration file: Correcting...")
                    cmd = "sudo chmod 666 {0}".format("/etc/xinetd.d/tftp")
                    retcode = subprocess.call(shlex.split(cmd))
                    if retcode == 0:
                        ui_messenger.info("TFTP service configuration file permissions corrected.")
                    else:
                        raise RuntimeError("Unable to correct TFTP service configuration file permissions.")
                else:
                    ui_messenger.info("Permissions correct: Good to go...")
            except subprocess.CalledProcessError as cpe:
                raise RuntimeError(
                    "Unable to check TFTP service configuration file permission: {0}".format(cpe.output))
            """

            ui_messenger.info("Modifying the TFTP service configuration...")
            cmd = (
                "sudo sed -i 's/server_args             = -s \/var\/lib\/tftpboot/server_args             = -c -s \/var\/lib\/tftpboot/g' /etc/xinetd.d/tftp",
                "sudo sed -i 's/disable                 = yes/disable                 = no/g' /etc/xinetd.d/tftp")
            for i, c in enumerate(cmd, 1):
                # print(shlex.split(c))
                retcode = subprocess.call(shlex.split(c))
                if retcode == 0:
                    print("TFTP configuration set to enabled ({0}/2)".format(i))
                else:
                    raise RuntimeError("Unable to set TFTP configuration to enabled ({0}/2)".format(i))

            ui_messenger.info("Allowing TFTP traffic through firewall...")
            cmd = "sudo firewall-cmd --zone=public --add-service=tftp"
            retcode = subprocess.call(shlex.split(cmd))
            if retcode == 0:
                ui_messenger.info("Firewall settings modified.")
            else:
                raise RuntimeError("Unable to modify firewall settings.")

            ui_messenger.info("Starting the TFTP server...")
            cmd = "sudo systemctl start tftp"
            retcode = subprocess.call(shlex.split(cmd))
            if retcode == 0:
                ui_messenger.info("TFTP service started.")
            else:
                raise RuntimeError("Unable to start the TFTP service.")

            ui_messenger.info("Enabling the TFTP server...")
            cmd = "sudo systemctl enable tftp"
            retcode = subprocess.call(shlex.split(cmd))
            if retcode == 0:
                ui_messenger.info("TFTP service enabled.")
            else:
                raise RuntimeError("Unable to enable the TFTP service.")

            ui_messenger.info("Don\"t forget to reset the TFTP service configuration before " +
                              "shutting down the machine!!!")
            rval = self.SUCCESS
        except RuntimeError:
            rval = self.ERROR
            raise RuntimeError("Unable to enable the TFTP service: {0}".format(sys.exc_info()))
        return rval

    def disable_tftp(self, ui_messenger, **kwargs):
        """Disable the TFTP service, close the firewall, and shutdown the TFTP
        server.

        :returns: If the function succeeded (0); if it failed (1); or if there was
            an error (2).
        :rtype: int

        :raises RuntimeError: If unable to disable the TFTP service.
        """
        cmd = retcode = None
        rval = self.FAIL
        try:
            # Disable the TFTP service and stop the TFTP server
            ui_messenger.info("Resetting the TFTP service configuration...")
            cmd = (
                "sudo sed -i 's/server_args             = -c -s \/var\/lib\/tftpboot/server_args             = -s \/var\/lib\/tftpboot/g' /etc/xinetd.d/tftp",
                "sudo sed -i 's/disable                 = no/disable                 = yes/g' /etc/xinetd.d/tftp")
            for i, c in enumerate(cmd, 1):
                # print(shlex.split(c))
                retcode = subprocess.call(shlex.split(c))
                if retcode == 0:
                    print("TFTP settings set to disabled ({0}/2)".format(i))
                else:
                    raise RuntimeError("Unable to set TFTP settings to disabled ({0}/2)".format(i))

            ui_messenger.info("Blocking TFTP traffic through firewall...")
            cmd = "sudo firewall-cmd --zone=public --remove-service=tftp"
            retcode = subprocess.call(shlex.split(cmd))
            if retcode == 0:
                ui_messenger.info("Firewall settings modified.")
            else:
                raise RuntimeError("Unable to modify firewall settings.")

            ui_messenger.info("Stopping the TFTP service...")
            cmd = "sudo systemctl stop tftp"
            retcode = subprocess.call(shlex.split(cmd))
            if retcode == 0:
                ui_messenger.info("TFTP service stopped.")
            else:
                raise RuntimeError("Unable to stop the TFTP service.")

            ui_messenger.info("Disabling the TFTP service...")
            cmd = "sudo systemctl disable tftp"
            retcode = subprocess.call(shlex.split(cmd))
            if retcode == 0:
                ui_messenger.info("TFTP service disabled.")
            else:
                raise RuntimeError("Unable to disable the TFTP service.")

            rval = self.SUCCESS
        except RuntimeError:
            rval = self.ERROR
            raise RuntimeError("Unable to disable the TFTP service: {0}".format(sys.exc_info()))
        return rval

    @staticmethod
    def pexpect_run_wrapper(cmd, timeout=30, error_message=None):
        child_result, child_exitstatus = pexpect.run(cmd, timeout=timeout, withexitstatus=True)
        if child_exitstatus == 0:
            return child_result
        else:
            raise RuntimeError(error_message if error_message else child_result.decode("utf-8"))


class UserInterface(object):
    @staticmethod
    def info(msg):
        print("Message: {0}".format(msg))

    @staticmethod
    def debug(msg):
        print("Debug: {0}".format(msg))

    @staticmethod
    def warning(msg):
        print("Warning: {0}".format(msg))

    @staticmethod
    def error(msg):
        print("Error: {0}".format(msg))


if __name__ == "__main__":
    # To maintain scope, create empty class containers here
    ui_messenger = r7206 = object()
    cmd = retcode = None

    # Only catch errors and exceptions due to invalid inputs or incorrectly connected devices.
    # Programming and logic errors will be reported and corrected through user feedback
    try:
        # Instantiate the user interface messaging object here,
        # since it does not have error-handling code
        ui_messenger = UserInterface()
        ui_messenger.info("Connecting to Cisco Ramon...")

        # Check that GNS3 is running; if false, the method will raise an error and the script
        # will exit.
        # Use subprocess here, so the user running the script, if not root, gets prompted for
        # their password
        cmd = "sudo -S pgrep gns3server"  # Returns the process ID
        retcode = subprocess.call(shlex.split(cmd))
        if retcode == 0:
            ui_messenger.info("GNS3 is running.")
        else:
            raise RuntimeError(
                "GNS3 is not running. " +
                "Please run ./gns3_run.sh to start GNS3 before executing this script.")

        # Initialize default parameter values
        config_file_path = "R1_7206_i1_startup-config.cfg"
        device_ip_address = "192.168.1.10"
        subnet_mask = "255.255.255.0"
        host_ip_address = "192.168.1.100"

        # Get parameter values from the command-line
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-x", "--execute",
            help="Run from the command line using the supplied parameter values. " +
                 "Requires config_file_path, device_ip_address, and subnet_mask.")
        parser.add_argument(
            "--config_file_path",
            help="The location of the configuration file to load into the router.")
        parser.add_argument(
            "--device_ip_address",
            help="The IP address for uploading the configuration file to the router.")
        parser.add_argument(
            "--subnet_mask",
            help="The subnet mask that applies to the host and router. " +
                 "Default is {0}.".format(subnet_mask),
            default=subnet_mask)
        parser.add_argument(
            "--host_ip_address",
            help="The IP address of the host. Default is {0}.".format(host_ip_address),
            default=host_ip_address)
        args = parser.parse_args()

        if args.execute:
            # Replace default values with user-supplied values
            config_file_path = args.config_file_path
            device_ip_address = args.device_ip_address
            subnet_mask = args.subnet_mask if args.subnet_mask else subnet_mask
            host_ip_address = args.host_ip_address if args.host_ip_address else host_ip_address
        else:
            ui_messenger.warning("You are running this application with default test values.")

        # Instantiate the router object here, since __init__ does not have error-handling code
        r7206 = Ramon7206(config_file_path, device_ip_address, subnet_mask, host_ip_address)

        # Check if the lab is loaded and the device is started
        try:
            # In Lab 0, the unconfigured router is connected to the host through console
            # port 5001 TCP.
            with telnetlib.Telnet(host_ip_address, 5001, timeout=15):
                ui_messenger.info("Device reached.")
        except ConnectionRefusedError:
            raise RuntimeError(
                "Unable to reach device. " +
                "Please load Lab 0 in GNS3 and start all devices before executing this script.")

    except RuntimeError:
        # Format the error, report, and exit
        e_type, e_value, e_traceback = sys.exc_info()
        ui_messenger.error("Type {0}: '{1}' in {2} at line {3}.".format(
            e_type.__name__,
            e_value,
            e_traceback.tb_frame.f_code.co_filename,
            e_traceback.tb_lineno))
        ui_messenger.info("Good-bye.")
        exit(1)

    # The Ramon object has its own error-handling code
    r7206.run(ui_messenger)
    ui_messenger.info("Script complete. Have a nice day.")
