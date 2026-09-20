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

The sender's registered phone number is the authentication factor; no PIN is
required. Commands are case-insensitive. Compound commands accept slash form
(`list/show`) or, where unambiguous, dumb-phone-friendly spaces (`list show`).
Send `help` for the on-phone list or `help <command>` for one command.

Long replies fit in one GSM-7 SMS when their characters permit it. Reply `more` (or `next`) for
the next page and `back` (or `prev`/`previous`) for the previous page. `again`
(or `repeat`) runs the last command again, while `cancel` clears the current
session state.

### Quick menu and shortcuts

| SMS text | Aliases | Action |
|---|---|---|
| `menu` | `m` | Show the compact dumb-phone menu |
| `1` | | Run `today` |
| `2` | | Run `list show` |
| `3` | | Run `status` |
| `4` | | Run `inbox` |
| `5` | | Run `ideas show` |
| `6` | | Run `help` |
| `help [command]` | `?` | List commands or show detailed help for one command |

The digit mappings can be replaced or extended with `sms_shortcuts` in the
user configuration.

### Day, weather, energy, and messages

| SMS text | Aliases | Action |
|---|---|---|
| `today` | `day` | Show today's calendar, reminders, weather, and solar summary |
| `agenda [days]` | `cal` | Show upcoming calendar events; defaults to 7 days and accepts 1-31 |
| `weather` | `weather/text` | Show today's forecast as text |
| `weather/image` | `weather/img` | Send today's forecast as an MMS image |
| `chart` | `solar`, `chart/today` | Show today's Growatt and EcoFlow solar production |
| `chartdays [days]` | | Show daily energy production; defaults to 7 days, maximum 30 |
| `data` | `inverter` | Show current inverter power and today's total energy |
| `news [count]` | `headlines` | Show RSS headlines; defaults to 3, maximum 10 |
| `bus <destination>` | `transit` | Get a compact result from the configured transit webhook |
| `inbox` | `messages` | Summarize messages stored while SMS delivery was unavailable |
| `inbox sources` | | List the waiting-message sources |
| `inbox telegram [group]` | `inbox tg [group]` | Retrieve up to five waiting Telegram messages, optionally from one group |
| `inbox reminders` | `inbox rem` | Retrieve waiting reminder messages |
| `inbox system` | | Retrieve waiting system messages |
| `inbox next` | | Retrieve the next batch of waiting messages |

Inbox commands read held Message Hub deliveries. Retrieved entries are
acknowledged only after the SMS response is accepted, so a failed response can
be retried.

Text and image command responses are stored in Message Hub before modem
delivery. Camera and weather images therefore remain queued during an SMS
gateway outage instead of rerunning the command or being discarded.

Physical sends require a stable Message Hub delivery token. sms-hub records
the token in `/data/sms-delivery-ledger.sqlite3`; replaying an accepted token
returns the cached result without touching the modem. An interrupted send is
reported as uncertain and requires the explicit **Retry anyway** action in
Message Hub, because it may already have reached the carrier.

### Shopping, ideas, and printing

| SMS text | Aliases | Action |
|---|---|---|
| `list show` | `list/show`, `get shoppinglist` | Show the Simplenote shopping list |
| `list add <item>` | `list/add` | Add an item to the shopping list |
| `list rm <item>` | `list/rm` | Remove an item from the shopping list |
| `list print` | `list/print`, `print/list` | Print the shopping list on the thermal printer |
| `ideas show` | `ideas/show`, `ideas/list` | Show the ideas note |
| `ideas add <idea>` | `ideas/add`, `idea/add`, `note` | Add text to the ideas note |
| `print today` | | Print today's compact summary |
| `print weather` | | Print the weather summary |
| `print list` | | Print the shopping list |
| `print note <text>` | | Print arbitrary text |

### Reminders, briefings, and safety

| SMS text | Aliases | Action |
|---|---|---|
| `rem in <duration> <message>` | `rem/in`, `remind`, `timer` | Set a reminder, for example `rem in 45m check oven` |
| `t <minutes> <message>` | | Fast timer, for example `t 20 pasta` |
| `rem list [status]` | `rem/list`, `reminders` | List reminders; the default status is `active` |
| `rem snooze <id> [duration]` | `rem/snooze`, `snooze`, `s` | Snooze a reminder; duration defaults to 10 minutes |
| `rem dismiss <id>` | `rem/dismiss`, `dismiss`, `d`, `done` | Dismiss a reminder |
| `brief <HHMM>` | | Schedule a daily compact briefing, for example `brief 0730` |
| `brief off` | | Disable the daily briefing |
| `quiet <HHMM> <HHMM>` | | Set quiet hours for proactive SMS, for example `quiet 2200 0700` |
| `quiet off` | | Disable quiet hours |
| `checkin <minutes>` | `check` | Start a safety deadline; maximum 1440 minutes |
| `ok` | `safe` | Confirm safety and close the active check-in |

Add `repeat=<rule>` (or `recurrence=<rule>`) to a reminder for recurrence. The
orchestrator accepts rules such as `daily`, `weekly:MON`, and `interval:30m`.

### Home, camera, and jobs

| SMS text | Aliases | Action |
|---|---|---|
| `status` | `home/status` | Show compact Home Assistant and service status |
| `scene list` | | List configured scene names |
| `scene <name> [argument]` | `mode` | Run a configured Home Assistant scene or automation |
| `<scene-name> [argument]` | | Run a configured scene directly, for example `bed` or `heat 60` |
| `home dev <entity_id>` | `home/dev`, `trigger tv` | Trigger an automation or turn on another Home Assistant entity |
| `cam` | `camera` | Send the latest camera snapshot by MMS |
| `run list` | `job list` | List allowlisted orchestrator jobs |
| `run <name>` | `job` | Run an allowlisted orchestrator job |

### Telegram bridge

| SMS text | Aliases | Action |
|---|---|---|
| `tg list` | `tg/list`, `tg/convos` | List recent Telegram conversations and their numbers |
| `tg use <num\|chat_id>` | `tg/use`, `tg/target` | Select the conversation used by replies and unaddressed MMS photos |
| `tg send <num\|chat_id> <message>` | `tg/send` | Send a message to a specific conversation |
| `tg reply <message>` | `tg/reply`, `tg/r`, `r`, `reply` | Reply to the selected or most recently active conversation |

To relay a photo, select a target with `tg use <num>`, then send a JPEG, PNG,
or GIF to the SIM by MMS. The MMS text becomes its Telegram caption. Start the
caption with `tg/send <num>`, `tg/use <num>`, or `tg/target <num>` to override
the selected target for that photo. A caption beginning with `r`, `reply`,
`tg/r`, or `tg/reply` is treated as a reply caption.

### Message routes

| SMS text | Aliases | Action |
|---|---|---|
| `relay` | `relay/list`, `relay/ls` | List routes, route state, and targets |
| `relay on [route]` | `relay/start`, `relay/enable` | Enable a route; omit the name when only one SMS route exists |
| `relay off [route]` | `relay/stop`, `relay/disable` | Disable a route; omit the name when only one SMS route exists |
| `relay preset on` | `relay/preset/on` | Enable all preset relay rules |
| `relay preset off` | `relay/preset/off` | Disable all preset relay rules |

### AI

| SMS text | Aliases | Action |
|---|---|---|
| `ai <message>` | `chat` | Chat with the configured AI assistant; it can also select a registered command |

If AI is configured, an unrecognized message is also offered to the assistant
as a natural-language fallback. Close command typos may be corrected or return
a short list of possible matches.

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

Allowed sender phone numbers are registered as SMS channel identifiers on the
corresponding orchestrator users. Command permissions can also be restricted
per user; administrators receive every command.

### Per-user dumb-phone configuration

The orchestrator user's `config` JSON controls optional integrations. All keys
are optional:

```json
{
  "weather_location_id": "1-72837",
  "sms_shortcuts": {"7": "scene bed", "8": "cam"},
  "status_entities": {
    "Front": "binary_sensor.front_door",
    "Temp": "sensor.living_room_temperature"
  },
  "sms_scenes": {
    "bed": "automation.bedtime",
    "away": "scene.away",
    "heat": {
      "entity_id": "automation.heat_boost",
      "argument_variable": "duration"
    }
  },
  "sms_jobs": {"backup": 12, "update": 18},
  "news_feed_url": "https://example.com/feed.xml",
  "transit_url": "https://example.internal/transit",
  "checkin_alert_phone": "+47xxxxxxxx",
  "missed_call_command": "scene home"
}
```

`transit_url` receives `destination` and `user_id` query parameters and may
return plain text or JSON containing a `text` field. A configured missed-call
command is run once per incoming call and the modem hangs up immediately.

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
