-- =====================================================================
-- 01_schema_and_views.sql
-- Raw prices are stored in long format; views pivot them and compute
-- crack spreads so every downstream query works off one definition.
-- =====================================================================

DROP TABLE IF EXISTS prices;
CREATE TABLE prices (
    date       TEXT NOT NULL,      -- ISO date, YYYY-MM-DD
    series_id  TEXT NOT NULL,      -- FRED series code
    value      REAL NOT NULL,
    PRIMARY KEY (date, series_id)
);

DROP TABLE IF EXISTS series_meta;
CREATE TABLE series_meta (
    series_id  TEXT PRIMARY KEY,
    name       TEXT,
    unit       TEXT
);
INSERT INTO series_meta VALUES
    ('DCOILBRENTEU', 'Brent crude (Europe)',              'USD/bbl'),
    ('DCOILWTICO',   'WTI crude (Cushing)',                'USD/bbl'),
    ('DGASNYH',      'Conventional gasoline (NY Harbor)',  'USD/gal'),
    ('DDFUELNYH',    'Ultra-low-sulphur diesel (NY Harbor)','USD/gal');

-- ---------------------------------------------------------------------
-- Wide daily table: one row per trading day where ALL four prices exist.
-- Products are converted from USD/gal to USD/bbl (1 bbl = 42 US gal).
-- ---------------------------------------------------------------------
DROP VIEW IF EXISTS v_daily_prices;
CREATE VIEW v_daily_prices AS
SELECT
    date,
    MAX(CASE WHEN series_id = 'DCOILBRENTEU' THEN value END)      AS brent,
    MAX(CASE WHEN series_id = 'DCOILWTICO'   THEN value END)      AS wti,
    MAX(CASE WHEN series_id = 'DGASNYH'      THEN value END) * 42 AS gasoline,
    MAX(CASE WHEN series_id = 'DDFUELNYH'    THEN value END) * 42 AS diesel
FROM prices
GROUP BY date
HAVING COUNT(DISTINCT series_id) = 4;

-- ---------------------------------------------------------------------
-- Crack spreads (USD per barrel of crude processed)
--   3-2-1 crack = (2 x gasoline + 1 x diesel - 3 x crude) / 3
--   Single-product cracks = product price - crude price
-- Brent is the main benchmark (NW European / Atlantic Basin refiner);
-- the WTI version shows the advantage of a US inland refiner.
-- ---------------------------------------------------------------------
DROP VIEW IF EXISTS v_daily_cracks;
CREATE VIEW v_daily_cracks AS
SELECT
    date,
    brent, wti, gasoline, diesel,
    (2 * gasoline + diesel - 3 * brent) / 3.0  AS crack_321_brent,
    (2 * gasoline + diesel - 3 * wti)   / 3.0  AS crack_321_wti,
    gasoline - brent                            AS gasoline_crack,
    diesel   - brent                            AS diesel_crack,
    diesel   - gasoline                         AS diesel_premium,
    brent    - wti                              AS brent_wti_spread
FROM v_daily_prices;

-- Monthly averages (the basis for seasonality and the hedging backtest)
DROP VIEW IF EXISTS v_monthly_cracks;
CREATE VIEW v_monthly_cracks AS
SELECT
    strftime('%Y-%m', date)          AS month,
    CAST(strftime('%Y', date) AS INT) AS year,
    CAST(strftime('%m', date) AS INT) AS cal_month,
    COUNT(*)                          AS trading_days,
    AVG(brent)            AS brent,
    AVG(wti)              AS wti,
    AVG(gasoline)         AS gasoline,
    AVG(diesel)           AS diesel,
    AVG(crack_321_brent)  AS crack_321_brent,
    AVG(crack_321_wti)    AS crack_321_wti,
    AVG(gasoline_crack)   AS gasoline_crack,
    AVG(diesel_crack)     AS diesel_crack,
    AVG(brent_wti_spread) AS brent_wti_spread
FROM v_daily_cracks
GROUP BY month;
