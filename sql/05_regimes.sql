-- Compare margins across market regimes (dates are approximate event windows).
SELECT
    CASE
        WHEN date BETWEEN '2008-07-01' AND '2009-06-30' THEN '2008-09 financial crisis'
        WHEN date BETWEEN '2014-07-01' AND '2016-06-30' THEN '2014-16 oil price collapse'
        WHEN date BETWEEN '2020-03-01' AND '2020-12-31' THEN '2020 COVID demand shock'
        WHEN date BETWEEN '2022-02-24' AND '2022-12-31' THEN '2022 Russia-Ukraine'
        WHEN date BETWEEN '2026-02-28' AND '2026-12-31' THEN '2026 Iran war / Hormuz'
        ELSE 'Other periods'
    END AS regime,
    COUNT(*)                          AS trading_days,
    ROUND(AVG(brent), 1)              AS avg_brent,
    ROUND(AVG(crack_321_brent), 1)    AS avg_crack_321,
    ROUND(AVG(gasoline_crack), 1)     AS avg_gasoline_crack,
    ROUND(AVG(diesel_crack), 1)       AS avg_diesel_crack,
    ROUND(AVG(brent_wti_spread), 1)   AS avg_brent_wti
FROM v_daily_cracks
GROUP BY regime
ORDER BY MIN(date);
