# Hugin calls

## Validation slice

The first implementation is deliberately small:

- An authenticated **Call me** button on the dashboard.
- The destination is always the logged-in user's registered E.164 phone number.
- `sms-hub` places a ring-only call through the Quectel modem for at most 20 seconds.
- The modem hangs up immediately when the call is answered and always hangs up at the timeout.
- Only one outgoing call can run at a time.

This slice validates the SIM, modem firmware, carrier voice support, and end-to-end Hugin routing before calls become part of scheduled automation.

## Validation result

Live testing on 2026-09-23 confirmed that a GUI-triggered call reaches the
registered phone. The first attempt ended before the phone rang and temporarily
left modem readiness unhealthy; the second attempt rang successfully. The
carrier voice path is therefore available. Those findings drove the call-state,
diagnostic, retry, and post-call registration handling described below.

The validated behavior is:

1. Reaches the registered phone with the expected caller ID.
2. Reports ringing or answered correctly.
3. Hangs up reliably.
4. Does not leave the modem unable to send or receive SMS afterward.

## Implemented alarm system

### Call transport

The modem call implementation now lives in `sms-bot/src/call_handler.py`, separate from SMS handling. It reports dialing, ringing, answered, busy, rejected, timeout, cancellation, and uncertain transport outcomes; captures radio diagnostics; waits for voice registration after hangup; serializes calls; and supports idempotent attempt tokens.

### Wake-up alarms

Calling alarms are explicit records and never an implicit notification channel for ordinary reminders. The GUI supports one-time, daily, and selected-weekday schedules; timezone-aware execution; enable/disable; test calls; snooze; cancellation; history; configurable ring/retry limits; and optional SMS fallback. Attempts and outcomes are durable, answered calls acknowledge the occurrence, uncertain calls are not automatically repeated, and per-user rate limiting prevents call storms.

SMS and Telegram provide alarm creation/listing/management plus **call me**. Expired safety check-ins can trigger a configured calling alarm through `user.config.checkin_alarm_id`. The generic trigger API can be used by explicitly configured critical home alerts and medication workflows.

The regular Jobs UI also exposes a `phone_call` job type for daily, weekly, interval, or manually started calls. Its target may be a Hugin user ID, username/display name, or explicit E.164 number, with a configurable 5–60 second ringing window. Each execution is recorded in the normal job-run history.

## Planned extensions

1. **Critical home alerts** — add GUI bindings from selected power, water, freezer, and security events to an alarm. These remain supplementary alerts, not certified life-safety alarms.
2. **Morning briefing** — speak calendar, weather, and the first appointment if modem audio is proven reliable.
3. **Call trees** — call explicitly configured backup contacts after the primary user.
4. **DTMF snooze** — only after two-way modem audio and tone detection are proven reliable.
