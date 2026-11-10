-- Annual summary of the Brent 3-2-1 crack and its components.
-- SQLite has no STDEV(), so standard deviation is computed as
-- sqrt(E[x^2] - E[x]^2) and finished in Python (SQRT is not built in everywhere).
SELECT
    CAST(strftime('%Y', date) AS INT)             AS year,
    COUNT(*)                                       AS trading_days,
    ROUND(AVG(brent), 2)                           AS avg_brent,
    ROUND(AVG(crack_321_brent), 2)                 AS avg_crack_321,
    ROUND(MIN(crack_321_brent), 2)                 AS min_crack_321,
    ROUND(MAX(crack_321_brent), 2)                 AS max_crack_321,
    AVG(crack_321_brent * crack_321_brent)
      - AVG(crack_321_brent) * AVG(crack_321_brent) AS var_crack_321,
    ROUND(AVG(gasoline_crack), 2)                  AS avg_gasoline_crack,
    ROUND(AVG(diesel_crack), 2)                    AS avg_diesel_crack,
    ROUND(AVG(brent_wti_spread), 2)                AS avg_brent_wti
FROM v_daily_cracks
GROUP BY year
ORDER BY year;
