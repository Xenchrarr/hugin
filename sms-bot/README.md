# SMS Bot

SMS command bot that listens for incoming messages on a Quectel EC25 USB modem and executes commands via Home Assistant, Simplenote, etc.

## Project Structure

```
main.py                        # Entrypoint
src/
├── sms_handler.py             # AT command modem I/O
├── command_processor.py       # Command routing
├── api/
│   └── homeassistant.py       # Home Assistant HTTP client
├── commands/
│   ├── base_command.py        # Base class for commands
│   ├── get_shoppinglist.py    # Fetch shopping list from Simplenote
│   ├── remind_command.py      # Reminder (stub)
│   └── trigger_automation.py  # Trigger HA automations
├── config/
│   ├── config.py              # Allowed senders, note keys
│   └── logging.py             # Logging setup
├── models/
│   └── sms_message.py         # SmsMessage dataclass
└── services/
    ├── home_assistant_service.py
    └── simple_note_service.py
```

## SMS Commands

| SMS Text | Action |
|---|---|
| `get shoppinglist` | Returns the shopping list from Simplenote |
| `trigger tv: automation.watch_tv` | Triggers a Home Assistant automation |
| `remind: 3pm Take out trash` | Parses time and echoes confirmation (stub) |

## Prerequisites

- Docker & Docker Compose
- A Quectel EC25 USB modem with a SIM card inserted
- Home Assistant instance with a long-lived access token
- Simplenote account

## Host Setup (x64)

### 1. Find the EC25 USB device

Plug in the EC25 and confirm it is detected:

```bash
lsusb | grep -i 2c7c
# Expected: ID 2c7c:0125 Quectel Wireless Solutions Co., Ltd. EC25 LTE modem
```

The EC25 exposes four serial ports (`ttyUSB0`–`ttyUSB3`). Interface `03` is the AT command port.

### 2. Identify the AT port

Check which `/dev/ttyUSBx` ports were assigned:

```bash
dmesg | grep tty | tail -20
```

Test the AT port (typically `ttyUSB3`):

```bash
screen /dev/ttyUSB3 115200
```

Type `AT` and press Enter — you should see `OK`. Exit with `Ctrl-A` then `K`.

### 3. Use the stable by-id symlink

udev automatically creates a stable, persistent symlink for the AT port — no custom rule needed:

```bash
ls /dev/serial/by-id/ | grep Quectel
# usb-Quectel_EC25-EUX_0123456789ABCDEF-if03-port0
```

This symlink is what the `docker-compose.yml` device mapping uses.

### 4. Add your user to the dialout group

```bash
sudo usermod -aG dialout $USER
```

Log out and back in for the group change to take effect.

## Configuration

Copy the example env file and fill in your values:

```bash
cp stack.env.example stack.env
```

| Variable | Description |
|---|---|
| `HA_TOKEN` | Home Assistant long-lived access token |
| `HA_URL` | Home Assistant URL (e.g. `http://192.168.2.106:8126`) |
| `SIMPLENOTE_EMAIL` | Simplenote account email |
| `SIMPLENOTE_PASSWORD` | Simplenote account password |

Allowed sender phone numbers are configured in `src/config/config.py`.

## Running

Build and start:

```bash
make build
make run
```

View logs:

```bash
make logs
```

Stop:

```bash
make stop
```

### Push to Docker Hub

```bash
make auth
make push
```

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
