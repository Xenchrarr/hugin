# Messenger relay proof of concept

This stack connects a personal Facebook Messenger account to Hugin
through the unmodified `mautrix-meta` bridge. It deliberately keeps the Meta
protocol implementation outside Hugin:

```text
Messenger <-> mautrix-meta <-> private Synapse <-> messenger-relay <-> Message Hub
```

The PoC is text-first. Inbound media is represented by a typed placeholder and
caption; downloading and re-uploading media is intentionally deferred. Matrix
rooms are unencrypted and non-federated, while mautrix-meta still acts as an
endpoint for Messenger's own encrypted conversations.

## Security boundary

- Synapse and Element bind only to `127.0.0.1`.
- Synapse registration must remain disabled after creating the single `hugin`
  account.
- Portal room federation is disabled in mautrix-meta.
- Facebook cookies stay under `/srv/hugin/messenger/mautrix-meta` on the server.
  Never put them in Portainer environment variables, logs, or the Hugin database.
- `MATRIX_ACCESS_TOKEN` is a credential. Store it only in Portainer's protected
  stack environment and do not commit it.
- Relaying a message to Telegram or SMS takes it outside Messenger E2EE.

The images are pinned to `mautrix-meta v26.09`, Synapse `v1.161.0`, and Element
Web `v1.12.26`. Upgrades should be deliberate and tested against a nonessential
account first.

## Deployment model

This guide assumes a fresh installation on the Docker server using Portainer's
Web Editor with a Docker Standalone environment. Run every shell command in
steps 1 and 2 on that server over SSH. Portainer owns the long-running
containers; the shell commands only generate their initial configuration.

The Compose file contains four services:

- `matrix-synapse`, `mautrix-meta`, and `messenger-relay` run continuously.
- `matrix-element` also runs under Portainer. Forwarding does not depend on its
  web UI after setup, but retaining it makes later bridge administration easy.

All durable Matrix and Meta state lives under `/srv/hugin/messenger` on the
server. The relay's cursor and SMS reply context live in the Docker named volume
`messenger_relay_data`. Back up both. The server directory contains signing
keys, bridge tokens, and Meta session credentials; never commit or publish it.

Portainer pulls `xenchrarr/messenger-relay:latest`, because a Web Editor stack
does not have the repository build context. Build and publish the changed Hugin
images before deploying this Compose revision.

## 1. Prepare a clean server directory

If an earlier Portainer attempt created the Matrix services, stop
`messenger-relay`, `matrix-element`, `mautrix-meta`, and `matrix-synapse` before
changing their files. In Portainer's **Volumes** view, remove the old volume
whose name ends in `_messenger_relay_data` only if you want to discard its old
sync cursor and reply context. Check the exact volume name and stack ownership
before deleting it. Skip this paragraph for a genuinely new deployment.

If `/srv/hugin/messenger` exists from an earlier attempt, preserve it as a
backup instead of deleting it:

```bash
sudo mv /srv/hugin/messenger /srv/hugin/messenger.previous
```

Skip that command when the directory does not exist. Then create the fresh
layout and give your server account access:

```bash
sudo mkdir -p /srv/hugin/messenger/synapse
sudo mkdir -p /srv/hugin/messenger/mautrix-meta
sudo chown -R "$(id -u):$(id -g)" /srv/hugin/messenger
```

If `messenger.previous` already exists, choose another backup name before
moving anything.

## 2. Generate and edit configuration on the server

Generate the private Synapse configuration:

```bash
docker run --rm \
  -v /srv/hugin/messenger/synapse:/data \
  -e SYNAPSE_SERVER_NAME=hugin.local \
  -e SYNAPSE_REPORT_STATS=no \
  matrixdotorg/synapse:v1.161.0 generate
```

Generate the initial unmodified mautrix-meta configuration:

```bash
docker run --rm \
  -v /srv/hugin/messenger/mautrix-meta:/data \
  dock.mau.dev/mautrix/meta:v26.09
```

Container-generated files may not initially be editable by your SSH user. If
necessary, grant that user an ACL without changing the containers' ownership:

```bash
sudo setfacl -Rm u:"$(id -u)":rwX /srv/hugin/messenger
sudo setfacl -Rdm u:"$(id -u)":rwX /srv/hugin/messenger
```

Edit `/srv/hugin/messenger/mautrix-meta/config.yaml` and set at least:

```yaml
network:
  thread_backfill:
    batch_count: 0

bridge:
  permissions:
    "*": relay
    "hugin.local": user
    "@hugin:hugin.local": admin
  private_chat_portal_meta: true

database:
  type: sqlite3-fk-wal
  uri: file:/data/mautrix-meta.db?_txlock=immediate

homeserver:
  address: http://matrix-synapse:8008
  domain: hugin.local
  software: standard

appservice:
  address: http://mautrix-meta:29319
  hostname: 0.0.0.0
  port: 29319
  id: facebook
  bot:
    username: facebookbot
    displayname: Facebook Messenger bridge bot
  username_template: facebook_{{.}}

matrix:
  delivery_receipts: false
  federate_rooms: false

backfill:
  enabled: false

encryption:
  allow: false
  default: false
  require: false
```

Leave generated `as_token` and `hs_token` values alone. Run the image once more
to update the config and generate `registration.yaml`:

```bash
docker run --rm \
  -v /srv/hugin/messenger/mautrix-meta:/data \
  dock.mau.dev/mautrix/meta:v26.09
```

The bridge creates `registration.yaml` for its own runtime UID. Grant the
pinned Synapse runtime UID read-only access without making the bridge tokens
world-readable:

```bash
sudo setfacl -m u:991:r /srv/hugin/messenger/mautrix-meta/registration.yaml
```

Add the following to `/srv/hugin/messenger/synapse/homeserver.yaml`:

```yaml
app_service_config_files:
  - /data/facebook-registration.yaml

enable_registration: false
allow_public_rooms_without_auth: false
allow_public_rooms_over_federation: false
federation_domain_whitelist: []
```

If the generated file already contains one of these keys, edit its existing
value instead of adding a duplicate YAML key.

Create `/srv/hugin/messenger/element-config.json` with this content:

```json
{
  "default_server_config": {
    "m.homeserver": {
      "base_url": "http://localhost:8008",
      "server_name": "hugin.local"
    }
  },
  "disable_custom_urls": true,
  "disable_guests": true,
  "disable_3pid_login": true,
  "brand": "Hugin Messenger PoC"
}
```

Before continuing, verify that these files exist on the server:

```text
/srv/hugin/messenger/synapse/homeserver.yaml
/srv/hugin/messenger/synapse/hugin.local.signing.key
/srv/hugin/messenger/mautrix-meta/config.yaml
/srv/hugin/messenger/mautrix-meta/registration.yaml
/srv/hugin/messenger/element-config.json
```

## 3. Deploy the stack in Portainer

From a Hugin repository checkout with registry access, publish every changed
image:

```bash
make build-orchestrator build-orchestrator-frontend build-sms-bot \
  build-telegram-relay build-messenger-relay
make push-orchestrator push-orchestrator-frontend push-sms-bot \
  push-telegram-relay push-messenger-relay
```

Then in Portainer:

1. Open the existing Hugin stack and select **Editor**.
2. Replace its Compose text with the current `docker-compose.yml`.
3. Add `MESSENGER_CONFIG_ROOT=/srv/hugin/messenger` under environment variables.
4. Add `MATRIX_USER_ID=@hugin:hugin.local`.
5. Leave `MATRIX_ACCESS_TOKEN` empty for now.
6. Enable **Re-pull image** and update the stack.

Confirm that `matrix-synapse`, `mautrix-meta`, and `matrix-element` are running.
`messenger-relay` will restart until a valid Matrix token is added; that is
expected during initial setup.

## 4. Create the private Matrix user

Open **Containers -> matrix-synapse -> Console**, connect with `/bin/sh`, and
run:

```bash
register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008
```

Create exactly one local user with localpart `hugin`, choose a strong unique
password, and make it an administrator.

## 5. Open Element and obtain the relay token

Synapse and Element bind only to loopback on the server. From the administrator
computer (your laptop or desktop), you only need an SSH client and a web
browser. Docker, Synapse, Element, and the relay continue to run exclusively on
the server.

Open a terminal on the administrator computer and create an SSH tunnel:

```bash
ssh -N -L 8088:127.0.0.1:8088 -L 8008:127.0.0.1:8008 <user>@<server>
```

Replace `<user>` with the SSH account on the Docker server and `<server>` with
its hostname or IP address. The command intentionally appears to do nothing;
`-N` means it only forwards ports. Keep that terminal open while using Element.

The tunnel maps ports on the administrator computer as follows:

- `http://localhost:8088` -> Element on port `8088` of the server.
- `http://localhost:8008` -> Synapse on port `8008` of the server.

Open `http://localhost:8088` in the administrator computer's browser and sign
in as `hugin`. Element itself is still served by the server. Its browser code
uses the second tunnel to reach Synapse at `http://localhost:8008`.

Click the profile circle, then **All settings -> Help & About**. At the bottom
under **Advanced**, reveal and copy **Access Token**.

In Portainer, edit the Hugin stack environment and set:

```dotenv
MATRIX_ACCESS_TOKEN=<copied token>
```

Update the stack. Do not log out of this Element session: logging out revokes
its token. Closing the browser tab is fine. Confirm that `messenger-relay`
becomes healthy in Portainer. Closing the SSH tunnel only removes browser access
from the administrator computer; it does not stop any server container or
message forwarding.

It is expected that `messenger-relay` starts before the Facebook account is
logged into mautrix-meta. At this point it only watches the private Matrix
homeserver; there are no Messenger portal rooms to relay yet. Backfill is
disabled, so completing the Facebook login later does not intentionally replay
old Messenger history through Hugin.

## 6. Log the account into Messenger

Return to Element, open a direct room with `@facebookbot:hugin.local`, and send:

```text
login facebook
```

Follow the bridge prompt. Cookie login should be done from a private browser
window; close that private window after copying the requested cURL/cookie data.
Enable Facebook 2FA before testing. Meta may still challenge or restrict an
unofficial client session.

After login, wait for portal rooms to appear and confirm that a new incoming
Messenger message appears in its corresponding Matrix room.

On first start, `messenger-relay` records the current Matrix sync token and does
not forward existing room history. Only later events are eligible for routes.

## 7. Configure routes

Migration `029_messenger_relay_poc.sql` creates `messenger-main` as the source
endpoint plus its Message Hub gateway. Outbound Messenger routes use fixed
target endpoints containing a `thread_id`.

For Messenger -> SMS, create a route with source `messenger-main` and an SMS
target. For Messenger -> Telegram, create a target endpoint like:

```json
{
  "key": "telegram-personal",
  "name": "Personal Telegram chat",
  "type": "telegram",
  "capabilities": ["target"],
  "config": {"chat_id": 123456789}
}
```

For Telegram -> Messenger, create a fixed target endpoint after `fb/list` has
revealed the thread ID:

```json
{
  "key": "messenger-family",
  "name": "Messenger family chat",
  "type": "messenger",
  "capabilities": ["target"],
  "config": {"thread_id": "1234567890123456"}
}
```

SMS supports:

- `fb/list`
- `fb/use <number>`
- `fb/send <number> <text>`
- `fb/reply <text>`

## PoC acceptance checks

1. A fresh Messenger DM reaches one SMS target exactly once.
2. A fresh Messenger DM reaches one Telegram target exactly once.
3. `fb/reply` arrives in the correct Messenger conversation.
4. A Telegram route targeting a Messenger thread arrives exactly once.
5. Restart `messenger-relay`; no old timeline messages are replayed.
6. Stop it during a delivery, restart it, and confirm Message Hub idempotency
   prevents duplicate target deliveries.
7. Confirm ordinary Matrix rooms and messages sent by `@hugin` are ignored.

Do not enable automatic media forwarding or broad catch-all routes until these
checks pass.
