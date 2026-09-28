# Reticulum Relay

`reticulum-relay` makes the Hugin host a Reticulum transport node, an LXMF
propagation node, a NomadNet page server, and a bidirectional Message Hub
connector.

Hugin renders `/data/rns/config` from `RETICULUM_*` environment variables on
every start. Runtime state remains in the `reticulum_data` Docker volume:

- `/data/identity` — the stable identity used by LXMF, propagation and pages
- `/data/lxmf` — propagation messages, peers, tickets and ratchets
- `/data/state` — recent contacts, SMS reply contexts and delivery receipts

The RNode defaults use coding rate `5` (LoRa 4/5). Reticulum requires an
explicit coding rate from `5` through `8`; set `RETICULUM_RNODE_CODING_RATE`
if the radio uses a different value.

The NomadNet Micron pages are built from `reticulum_relay/pages` into the
container at `/app/pages`, so the site content is versioned and deployed by
Hugin instead of drifting in the runtime volume. Set `RETICULUM_PAGES_PATH`
only when deliberately using another page directory.

The service publishes three destination hashes derived from the same identity.
They are returned by `GET /health`: `delivery_hash`, `propagation_hash` and
`site_hash`.

## Server migration

Do not delete the current server configuration first. The old process and the
container cannot both own `/dev/ttyACM0` or TCP port 4242.

1. Back up the existing Reticulum application directories, commonly
   `~/.reticulum`, `~/.lxmd` and `~/.nomadnetwork`.
2. If an existing LXMF identity must be retained, copy its identity file to
   `/data/identity` in the `reticulum_data` volume before first startup. An RNS
   interface config by itself does not contain an LXMF identity.
3. Stop, but do not yet remove, host `rnsd`, `lxmd` and `nomadnet` services.
   Set `RETICULUM_RNODE_GID` to the numeric host `dialout` GID reported by
   `getent group dialout` (Fedora commonly uses `18`; Debian commonly uses
   `20`). On SELinux hosts, enable `container_use_devices` if policy blocks the
   mapped serial device.
4. Deploy Hugin and check `docker compose ps reticulum-relay`, its logs, and
   `docker compose exec reticulum-relay curl -fsS localhost:8082/health`.
5. Verify the RNode interface, TCP listener, all three hashes, a NomadNet page
   request, and one LXMF delivery in each direction.
6. Disable the old host services only after those checks. Keep the backup until
   the new node has run successfully through a restart.

If there is no identity to preserve, let the container create one on first
start and back up the `reticulum_data` volume immediately afterward.

## Message routing

Migration `030_reticulum_relay.sql` creates the `reticulum-main` source endpoint
and gateway. Add target endpoints in Message Routes with a 32-character LXMF
delivery destination hash and choose `direct`, `opportunistic`, or `propagated`.

Propagated outbound delivery requires `RETICULUM_OUTBOUND_PROPAGATION_NODE`.
Hosting a propagation node does not automatically make that same destination a
usable outbound propagation hop for the local LXMF client.

Text and titles are supported initially. Arbitrary LXMF fields and attachments
are deliberately not bridged to other transports yet.
