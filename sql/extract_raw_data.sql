-- ============================================================
-- P01 Healthcare SQL | MedCore Analytics
-- St. Aurelius General Hospital
-- Schema: healthcare
-- ============================================================
-- ===========================================================================
-- UNDERSTAND: How to use this file
-- ---------------------------------------------------------------------------
-- This is PostgreSQL SQL, not Python. You can run it two ways:
--   1. DBeaver: highlight ONE query block (between semicolons), click Execute.
--   2. Python:  DataExtractor calls run_file() which executes the ENTIRE file;
--      pandas returns only the LAST query's result (Section 5 — production join).
--
-- healthcare.patients means schema.table in Postgres:
--   schema = namespace (like a folder for tables)
--   patients = table name inside that schema
-- ===========================================================================


-- ============================================================
-- SECTION 1: BASICS — Explore each table
-- ============================================================
-- ---------------------------------------------------------------------------
-- SECTION 1 — BASICS
-- SELECT * = all columns; LIMIT n = first n rows only;
-- DISTINCT = unique values; COUNT(*) = how many rows in a table.
-- ---------------------------------------------------------------------------

-- 1.1 Preview all patients
SELECT *
FROM healthcare.patients
LIMIT 10;

-- 1.2 Preview all doctors
SELECT *
FROM healthcare.doctors
LIMIT 10;

-- 1.3 Preview all appointments
SELECT *
FROM healthcare.appointments
LIMIT 10;

-- 1.4 Preview billing records
SELECT *
FROM healthcare.billing
LIMIT 10;

-- 1.5 Row counts per table
SELECT 'patients'     AS table_name, COUNT(*) AS row_count FROM healthcare.patients
UNION ALL
SELECT 'doctors',                    COUNT(*)               FROM healthcare.doctors
UNION ALL
SELECT 'appointments',               COUNT(*)               FROM healthcare.appointments
UNION ALL
SELECT 'billing',                    COUNT(*)               FROM healthcare.billing;

-- 1.6 Distinct appointment statuses
SELECT DISTINCT status
FROM healthcare.appointments;

-- 1.7 Distinct payment statuses
SELECT DISTINCT payment_status
FROM healthcare.billing;

-- 1.8 Distinct visit types
SELECT DISTINCT visit_type
FROM healthcare.appointments;

-- 1.9 Distinct insurance types
SELECT DISTINCT insurance_type
FROM healthcare.patients;


-- ============================================================
-- SECTION 2: AGGREGATIONS — Summary statistics
-- ============================================================
-- ---------------------------------------------------------------------------
-- SECTION 2 — AGGREGATIONS
-- GROUP BY collapses rows that share a category (e.g. payment_status).
-- SUM/AVG/COUNT compute metrics per group — answers "how much per status?"
-- ---------------------------------------------------------------------------

-- 2.1 Total revenue summary
SELECT
    SUM(amount_charged)  AS total_charged,
    SUM(insurance_paid)  AS total_insurance_paid,
    SUM(patient_paid)    AS total_patient_paid,
    COUNT(*)             AS total_bills
FROM healthcare.billing;

-- 2.2 Revenue by payment status
SELECT
    payment_status,
    COUNT(*)             AS num_bills,
    SUM(amount_charged)  AS total_charged,
    SUM(patient_paid)    AS total_collected
FROM healthcare.billing
GROUP BY payment_status
ORDER BY total_charged DESC;

-- 2.3 Revenue by payment method
SELECT
    payment_method,
    COUNT(*)             AS num_transactions,
    SUM(amount_charged)  AS total_charged
FROM healthcare.billing
GROUP BY payment_method
ORDER BY total_charged DESC;

-- 2.4 Appointments by status
SELECT
    status,
    COUNT(*) AS total_appointments
FROM healthcare.appointments
GROUP BY status
ORDER BY total_appointments DESC;

-- 2.5 Appointments by visit type
SELECT
    visit_type,
    COUNT(*)             AS total_visits,
    AVG(duration_mins)   AS avg_duration_mins,
    AVG(fee)             AS avg_fee
FROM healthcare.appointments
GROUP BY visit_type
ORDER BY total_visits DESC;

-- 2.6 Patient count by city
SELECT
    city,
    COUNT(*) AS num_patients
FROM healthcare.patients
GROUP BY city
ORDER BY num_patients DESC;

-- 2.7 Patient count by insurance type
SELECT
    insurance_type,
    COUNT(*) AS num_patients
FROM healthcare.patients
GROUP BY insurance_type
ORDER BY num_patients DESC;

-- 2.8 Doctor count by specialization
SELECT
    specialization,
    COUNT(*)         AS num_doctors,
    AVG(years_exp)   AS avg_years_exp,
    AVG(salary)      AS avg_salary
FROM healthcare.doctors
GROUP BY specialization
ORDER BY num_doctors DESC;

-- 2.9 Monthly appointment volume
SELECT
    DATE_TRUNC('month', appointment_date) AS month,
    COUNT(*)                               AS total_appointments
FROM healthcare.appointments
GROUP BY month
ORDER BY month;

-- 2.10 Monthly billing revenue
SELECT
    DATE_TRUNC('month', bill_date) AS month,
    SUM(amount_charged)             AS total_charged,
    SUM(patient_paid)               AS total_collected
FROM healthcare.billing
GROUP BY month
ORDER BY month;


-- ============================================================
-- SECTION 3: JOINS — Combined views
-- ============================================================
-- ---------------------------------------------------------------------------
-- SECTION 3 — JOINS
-- JOIN connects tables where keys match (patient_id, appointment_id, doctor_id).
-- INNER JOIN keeps only rows that exist in BOTH tables being joined.
-- ---------------------------------------------------------------------------

-- 3.1 Patients with their appointments
SELECT
    p.patient_id,
    p.first_name,
    p.last_name,
    p.gender,
    p.city,
    p.insurance_type,
    a.appointment_id,
    a.appointment_date,
    a.appointment_time,
    a.status,
    a.visit_type,
    a.duration_mins,
    a.fee
FROM healthcare.patients p
JOIN healthcare.appointments a ON p.patient_id = a.patient_id
ORDER BY a.appointment_date DESC
LIMIT 20;

-- 3.2 Appointments with doctor details
SELECT
    a.appointment_id,
    a.appointment_date,
    a.status,
    a.visit_type,
    a.fee,
    d.first_name  AS doctor_first_name,
    d.last_name   AS doctor_last_name,
    d.specialization,
    d.years_exp
FROM healthcare.appointments a
JOIN healthcare.doctors d ON a.doctor_id = d.doctor_id
ORDER BY a.appointment_date DESC
LIMIT 20;

-- 3.3 Billing with patient details
SELECT
    b.bill_id,
    b.bill_date,
    b.amount_charged,
    b.insurance_paid,
    b.patient_paid,
    b.payment_status,
    b.payment_method,
    p.first_name,
    p.last_name,
    p.insurance_type,
    p.city
FROM healthcare.billing b
JOIN healthcare.patients p ON b.patient_id = p.patient_id
ORDER BY b.bill_date DESC
LIMIT 20;

-- 3.4 Full join — patients + appointments + billing + doctors
SELECT
    p.patient_id,
    p.first_name                  AS patient_first_name,
    p.last_name                   AS patient_last_name,
    p.gender,
    p.city,
    p.insurance_type,
    a.appointment_id,
    a.appointment_date,
    a.status                      AS appointment_status,
    a.visit_type,
    a.duration_mins,
    a.fee                         AS appointment_fee,
    d.first_name                  AS doctor_first_name,
    d.last_name                   AS doctor_last_name,
    d.specialization,
    b.bill_id,
    b.amount_charged,
    b.insurance_paid,
    b.patient_paid,
    b.payment_status,
    b.payment_method,
    b.bill_date
FROM healthcare.patients p
JOIN healthcare.appointments a  ON p.patient_id  = a.patient_id
JOIN healthcare.doctors d       ON a.doctor_id   = d.doctor_id
JOIN healthcare.billing b       ON a.appointment_id = b.appointment_id
ORDER BY a.appointment_date DESC;

-- 3.5 Revenue per doctor
SELECT
    d.doctor_id,
    d.first_name || ' ' || d.last_name  AS doctor_name,
    d.specialization,
    COUNT(b.bill_id)                     AS total_bills,
    SUM(b.amount_charged)                AS total_revenue,
    AVG(b.amount_charged)                AS avg_bill_amount
FROM healthcare.doctors d
JOIN healthcare.appointments a ON d.doctor_id   = a.doctor_id
JOIN healthcare.billing b      ON a.appointment_id = b.appointment_id
GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization
ORDER BY total_revenue DESC;

-- 3.6 Patients with outstanding balances (unpaid bills)
SELECT
    p.patient_id,
    p.first_name || ' ' || p.last_name  AS patient_name,
    p.city,
    p.insurance_type,
    COUNT(b.bill_id)                     AS unpaid_bills,
    SUM(b.amount_charged)                AS total_owed
FROM healthcare.patients p
JOIN healthcare.billing b ON p.patient_id = b.patient_id
WHERE b.payment_status = 'Unpaid'
GROUP BY p.patient_id, p.first_name, p.last_name, p.city, p.insurance_type
ORDER BY total_owed DESC;


-- ============================================================
-- SECTION 4: CTEs & WINDOW FUNCTIONS
-- ============================================================
-- ---------------------------------------------------------------------------
-- SECTION 4 — CTEs & WINDOW FUNCTIONS
-- WITH name AS (SELECT ...) creates a temporary named result you reuse below.
-- RANK() OVER (ORDER BY ...) ranks rows; LAG() compares to previous row (trends).
-- ---------------------------------------------------------------------------

-- 4.1 CTE — Patient billing summary
WITH patient_billing AS (
    SELECT
        p.patient_id,
        p.first_name || ' ' || p.last_name  AS patient_name,
        p.insurance_type,
        COUNT(b.bill_id)                     AS total_bills,
        SUM(b.amount_charged)                AS total_charged,
        SUM(b.insurance_paid)                AS total_insurance_paid,
        SUM(b.patient_paid)                  AS total_patient_paid,
        SUM(b.amount_charged - b.insurance_paid - b.patient_paid) AS outstanding_balance
    FROM healthcare.patients p
    JOIN healthcare.billing b ON p.patient_id = b.patient_id
    GROUP BY p.patient_id, p.first_name, p.last_name, p.insurance_type
)
SELECT *
FROM patient_billing
ORDER BY total_charged DESC;

-- 4.2 CTE — Doctor performance summary
WITH doctor_performance AS (
    SELECT
        d.doctor_id,
        d.first_name || ' ' || d.last_name  AS doctor_name,
        d.specialization,
        d.years_exp,
        COUNT(DISTINCT a.appointment_id)     AS total_appointments,
        COUNT(DISTINCT a.patient_id)         AS unique_patients,
        SUM(b.amount_charged)                AS total_revenue,
        AVG(a.duration_mins)                 AS avg_appointment_duration
    FROM healthcare.doctors d
    JOIN healthcare.appointments a  ON d.doctor_id      = a.doctor_id
    JOIN healthcare.billing b       ON a.appointment_id = b.appointment_id
    GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization, d.years_exp
)
SELECT *
FROM doctor_performance
ORDER BY total_revenue DESC;

-- 4.3 Window function — Rank patients by total spend
SELECT
    p.patient_id,
    p.first_name || ' ' || p.last_name      AS patient_name,
    p.city,
    SUM(b.amount_charged)                    AS total_charged,
    RANK() OVER (ORDER BY SUM(b.amount_charged) DESC) AS spend_rank
FROM healthcare.patients p
JOIN healthcare.billing b ON p.patient_id = b.patient_id
GROUP BY p.patient_id, p.first_name, p.last_name, p.city
ORDER BY spend_rank;

-- 4.4 Window function — Running total revenue over time
SELECT
    bill_date,
    amount_charged,
    SUM(amount_charged) OVER (ORDER BY bill_date) AS running_total_revenue
FROM healthcare.billing
ORDER BY bill_date;

-- 4.5 Window function — Rank doctors by revenue within each specialization
SELECT
    d.first_name || ' ' || d.last_name       AS doctor_name,
    d.specialization,
    SUM(b.amount_charged)                     AS total_revenue,
    RANK() OVER (
        PARTITION BY d.specialization
        ORDER BY SUM(b.amount_charged) DESC
    )                                         AS rank_within_specialization
FROM healthcare.doctors d
JOIN healthcare.appointments a  ON d.doctor_id      = a.doctor_id
JOIN healthcare.billing b       ON a.appointment_id = b.appointment_id
GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization
ORDER BY d.specialization, rank_within_specialization;

-- 4.6 CTE + Window — Month-over-month revenue growth
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', bill_date)  AS month,
        SUM(amount_charged)              AS revenue
    FROM healthcare.billing
    GROUP BY month
)
SELECT
    month,
    revenue,
    LAG(revenue) OVER (ORDER BY month)  AS prev_month_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY month))
        / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) * 100, 2
    )                                    AS pct_growth
FROM monthly_revenue
ORDER BY month;


-- ============================================================
-- SECTION 5: RAW DATA EXTRACT (for raw-data.csv)
-- ============================================================
-- ---------------------------------------------------------------------------
-- SECTION 5 — PRODUCTION EXTRACT (this result becomes data/raw-data.csv)
-- One SELECT joins patients + appointments + doctors + billing into ~30 columns.
-- Python's run_file() returns THIS query's rows to DataExtractor.save().
-- ---------------------------------------------------------------------------

SELECT
    p.patient_id,
    p.first_name                  AS patient_first_name,
    p.last_name                   AS patient_last_name,
    p.date_of_birth,
    p.gender,
    p.blood_type,
    p.city,
    p.insurance_type,
    p.email                       AS patient_email,
    p.phone                       AS patient_phone,
    a.appointment_id,
    a.appointment_date,
    a.appointment_time,
    a.status                      AS appointment_status,
    a.visit_type,
    a.duration_mins,
    a.fee                         AS appointment_fee,
    a.notes,
    d.doctor_id,
    d.first_name                  AS doctor_first_name,
    d.last_name                   AS doctor_last_name,
    d.specialization,
    d.years_exp                   AS doctor_years_exp,
    b.bill_id,
    b.amount_charged,
    b.insurance_paid,
    b.patient_paid,
    b.payment_status,
    b.payment_method,
    b.bill_date
FROM healthcare.patients p
JOIN healthcare.appointments a  ON p.patient_id     = a.patient_id
JOIN healthcare.doctors d       ON a.doctor_id      = d.doctor_id
JOIN healthcare.billing b       ON a.appointment_id = b.appointment_id
ORDER BY a.appointment_date DESC;