# python-wifi-connect
An application that displays a wifi configuration UI for embedded Linux devices.

Inspired by the [wifi-connect](https://github.com/balena-io/wifi-connect) project written by [balena.io](https://www.balena.io/).

# Install and Run

Please read the [INSTALL.md](INSTALL.md) then the [RUN.md](RUN.md) files.


# How it works
![How it works](./docs/images/how-it-works.png?raw=true)

WiFi Connect interacts with NetworkManager, which should be the active network manager on the device's host OS.

### 1. Advertise: Device Creates Access Point

WiFi Connect detects available WiFi networks and opens an access point with a captive portal. Connecting to this access point with a mobile phone or laptop allows new WiFi credentials to be configured.

### 2. Connect: User Connects Phone to Device Access Point

Connect to the opened access point on the device from your mobile phone or laptop. The access point SSID is, by default, `PFC_EDU-<name>` where "name" is something random like "shy-lake" or "green-frog".

### 3. Portal: Phone Shows Captive Portal to User

After connecting to the access point from a mobile phone, it will detect the captive portal and open its web page. Opening any web page will redirect to the captive portal as well.

### 4. Credentials: User Enters Local WiFi Network Credentials on Phone

The captive portal provides the option to select a WiFi SSID from a list with detected WiFi networks and enter a passphrase for the desired network.

### 5. Connected!: Device Connects to Local WiFi Network

When the network credentials have been entered, WiFi Connect will disable the access point and try to connect to the network. If the connection fails, it will enable the access point for another attempt. If it succeeds, the configuration will be saved by NetworkManager.

# Details
* [Video demo of the application.](https://www.youtube.com/watch?v=TN7jXMmKV50)
* [These are the geeky development details and background on this application.](docs/details.md)

# About this fork
I wanted to use the netman.py from the original project as a library, so i added poetry and renamed the src folder by python_wifi_connect to use as a package name.

## commands
To install poetry : `curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -`

To use poetry to install an venv : `poetry install`

To use poetry to generate a wheel in the dist subfolder : `poetry build`

To install as a package in another project : `poetry add [yourpath]/dist/python_wifi_connect-[versionhere]-py3-none-any.whl`

## Usage as a library
Once installed in another project you can do the following :
```
from python_wifi_connect import netman
from loguru import logger

# Override the logger settings for your app.
logger.add("connect_wifi.log", retention="15 days")

# sometime we need to init DBus
DBusGMainLoop(set_as_default=True)

# call the functions from the library
access_points = netman.get_list_of_access_points(hidden_placeholder=False)

print(access_points)
...
```

### Function added from the original library

```
def get_active_access_point()->NetworkManager.AccessPoint:
    """Return the active access point object from NetworkManager DBUS interface"""
```
