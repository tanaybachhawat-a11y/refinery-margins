-- The ten best and ten worst months for the Brent 3-2-1 crack.
SELECT 'best' AS bucket, month, ROUND(crack_321_brent, 2) AS crack_321,
       ROUND(gasoline_crack, 2) AS gasoline_crack, ROUND(diesel_crack, 2) AS diesel_crack
FROM (SELECT * FROM v_monthly_cracks ORDER BY crack_321_brent DESC LIMIT 10)
UNION ALL
SELECT 'worst', month, ROUND(crack_321_brent, 2),
       ROUND(gasoline_crack, 2), ROUND(diesel_crack, 2)
FROM (SELECT * FROM v_monthly_cracks ORDER BY crack_321_brent ASC LIMIT 10);
