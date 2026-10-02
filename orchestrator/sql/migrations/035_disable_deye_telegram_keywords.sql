-- Deye queries are handled by the Telegram bot's /deye CommandHandler.
-- Disable the legacy relay preset so ordinary messages containing words such
-- as "sol", "solar", "solenergi", or "inverter" do not invoke the webhook.
UPDATE message_relay_routes
SET enabled = 0,
    updated_at = NOW()
WHERE name = 'Deye solar query'
  AND is_preset = 1;
