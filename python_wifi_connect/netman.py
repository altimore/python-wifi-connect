# Start a local hotspot using NetworkManager.

# You must use https://developer.gnome.org/NetworkManager/1.2/spec.html
# to see the DBUS API that the python-NetworkManager module is communicating
# over (the module documentation is scant).

import os
import socket
import time
import uuid

import NetworkManager
from dbus.mainloop.glib import DBusGMainLoop
from loguru import logger

logger.add("netman.log", retention="15 days")


HOTSPOT_CONNECTION_NAME = "hotspot"
GENERIC_CONNECTION_NAME = "python-wifi-connect"


def have_active_internet_connection(host="8.8.8.8", port=53, timeout=2)->bool:
    """
    Returns True if we are connected to the internet, False otherwise.
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as e:
        # logger.debug(f"Exception: {e}")
        return False


def delete_all_wifi_connections():
    """Remove ALL wifi connections - to start clean or before running the hotspot."""
    # Get all known connections
    connections = NetworkManager.Settings.ListConnections()

    # Delete the '802-11-wireless' connections
    for connection in connections:
        if connection.GetSettings()["connection"]["type"] == "802-11-wireless":
            logger.debug(
                "Deleting connection " + connection.GetSettings()["connection"]["id"]
            )
            connection.Delete()
    time.sleep(2)


def stop_hotspot():
    """Stop and delete the hotspot.
    Returns True for success or False (for hotspot not found or error)."""
    return stop_connection(HOTSPOT_CONNECTION_NAME)


def stop_connection(conn_name=GENERIC_CONNECTION_NAME) -> bool:
    """Generic connection stopper / deleter."""
    # Find the hotspot connection
    try:
        connections = NetworkManager.Settings.ListConnections()
        connections = dict(
            [(x.GetSettings()["connection"]["id"], x) for x in connections]
        )
        conn = connections[conn_name]
        conn.Delete()
    except Exception as e:
        # logger.debug(f'stop_hotspot error {e}')
        return False
    time.sleep(2)
    return True


def get_list_of_access_points(hidden_placeholder: bool = True)->[]:
    """Return a list of available SSIDs and their security type, or [] for none available or error."""
    # bit flags we use when decoding what we get back from NetMan for each AP
    NM_SECURITY_NONE = 0x0
    NM_SECURITY_WEP = 0x1
    NM_SECURITY_WPA = 0x2
    NM_SECURITY_WPA2 = 0x4
    NM_SECURITY_ENTERPRISE = 0x8

    ssids = []  # list we return

    for dev in NetworkManager.NetworkManager.GetDevices():
        if dev.DeviceType != NetworkManager.NM_DEVICE_TYPE_WIFI:
            continue
        for ap in dev.GetAccessPoints():

            # Get Flags, WpaFlags and RsnFlags, all are bit OR'd combinations
            # of the NM_802_11_AP_SEC_* bit flags.
            # https://developer.gnome.org/NetworkManager/1.2/nm-dbus-types.html#NM80211ApSecurityFlags

            security = NM_SECURITY_NONE

            # Based on a subset of the flag settings we can determine which
            # type of security this AP uses.
            # We can also determine what input we need from the user to connect to
            # any given AP (required for our dynamic UI form).
            if (
                ap.Flags & NetworkManager.NM_802_11_AP_FLAGS_PRIVACY
                and ap.WpaFlags == NetworkManager.NM_802_11_AP_SEC_NONE
                and ap.RsnFlags == NetworkManager.NM_802_11_AP_SEC_NONE
            ):
                security = NM_SECURITY_WEP

            if ap.WpaFlags != NetworkManager.NM_802_11_AP_SEC_NONE:
                security = NM_SECURITY_WPA

            if ap.RsnFlags != NetworkManager.NM_802_11_AP_SEC_NONE:
                security = NM_SECURITY_WPA2

            if (
                ap.WpaFlags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_802_1X
                or ap.RsnFlags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_802_1X
            ):
                security = NM_SECURITY_ENTERPRISE

            # logger.debug(f'{ap.Ssid:15} Flags=0x{ap.Flags:X} WpaFlags=0x{ap.WpaFlags:X} RsnFlags=0x{ap.RsnFlags:X}')

            # Decode our flag into a display string
            security_str = ""
            if security == NM_SECURITY_NONE:
                security_str = "NONE"

            if security & NM_SECURITY_WEP:
                security_str = "WEP"

            if security & NM_SECURITY_WPA:
                security_str = "WPA"

            if security & NM_SECURITY_WPA2:
                security_str = "WPA2"

            if security & NM_SECURITY_ENTERPRISE:
                security_str = "ENTERPRISE"

            entry = {"ssid": ap.Ssid, "security": security_str}

            # Don't add duplicates to the list, issue #8
            if ssids.__contains__(entry):
                continue

            # Don't add other PFC's to the list!
            if ap.Ssid.startswith("PFC_EDU-"):
                continue

            ssids.append(entry)

    if hidden_placeholder:
        ssids.append({"ssid": "Enter a hidden WiFi name", "security": "HIDDEN"})

    logger.debug(f"Available SSIDs: {ssids}")
    return ssids


def get_hotspot_SSID()->str:
    """Get hotspot SSID name."""
    return "PFC_EDU-" + os.getenv("RESIN_DEVICE_NAME_AT_INIT", "aged-cheese")


def start_hotspot()->bool:
    """Start a local hotspot on the wifi interface.
    Returns True for success, False for error."""
    return connect_to_AP(CONN_TYPE_HOTSPOT, HOTSPOT_CONNECTION_NAME, get_hotspot_SSID())


# ------------------------------------------------------------------------------
# Supported connection types for the function below.
CONN_TYPE_HOTSPOT = "hotspot"
CONN_TYPE_SEC_NONE = "NONE"  # MIT
CONN_TYPE_SEC_PASSWORD = "PASSWORD"  # WPA, WPA2 and WEP
CONN_TYPE_SEC_ENTERPRISE = "ENTERPRISE"  # MIT SECURE


def connect_to_AP(
    conn_type=None,
    conn_name=GENERIC_CONNECTION_NAME,
    ssid=None,
    username=None,
    password=None,
) -> bool:
    """Generic connect to the user selected AP function.
    Returns True for success, or False."""
    # logger.debug(f"connect_to_AP conn_type={conn_type} conn_name={conn_name} ssid={ssid} username={username} password={password}")

    if conn_type is None or ssid is None:
        logger.debug(f"connect_to_AP() Error: Missing args conn_type or ssid")
        return False

    try:
        # This is the hotspot that we turn on, on the RPI so we can show our
        # captured portal to let the user select an AP and provide credentials.
        hotspot_dict = {
            "802-11-wireless": {"band": "bg", "mode": "ap", "ssid": ssid},
            "connection": {
                "autoconnect": False,
                "id": conn_name,
                "interface-name": "wlan0",
                "type": "802-11-wireless",
                "uuid": str(uuid.uuid4()),
            },
            "ipv4": {
                "address-data": [{"address": "192.168.42.1", "prefix": 24}],
                "addresses": [["192.168.42.1", 24, "0.0.0.0"]],
                "method": "manual",
            },
            "ipv6": {"method": "auto"},
        }

        # debugrob: is this realy a generic ENTERPRISE config, need another?
        # debugrob: how do we handle connecting to a captured portal?

        # This is what we use for "MIT SECURE" network.
        enterprise_dict = {
            "802-11-wireless": {
                "mode": "infrastructure",
                "security": "802-11-wireless-security",
                "ssid": ssid,
            },
            "802-11-wireless-security": {"auth-alg": "open", "key-mgmt": "wpa-eap"},
            "802-1x": {
                "eap": ["peap"],
                "identity": username,
                "password": password,
                "phase2-auth": "mschapv2",
            },
            "connection": {
                "id": conn_name,
                "type": "802-11-wireless",
                "uuid": str(uuid.uuid4()),
            },
            "ipv4": {"method": "auto"},
            "ipv6": {"method": "auto"},
        }

        # No auth, 'open' connection.
        none_dict = {
            "802-11-wireless": {"mode": "infrastructure", "ssid": ssid},
            "connection": {
                "id": conn_name,
                "type": "802-11-wireless",
                "uuid": str(uuid.uuid4()),
            },
            "ipv4": {"method": "auto"},
            "ipv6": {"method": "auto"},
        }

        # Hidden, WEP, WPA, WPA2, password required.
        passwd_dict = {
            "802-11-wireless": {
                "mode": "infrastructure",
                "security": "802-11-wireless-security",
                "ssid": ssid,
            },
            "802-11-wireless-security": {"key-mgmt": "wpa-psk", "psk": password},
            "connection": {
                "id": conn_name,
                "type": "802-11-wireless",
                "uuid": str(uuid.uuid4()),
            },
            "ipv4": {"method": "auto"},
            "ipv6": {"method": "auto"},
        }

        conn_dict = None
        conn_str = ""
        if conn_type == CONN_TYPE_HOTSPOT:
            conn_dict = hotspot_dict
            conn_str = "HOTSPOT"

        if conn_type == CONN_TYPE_SEC_NONE:
            conn_dict = none_dict
            conn_str = "OPEN"

        if conn_type == CONN_TYPE_SEC_PASSWORD:
            conn_dict = passwd_dict
            conn_str = "WEP/WPA/WPA2"

        if conn_type == CONN_TYPE_SEC_ENTERPRISE:
            conn_dict = enterprise_dict
            conn_str = "ENTERPRISE"

        if conn_dict is None:
            logger.debug(f'connect_to_AP() Error: Invalid conn_type="{conn_type}"')
            return False

        # logger.debug(f"new connection {conn_dict} type={conn_str}")

        NetworkManager.Settings.AddConnection(conn_dict)
        logger.debug(f"Added connection {conn_name} of type {conn_str}")

        # Now find this connection and its device
        connections = NetworkManager.Settings.ListConnections()
        connections = dict(
            [(x.GetSettings()["connection"]["id"], x) for x in connections]
        )
        conn = connections[conn_name]

        # Find a suitable device
        ctype = conn.GetSettings()["connection"]["type"]
        dtype = {"802-11-wireless": NetworkManager.NM_DEVICE_TYPE_WIFI}.get(
            ctype, ctype
        )
        devices = NetworkManager.NetworkManager.GetDevices()

        for dev in devices:
            if dev.DeviceType == dtype:
                break
        else:
            logger.debug(
                f"connect_to_AP() Error: No suitable and available {ctype} device found."
            )
            return False

        # And connect
        NetworkManager.NetworkManager.ActivateConnection(conn, dev, "/")
        logger.debug(f"Activated connection={conn_name}.")

        # Wait for ADDRCONF(NETDEV_CHANGE): wlan0: link becomes ready
        logger.debug(f"Waiting for connection to become active...")
        loop_count = 0
        while dev.State != NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            # logger.debug(f'dev.State={dev.State}')
            time.sleep(1)
            loop_count += 1
            if loop_count > 30:  # only wait 30 seconds max
                break

        if dev.State == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            logger.debug(f"Connection {conn_name} is live.")
            return True

    except Exception as e:
        logger.debug(f"Connection error {e}")

    logger.debug(f"Connection {conn_name} failed.")
    return False


def get_active_access_point()->NetworkManager.AccessPoint:
    """Return the active access point object from NetworkManager DBUS interface"""
    # TODO: get rid of this trick the other code doesn't need it.
    DBusGMainLoop(set_as_default=True)

    devices = [
        device
        for device in NetworkManager.NetworkManager.GetAllDevices()
        if isinstance(device, NetworkManager.Wireless)
    ]
    logger.debug(f"All devices : {devices}")
    # if len(device) == 1:
    # get the first wifi device
    selected_device = devices[0]
    active_access_point = selected_device.ActiveAccessPoint
    if active_access_point:
        logger.debug(f" * Active access point : {active_access_point.Ssid}")
    else:
        logger.debug(f" * No active access point")
    return active_access_point


if __name__ == "__main__":
    print(get_active_access_point())
