-- Power readings: each MQTT update stored with timestamp
CREATE TABLE IF NOT EXISTS power_readings (
    id          BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pv1_power   DOUBLE PRECISION,   -- watts
    pv2_power   DOUBLE PRECISION,   -- watts
    grid_power  DOUBLE PRECISION,   -- watts
    grid_status TEXT
);

-- Index for time-range queries (last hour, today, etc.)
CREATE INDEX IF NOT EXISTS idx_readings_recorded_at ON power_readings (recorded_at DESC);

-- Daily energy totals (calculated by aggregator)
CREATE TABLE IF NOT EXISTS daily_energy (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL UNIQUE,
    pv1_energy_wh   DOUBLE PRECISION NOT NULL DEFAULT 0,
    pv2_energy_wh   DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_energy_wh DOUBLE PRECISION NOT NULL DEFAULT 0,
    grid_energy_wh  DOUBLE PRECISION NOT NULL DEFAULT 0,
    pv1_max_power   DOUBLE PRECISION NOT NULL DEFAULT 0,
    pv2_max_power   DOUBLE PRECISION NOT NULL DEFAULT 0,
    grid_max_power  DOUBLE PRECISION NOT NULL DEFAULT 0,
    reading_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_energy_date ON daily_energy (date DESC);
