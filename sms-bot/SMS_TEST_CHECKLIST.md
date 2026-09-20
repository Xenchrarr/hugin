# SMS Feature Test Checklist

Send each line as a separate SMS from a phone number registered on the user's
SMS channel. No PIN is needed.

Before starting, replace these placeholders:

- `<DESTINATION>`: a destination understood by the configured transit webhook
- `<ENTITY>`: a harmless Home Assistant entity to turn on or trigger
- `<SCENE>`: a safe name returned by `scene list`
- `<SCENE_ARG>`: an argument for a configured scene that accepts one
- `<JOB>`: a safe name returned by `run list`
- `<TG>`: a conversation number returned by `tg list`
- `<TG_GROUP>`: a Telegram source name returned by `inbox sources`
- `<RULE>`: a relay rule number or name returned by `relay list`
- `<ID>`: the reminder ID returned by the preceding reminder command

Commands marked **side effect** send something, operate a device, change a
setting, or create stored data. Record existing brief, quiet-hour, and relay
settings before changing them if they need to be restored afterward.

## 1. Access, menu, shortcuts, and parsing

- [ ] `menu` — compact dumb-phone menu
- [ ] `help` — command list; it should normally produce multiple pages
- [ ] `more` — next page
- [ ] `back` — previous page
- [ ] `next` — next page, as an alias for `more`
- [ ] `prev` — previous page, as an alias for `back`
- [ ] `cancel` — clear paging/session state
- [ ] `more` — should now say there is nothing to page through
- [ ] `weather`
- [ ] `again` — repeat the preceding `weather` command
- [ ] `weathe` — typo correction should run `weather`
- [ ] `list/show` — verify slash-form commands
- [ ] `list show` — verify space-form commands
- [ ] `1` — `today`
- [ ] `2` — `list show`
- [ ] `3` — `status`
- [ ] `4` — `inbox`
- [ ] `5` — `ideas show`
- [ ] `6` — `help`
- [ ] `help rem` — namespace-specific help

Optional authentication check: send `help` from an unregistered phone. It
should receive `Unknown user. Contact admin.` and must not run a command.

## 2. Daily information and media

- [ ] `today`
- [ ] `agenda 1`
- [ ] `agenda 7`
- [ ] `weather`
- [ ] `weather/image` — expect a weather image by MMS
- [ ] `chart`
- [ ] `chartdays 7`
- [ ] `data`
- [ ] `news 3`
- [ ] `bus <DESTINATION>`
- [ ] `status`
- [ ] `cam` — expect the latest camera snapshot by MMS

## 3. Shopping, ideas, and printer

- [ ] `list show`
- [ ] `list add SMS TEST ITEM` — **side effect:** adds an item
- [ ] `list show` — confirm `SMS TEST ITEM` is present
- [ ] `list rm SMS TEST ITEM` — cleanup and test removal
- [ ] `ideas show`
- [ ] `ideas add SMS TEST IDEA` — **side effect:** adds persistent note text
- [ ] `ideas show` — confirm `SMS TEST IDEA` is present
- [ ] `list print` — **side effect:** prints the shopping list
- [ ] `print today` — **side effect:** prints the daily summary
- [ ] `print weather` — **side effect:** prints the weather image
- [ ] `print list` — **side effect:** prints the shopping list through the
  general print command
- [ ] `print note SMS printer test` — **side effect:** prints arbitrary text

There is currently no SMS command for removing an ideas-note entry, so remove
`SMS TEST IDEA` in Simplenote afterward if desired.

## 4. Reminders

- [ ] `t 1 fast timer test` — **side effect:** creates a one-minute reminder
- [ ] Wait for the timer SMS
- [ ] `rem in 10m snooze test` — note the returned ID as `<ID>`
- [ ] `rem list`
- [ ] `rem snooze <ID> 1m` — **side effect:** moves the reminder by one minute
- [ ] Wait for the snoozed reminder SMS
- [ ] `rem in 10m dismiss test` — note the new returned ID as `<ID>`
- [ ] `rem dismiss <ID>` — dismiss and clean up that reminder
- [ ] `rem in 1d recurring test repeat=daily` — note its returned ID
- [ ] `rem list`
- [ ] `rem dismiss <ID>` — clean up the recurring test reminder

## 5. Briefings, quiet hours, and safety check-in

- [ ] `brief 0730` — **side effect:** schedule the daily briefing
- [ ] `brief off` — disable the test briefing
- [ ] `quiet 2200 0700` — **side effect:** set proactive-message quiet hours
- [ ] `quiet off` — disable the test quiet hours
- [ ] `checkin 5` — **side effect:** start a five-minute safety deadline
- [ ] `ok` — acknowledge it immediately so no alert is sent

If briefings or quiet hours were already in use, restore their previous values
instead of leaving them off.

## 6. Home Assistant and orchestrator jobs

- [ ] `scene list`
- [ ] `scene <SCENE>` — **side effect:** run a safe configured scene
- [ ] `<SCENE>` — run the same scene using its direct shortcut
- [ ] `scene <SCENE> <SCENE_ARG>` — **side effect:** test a scene configured
  with `argument_variable`; skip if none accepts an argument
- [ ] `home dev <ENTITY>` — **side effect:** trigger or turn on the entity
- [ ] `run list`
- [ ] `run <JOB>` — **side effect:** start the selected allowlisted job

## 7. Stored-message inbox

- [ ] `inbox` — summary; an empty inbox is a valid result
- [ ] `inbox sources`
- [ ] `inbox telegram` — retrieves and acknowledges up to five messages
- [ ] `inbox telegram <TG_GROUP>` — filter by Telegram source
- [ ] `inbox reminders`
- [ ] `inbox system`
- [ ] `inbox next`

Retrieval tests are meaningful only when matching messages have first been
stored during an SMS outage. Retrieved messages are acknowledged after their
SMS response is sent successfully.

## 8. Telegram bridge and inbound MMS

- [ ] `tg list` — note a safe conversation number as `<TG>`
- [ ] `tg use <TG>` — select the sticky target
- [ ] `tg reply SMS reply test` — **side effect:** message the selected conversation
- [ ] `r SMS short-alias test` — **side effect:** test the compact reply alias
- [ ] `tg send <TG> SMS direct-send test` — **side effect:** address it directly
- [ ] Send a JPEG, PNG, or GIF by MMS with caption `SMS photo relay test` — it
  should reach the selected conversation
- [ ] Send another image with caption `tg/send <TG> explicit photo test` — it
  should reach the explicitly addressed conversation

## 9. Telegram relay rules

- [ ] `relay list` — record the initial states and choose `<RULE>`
- [ ] If `<RULE>` is on: `relay stop <RULE>`, then `relay start <RULE>`
- [ ] If `<RULE>` is off: `relay start <RULE>`, then `relay stop <RULE>`
- [ ] `relay preset off` — **side effect:** disable every preset rule
- [ ] `relay preset on` — **side effect:** enable every preset rule
- [ ] `relay list` — verify the intended final state

The preset test deliberately changes all preset rules. Skip it if their
individual enabled states must be preserved.

## 10. AI

- [ ] `ai Reply with exactly: SMS AI OK`
- [ ] `chat Reply with exactly: SMS CHAT OK` — alias test
- [ ] `What is on my shopping list?` — test natural-language fallback when AI
  is configured; it should answer or select a registered command

## 11. Missed-call action

This is not an SMS command, but it completes the phone feature test:

- [ ] Set `missed_call_command` to a safe command such as `status`
- [ ] Call the modem number from the registered phone
- [ ] Confirm the modem hangs up and runs the configured command once

## Expected configuration-dependent failures

A clear configuration message is a successful routing test when an optional
integration has not been configured. Examples include missing weather,
transit, news, printer, camera, AI, check-in alert phone, scene, or job setup.
Non-admin users also need each command's canonical path in `allowed_commands`.
