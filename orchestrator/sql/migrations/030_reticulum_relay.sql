-- Reticulum/LXMF transport and routing endpoint. The cryptographic identity and
-- propagation store live in the reticulum-relay persistent volume.

INSERT INTO message_gateways (key, name, type)
VALUES ('reticulum-main', 'Reticulum node', 'reticulum')
ON CONFLICT (key) DO NOTHING;

INSERT INTO message_relay_endpoints
    (key, name, type, enabled, capabilities, config)
VALUES
    ('reticulum-main', 'Reticulum', 'reticulum', 1, '["source"]', '{}')
ON CONFLICT (key) DO NOTHING;

