-- Average crack by calendar month.
-- 2022 (Russia-Ukraine) and 2026 (Iran war / Strait of Hormuz) are excluded
-- because one-off supply shocks swamp the normal seasonal pattern.
-- Seasonality is measured relative to each year's own average, so a
-- high-margin year does not distort the monthly shape.
WITH yearly AS (
    SELECT year,
           AVG(gasoline_crack) AS yr_gas,
           AVG(diesel_crack)   AS yr_dsl,
           AVG(crack_321_brent) AS yr_321
    FROM v_monthly_cracks
    GROUP BY year
)
SELECT
    m.cal_month,
    ROUND(AVG(m.gasoline_crack  - y.yr_gas), 2) AS gasoline_vs_year_avg,
    ROUND(AVG(m.diesel_crack    - y.yr_dsl), 2) AS diesel_vs_year_avg,
    ROUND(AVG(m.crack_321_brent - y.yr_321), 2) AS crack_321_vs_year_avg,
    COUNT(*)                                    AS n_years
FROM v_monthly_cracks m
JOIN yearly y USING (year)
WHERE m.year NOT IN (2022, 2026)
  AND m.year BETWEEN 2007 AND 2025          -- full calendar years only
GROUP BY m.cal_month
ORDER BY m.cal_month;
