PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS countries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    iso_code        TEXT,
    region          TEXT,
    is_popular      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resorts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    country_id      INTEGER NOT NULL,
    name            TEXT NOT NULL,
    is_coastal      INTEGER DEFAULT 0,
    avg_temp_summer REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (country_id) REFERENCES countries(id),
    UNIQUE(country_id, name)
);

CREATE TABLE IF NOT EXISTS tour_operators (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    short_name      TEXT,
    is_active       INTEGER DEFAULT 1,
    website         TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS operator_mapping (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     INTEGER NOT NULL,
    raw_name        TEXT NOT NULL,
    source          TEXT,
    confidence      REAL DEFAULT 1.0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (operator_id) REFERENCES tour_operators(id),
    UNIQUE(raw_name, source)
);

CREATE TABLE IF NOT EXISTS geo_aliases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,
    alias_name      TEXT NOT NULL,
    country_id      INTEGER,
    resort_id       INTEGER,
    source          TEXT,
    confidence      REAL DEFAULT 1.0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (country_id) REFERENCES countries(id),
    FOREIGN KEY (resort_id) REFERENCES resorts(id),
    UNIQUE(entity_type, alias_name, source)
);

CREATE TABLE IF NOT EXISTS hotels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resort_id       INTEGER NOT NULL,
    name            TEXT NOT NULL,
    star_rating     REAL,
    meal_plan       TEXT,
    latitude        REAL,
    longitude       REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (resort_id) REFERENCES resorts(id)
);

CREATE TABLE IF NOT EXISTS hotel_aliases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hotel_id        INTEGER NOT NULL,
    operator_id     INTEGER,
    alias_name      TEXT NOT NULL,
    source          TEXT,
    confidence      REAL DEFAULT 1.0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (hotel_id) REFERENCES hotels(id),
    FOREIGN KEY (operator_id) REFERENCES tour_operators(id),
    UNIQUE(alias_name, operator_id, source)
);

CREATE TABLE IF NOT EXISTS tours (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     INTEGER NOT NULL,
    hotel_id        INTEGER NOT NULL,
    country_id      INTEGER NOT NULL,
    resort_id       INTEGER NOT NULL,
    departure_date  TEXT NOT NULL,
    duration_nights INTEGER NOT NULL,
    meal_type       TEXT,
    actual_price    REAL NOT NULL,
    original_price  REAL,
    discount_pct    REAL DEFAULT 0,
    adults          INTEGER DEFAULT 2,
    children        INTEGER DEFAULT 0,
    room_type       TEXT,
    is_available    INTEGER DEFAULT 1,
    source_url      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (operator_id) REFERENCES tour_operators(id),
    FOREIGN KEY (hotel_id) REFERENCES hotels(id),
    FOREIGN KEY (country_id) REFERENCES countries(id),
    FOREIGN KEY (resort_id) REFERENCES resorts(id)
);

CREATE TABLE IF NOT EXISTS source_import_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     INTEGER,
    source_name     TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    file_path       TEXT,
    records_total   INTEGER DEFAULT 0,
    records_loaded  INTEGER DEFAULT 0,
    records_failed  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    started_at      TEXT,
    finished_at     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (operator_id) REFERENCES tour_operators(id)
);

CREATE TABLE IF NOT EXISTS hotels_raw (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     INTEGER,
    raw_name        TEXT NOT NULL,
    raw_country     TEXT,
    raw_resort      TEXT,
    raw_stars       TEXT,
    raw_meal        TEXT,
    source_name     TEXT,
    source_type     TEXT,
    hotel_id        INTEGER,
    is_processed    INTEGER DEFAULT 0,
    load_batch      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (operator_id) REFERENCES tour_operators(id),
    FOREIGN KEY (hotel_id) REFERENCES hotels(id)
);

CREATE TABLE IF NOT EXISTS tours_raw (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id     INTEGER,
    raw_hotel_name  TEXT,
    raw_country     TEXT,
    raw_resort      TEXT,
    raw_price       TEXT,
    raw_departure   TEXT,
    raw_duration    TEXT,
    raw_meal        TEXT,
    raw_adults      TEXT,
    raw_children    TEXT,
    source_name     TEXT,
    source_type     TEXT,
    tour_id         INTEGER,
    is_processed    INTEGER DEFAULT 0,
    error_type      TEXT,
    load_batch      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (operator_id) REFERENCES tour_operators(id),
    FOREIGN KEY (tour_id) REFERENCES tours(id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tour_id         INTEGER NOT NULL,
    price           REAL NOT NULL,
    recorded_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (tour_id) REFERENCES tours(id)
);

CREATE TABLE IF NOT EXISTS hotel_duplicates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hotel_id_1      INTEGER NOT NULL,
    hotel_id_2      INTEGER NOT NULL,
    similarity      REAL NOT NULL,
    status          TEXT DEFAULT 'pending',
    resolved_by     TEXT,
    resolved_at     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (hotel_id_1) REFERENCES hotels(id),
    FOREIGN KEY (hotel_id_2) REFERENCES hotels(id)
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT,
    email           TEXT,
    city            TEXT,
    age_group       TEXT,
    registered_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    session_id      TEXT NOT NULL,
    country_id      INTEGER,
    resort_id       INTEGER,
    date_from       TEXT,
    date_to         TEXT,
    adults          INTEGER,
    children        INTEGER,
    max_price       REAL,
    min_duration    INTEGER,
    results_count   INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (country_id) REFERENCES countries(id),
    FOREIGN KEY (resort_id) REFERENCES resorts(id)
);

CREATE TABLE IF NOT EXISTS tour_views (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    session_id      TEXT NOT NULL,
    tour_id         INTEGER NOT NULL,
    view_duration   INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tour_id) REFERENCES tours(id)
);

CREATE TABLE IF NOT EXISTS click_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    session_id      TEXT NOT NULL,
    tour_id         INTEGER NOT NULL,
    click_type      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tour_id) REFERENCES tours(id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    session_id      TEXT,
    tour_id         INTEGER NOT NULL,
    booking_date    TEXT NOT NULL,
    total_price     REAL NOT NULL,
    status          TEXT DEFAULT 'pending',
    adults          INTEGER DEFAULT 2,
    children        INTEGER DEFAULT 0,
    contact_email   TEXT,
    contact_phone   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tour_id) REFERENCES tours(id)
);

CREATE TABLE IF NOT EXISTS load_errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table    TEXT NOT NULL,
    raw_record_id   INTEGER,
    error_type      TEXT NOT NULL,
    error_message   TEXT,
    raw_data        TEXT,
    is_resolved     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    log_level       TEXT DEFAULT 'INFO',
    module          TEXT,
    message         TEXT,
    details         TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS data_quality_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name      TEXT NOT NULL,
    check_category  TEXT,
    table_name      TEXT,
    total_records   INTEGER,
    failed_records  INTEGER,
    fail_pct        REAL,
    details         TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tours_country_date         ON tours(country_id, departure_date);
CREATE INDEX IF NOT EXISTS idx_tours_actual_price         ON tours(actual_price);
CREATE INDEX IF NOT EXISTS idx_tours_operator             ON tours(operator_id);
CREATE INDEX IF NOT EXISTS idx_tours_hotel                ON tours(hotel_id);
CREATE INDEX IF NOT EXISTS idx_tours_resort               ON tours(resort_id);
CREATE INDEX IF NOT EXISTS idx_tours_departure            ON tours(departure_date);
CREATE INDEX IF NOT EXISTS idx_tours_available            ON tours(is_available);
CREATE INDEX IF NOT EXISTS idx_tours_compound             ON tours(country_id, departure_date, actual_price);

CREATE INDEX IF NOT EXISTS idx_hotels_resort              ON hotels(resort_id);
CREATE INDEX IF NOT EXISTS idx_hotels_stars               ON hotels(star_rating);
CREATE INDEX IF NOT EXISTS idx_hotels_name                ON hotels(name);
CREATE INDEX IF NOT EXISTS idx_hotel_aliases_name         ON hotel_aliases(alias_name);

CREATE INDEX IF NOT EXISTS idx_geo_aliases_lookup         ON geo_aliases(entity_type, alias_name);
CREATE INDEX IF NOT EXISTS idx_operator_mapping_raw       ON operator_mapping(raw_name);

CREATE INDEX IF NOT EXISTS idx_price_history_tour         ON price_history(tour_id);
CREATE INDEX IF NOT EXISTS idx_price_history_date         ON price_history(recorded_at);

CREATE INDEX IF NOT EXISTS idx_search_logs_user           ON search_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_country        ON search_logs(country_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_session        ON search_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_created        ON search_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_tour_views_user            ON tour_views(user_id);
CREATE INDEX IF NOT EXISTS idx_tour_views_tour            ON tour_views(tour_id);
CREATE INDEX IF NOT EXISTS idx_tour_views_session         ON tour_views(session_id);

CREATE INDEX IF NOT EXISTS idx_click_logs_user            ON click_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_click_logs_tour            ON click_logs(tour_id);
CREATE INDEX IF NOT EXISTS idx_click_logs_session         ON click_logs(session_id);

CREATE INDEX IF NOT EXISTS idx_bookings_user              ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_tour              ON bookings(tour_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status            ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_date              ON bookings(booking_date);
CREATE INDEX IF NOT EXISTS idx_bookings_session           ON bookings(session_id);

CREATE INDEX IF NOT EXISTS idx_hotels_raw_processed       ON hotels_raw(is_processed);
CREATE INDEX IF NOT EXISTS idx_hotels_raw_source          ON hotels_raw(source_type, source_name);
CREATE INDEX IF NOT EXISTS idx_tours_raw_processed        ON tours_raw(is_processed);
CREATE INDEX IF NOT EXISTS idx_tours_raw_source           ON tours_raw(source_type, source_name);

CREATE INDEX IF NOT EXISTS idx_hotel_dup_status           ON hotel_duplicates(status);

CREATE INDEX IF NOT EXISTS idx_load_errors_resolved       ON load_errors(is_resolved);
CREATE INDEX IF NOT EXISTS idx_dq_reports_category        ON data_quality_reports(check_category);
CREATE INDEX IF NOT EXISTS idx_source_runs_status         ON source_import_runs(status);
