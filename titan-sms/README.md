# Titan SMS

Titan SMS is an isolated, native Kotlin SMS application for the Unihertz Titan
Pocket (Android 11). It keeps ordinary SMS threads ordinary while projecting
the repository's readable SMS-hub protocol into separate local conversations.
It has no Internet permission and uses no hub API: every transport operation is
an SMS to or from the configured hub number.

## Safety and data model

- Android's SMS provider remains the transport source of truth. It stores the
  real phone number and complete raw body, including hub routing prefixes.
- `titan-sms.db` is only a local projection: virtual conversations, parsed
  bodies, references, raw-provider links, chunks, unread counts, and send state.
  Virtual aliases never become fake contacts or provider recipients.
- Parsing is activated only when the normalized sender matches the configured
  hub number. Parser v1 mirrors `sms-bot/src/conversation_routing.py` and the
  independent chunk format in `sms-bot/src/sms_handler.py`.
- Provider IDs are unique in the local link table, making repeated imports
  idempotent. Re-index clears only the projection and never sends or alters SMS.
- A selected subscription ID must still be active at send time. Removal stops
  the send with a visible error; another SIM is never chosen implicitly.
- Retry is deliberately manual. A failed/uncertain item remains visible and its
  **Retry deliberately** action warns about duplicate risk before creating a
  new attempt. The app never retries after restart.

## Android role and permissions

The manifest supplies all handlers Android requires of an SMS-role candidate:
`SENDTO`, `SMS_DELIVER`, `WAP_PUSH_DELIVER`, and
`RESPOND_VIA_MESSAGE`. On Android 11 the app requests `RoleManager.ROLE_SMS`,
then the SMS/phone runtime permissions. Refusal leaves the UI usable for
already indexed data and clearly disables provider access, sending, and
background reception.

Incoming SMS is inserted into the inbox by the default handler. Outgoing SMS is
inserted once as an outbox record, sent with
`SmsManager.getSmsManagerForSubscriptionId`, and moved to sent or failed from
per-part sent callbacks. Delivery callbacks are tracked separately: carrier
delivery confirmation does not mean Telegram/service delivery or reading.
`(hub) Sent to …` is displayed as a system response and is never guessed to be
an acknowledgement for one particular outgoing message.

## UI and keyboard

The interface uses platform widgets and a single dense column for the 716 × 720
display. Every operation is reachable by D-pad/focus navigation and by touch.

- `Enter` inserts a newline in the composer.
- `Ctrl+Enter` sends.
- `Ctrl+L` focuses the composer.
- Android Back returns from a chat to the conversation list.
- Select a referenced incoming message and choose **Reply to #…** for an
  explicit reference reply. The selected reference is retained even if another
  message arrives.

The Titan Pocket manual documents physical Shift and Alt keys and allows its Fn
key to be assigned as Ctrl under **Settings → Intelligent assistance → Shortcut
settings → Fn key**. Configure Fn as Ctrl for the two app shortcuts above. The
Send button remains the always-available, remapping-independent action.

## Build and tests

Open `titan-sms` in Android Studio, use JDK 17, install Android SDK 35, then run:

```sh
./gradlew test
./gradlew assembleDebug
```

Install the debug APK only when ready to perform the manual validation. Building
does not deploy it and the repository contains no command that sends a real SMS.

## Titan Pocket manual validation checklist

Do this with a test SIM/number. Sending real SMS or deploying to the phone must
be explicitly authorized first.

1. **Role and refusal:** Launch without accepting the SMS role. Confirm the
   warning remains, browsing works, and Send fails without opening another SMS
   app. Grant the role and permissions, relaunch, and verify the warning clears.
2. **Configuration:** Enter the hub in national and then international format;
   re-index and verify only that number activates headers. Send the same header
   from an ordinary contact and verify it stays in that phone-number thread.
3. **Dual SIM:** Select SIM 2 and send a test normal SMS. Confirm SIM 2 is used.
   Remove/disable it and verify sending stops with a selection error and never
   switches to SIM 1. Reinsert it and explicitly select its current subscription.
4. **Normal SMS:** With the UI closed, receive a normal SMS. Confirm one
   notification, unread count, phone-number conversation, raw provider record,
   reply, sent state, and (where supported) later delivery-confirmed state.
5. **Hub projection:** Receive Nikolai and Family fixture messages. Confirm
   separate `Nikolai · Telegram` and `Family · Telegram` chats, while another
   SMS app still shows readable originals in the real hub-number thread.
6. **Routing:** Send multiline text in Nikolai and inspect Details for the exact
   `tg/nikolai ` envelope. Select #184, choose Reply, let another message arrive,
   then send and verify the envelope still starts `#184 `.
7. **Chunks:** Deliver parts 2/2, duplicate 2/2, then 1/2. Confirm one incomplete
   item first lists missing part 1 and later becomes one correctly ordered body.
8. **Recovery:** Import twice and verify counts/messages do not duplicate. Send
   a historical `#999 text` with no mapping, re-index, and confirm it remains in
   Hub. Restart during a failed/unknown send and confirm nothing is resent.
9. **Notifications:** Close the UI, receive a virtual message, verify its alias
   title, tap into the right chat, and test notification Reply. Enable privacy
   and confirm lock-screen/message text is hidden.
10. **Keyboard/layout:** At the smallest preferred font/display size and again
    at a larger accessibility font, traverse every control with D-pad/Enter.
    Confirm Back, multiline Enter, Fn(Ctrl)+L, Fn(Ctrl)+Enter, scrolling, reply
    selection, and the touch Send button on the square screen.
11. **Role switching:** Make the stock app default, receive SMS there, then make
    Titan SMS default and import. Confirm the readable raw hub messages survived
    and reconstruct the same virtual chats.

## Initial-release limits

Text SMS is supported. MMS, RCS, attachments, and group MMS are outside v0.1.
The required MMS role receiver creates an explicit local “Unsupported content”
item and notification instead of failing silently; it does not decode or persist
the MMS payload, so make an MMS-capable application the default before receiving
MMS. Contact-name lookup, message
search, export, and automatic `/chats` discovery are also deferred. New virtual
conversations accept an explicit protocol alias because aliases are routing
identifiers and must not be inferred as stable external identities.
