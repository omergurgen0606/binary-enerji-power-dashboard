--
-- PostgreSQL database dump
--

\restrict JP3bEwbYm6ddAfSRXGpyypebSgrL7s1p7X2TxF9NPvFyfjqdDhvn5tK5JsRfNwn

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: device_energy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_energy (
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    device_id text NOT NULL,
    active_wh_tuketim bigint,
    inductive_varh_tuketim bigint,
    capacitive_varh_tuketim bigint,
    active_wh_uretim bigint,
    inductive_varh_uretim bigint,
    capacitive_varh_uretim bigint
);


--
-- Name: _direct_view_10; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._direct_view_10 AS
 SELECT device_id,
    public.time_bucket('01:00:00'::interval, "time") AS bucket,
    public.last("time", "time") AS reading_time,
    public.first(active_wh_tuketim, "time") AS first_active_tuketim,
    public.last(active_wh_tuketim, "time") AS active_wh_tuketim,
    max(active_wh_tuketim) AS max_active_tuketim,
    public.first(inductive_varh_tuketim, "time") AS first_inductive_tuketim,
    public.last(inductive_varh_tuketim, "time") AS inductive_varh_tuketim,
    max(inductive_varh_tuketim) AS max_inductive_tuketim,
    public.first(capacitive_varh_tuketim, "time") AS first_capacitive_tuketim,
    public.last(capacitive_varh_tuketim, "time") AS capacitive_varh_tuketim,
    max(capacitive_varh_tuketim) AS max_capacitive_tuketim,
    public.first(active_wh_uretim, "time") AS first_active_uretim,
    public.last(active_wh_uretim, "time") AS active_wh_uretim,
    max(active_wh_uretim) AS max_active_uretim,
    public.first(inductive_varh_uretim, "time") AS first_inductive_uretim,
    public.last(inductive_varh_uretim, "time") AS inductive_varh_uretim,
    max(inductive_varh_uretim) AS max_inductive_uretim,
    public.first(capacitive_varh_uretim, "time") AS first_capacitive_uretim,
    public.last(capacitive_varh_uretim, "time") AS capacitive_varh_uretim,
    max(capacitive_varh_uretim) AS max_capacitive_uretim
   FROM public.device_energy
  GROUP BY device_id, (public.time_bucket('01:00:00'::interval, "time"));


--
-- Name: measurements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.measurements (
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    device_id text NOT NULL,
    v1 double precision,
    i1 double precision,
    p1 double precision,
    f1 double precision,
    v2 double precision,
    i2 double precision,
    p2 double precision,
    v3 double precision,
    i3 double precision,
    p3 double precision,
    vl12 double precision,
    vl23 double precision,
    vl31 double precision,
    q1 double precision,
    q2 double precision,
    q3 double precision,
    s1 double precision,
    s2 double precision,
    s3 double precision,
    f2 double precision,
    f3 double precision,
    v_neutral double precision,
    i_neutral double precision,
    cos1 double precision,
    cos2 double precision,
    cos3 double precision,
    pf1 double precision,
    pf2 double precision,
    pf3 double precision,
    thd1 double precision,
    thd2 double precision,
    thd3 double precision,
    thvd1 double precision,
    thvd2 double precision,
    thvd3 double precision
);


--
-- Name: _direct_view_11; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._direct_view_11 AS
 SELECT device_id,
    public.time_bucket('00:10:00'::interval, "time") AS bucket,
    count(*) AS sample_count,
    avg(v1) AS avg_v1,
    min(v1) AS min_v1,
    max(v1) AS max_v1,
    avg(v2) AS avg_v2,
    min(v2) AS min_v2,
    max(v2) AS max_v2,
    avg(v3) AS avg_v3,
    min(v3) AS min_v3,
    max(v3) AS max_v3,
    avg(f1) AS avg_f,
    min(f1) AS min_f,
    max(f1) AS max_f,
    avg(thvd1) AS avg_thvd1,
    max(thvd1) AS max_thvd1,
    avg(thvd2) AS avg_thvd2,
    max(thvd2) AS max_thvd2,
    avg(thvd3) AS avg_thvd3,
    max(thvd3) AS max_thvd3
   FROM public.measurements
  GROUP BY device_id, (public.time_bucket('00:10:00'::interval, "time"));


--
-- Name: _direct_view_9; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._direct_view_9 AS
 SELECT device_id,
    public.time_bucket('00:15:00'::interval, "time") AS bucket,
    count(*) AS sample_count,
    avg(((COALESCE(p1, (0)::double precision) + COALESCE(p2, (0)::double precision)) + COALESCE(p3, (0)::double precision))) AS avg_total_p,
    max(((COALESCE(p1, (0)::double precision) + COALESCE(p2, (0)::double precision)) + COALESCE(p3, (0)::double precision))) AS max_total_p,
    avg(((COALESCE(q1, (0)::double precision) + COALESCE(q2, (0)::double precision)) + COALESCE(q3, (0)::double precision))) AS avg_total_q,
    avg(((COALESCE(s1, (0)::double precision) + COALESCE(s2, (0)::double precision)) + COALESCE(s3, (0)::double precision))) AS avg_total_s,
    avg(v1) AS avg_v1,
    min(v1) AS min_v1,
    max(v1) AS max_v1,
    avg(v2) AS avg_v2,
    min(v2) AS min_v2,
    max(v2) AS max_v2,
    avg(v3) AS avg_v3,
    min(v3) AS min_v3,
    max(v3) AS max_v3,
    avg(i1) AS avg_i1,
    max(i1) AS max_i1,
    avg(i2) AS avg_i2,
    max(i2) AS max_i2,
    avg(i3) AS avg_i3,
    max(i3) AS max_i3,
    avg(i_neutral) AS avg_i_neutral,
    max(i_neutral) AS max_i_neutral,
    avg(f1) AS avg_f,
    min(f1) AS min_f,
    max(f1) AS max_f,
    avg(pf1) AS avg_pf1,
    avg(pf2) AS avg_pf2,
    avg(pf3) AS avg_pf3,
    avg(thd1) AS avg_thd1,
    max(thd1) AS max_thd1,
    avg(thd2) AS avg_thd2,
    max(thd2) AS max_thd2,
    avg(thd3) AS avg_thd3,
    max(thd3) AS max_thd3,
    avg(thvd1) AS avg_thvd1,
    max(thvd1) AS max_thvd1,
    avg(thvd2) AS avg_thvd2,
    max(thvd2) AS max_thvd2,
    avg(thvd3) AS avg_thvd3,
    max(thvd3) AS max_thvd3
   FROM public.measurements
  GROUP BY device_id, (public.time_bucket('00:15:00'::interval, "time"));


--
-- Name: _materialized_hypertable_10; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_10 (
    device_id text,
    bucket timestamp with time zone NOT NULL,
    reading_time timestamp with time zone,
    first_active_tuketim bigint,
    active_wh_tuketim bigint,
    max_active_tuketim bigint,
    first_inductive_tuketim bigint,
    inductive_varh_tuketim bigint,
    max_inductive_tuketim bigint,
    first_capacitive_tuketim bigint,
    capacitive_varh_tuketim bigint,
    max_capacitive_tuketim bigint,
    first_active_uretim bigint,
    active_wh_uretim bigint,
    max_active_uretim bigint,
    first_inductive_uretim bigint,
    inductive_varh_uretim bigint,
    max_inductive_uretim bigint,
    first_capacitive_uretim bigint,
    capacitive_varh_uretim bigint,
    max_capacitive_uretim bigint
);


--
-- Name: _hyper_10_14_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_10_14_chunk (
    CONSTRAINT constraint_14 CHECK (((bucket >= '2026-07-16 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-09-24 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_10);


--
-- Name: _materialized_hypertable_11; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_11 (
    device_id text,
    bucket timestamp with time zone NOT NULL,
    sample_count bigint,
    avg_v1 double precision,
    min_v1 double precision,
    max_v1 double precision,
    avg_v2 double precision,
    min_v2 double precision,
    max_v2 double precision,
    avg_v3 double precision,
    min_v3 double precision,
    max_v3 double precision,
    avg_f double precision,
    min_f double precision,
    max_f double precision,
    avg_thvd1 double precision,
    max_thvd1 double precision,
    avg_thvd2 double precision,
    max_thvd2 double precision,
    avg_thvd3 double precision,
    max_thvd3 double precision
);


--
-- Name: _hyper_11_21_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_11_21_chunk (
    CONSTRAINT constraint_21 CHECK (((bucket >= '2026-08-25 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-09-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_11);


--
-- Name: _hyper_11_22_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_11_22_chunk (
    CONSTRAINT constraint_22 CHECK (((bucket >= '2026-08-15 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-08-25 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_11);


--
-- Name: _hyper_11_23_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_11_23_chunk (
    CONSTRAINT constraint_23 CHECK (((bucket >= '2026-08-05 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-08-15 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_11);


--
-- Name: _hyper_11_34_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_11_34_chunk (
    CONSTRAINT constraint_34 CHECK (((bucket >= '2026-09-04 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-09-14 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_11);


--
-- Name: _hyper_1_15_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_15_chunk (
    CONSTRAINT constraint_15 CHECK ((("time" >= '2026-08-28 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-29 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_1_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_1_chunk (
    CONSTRAINT constraint_1 CHECK ((("time" >= '2026-08-06 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-13 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_1_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_1_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    v1 _timescaledb_internal.compressed_data,
    i1 _timescaledb_internal.compressed_data,
    p1 _timescaledb_internal.compressed_data,
    f1 _timescaledb_internal.compressed_data,
    v2 _timescaledb_internal.compressed_data,
    i2 _timescaledb_internal.compressed_data,
    p2 _timescaledb_internal.compressed_data,
    v3 _timescaledb_internal.compressed_data,
    i3 _timescaledb_internal.compressed_data,
    p3 _timescaledb_internal.compressed_data,
    vl12 _timescaledb_internal.compressed_data,
    vl23 _timescaledb_internal.compressed_data,
    vl31 _timescaledb_internal.compressed_data,
    q1 _timescaledb_internal.compressed_data,
    q2 _timescaledb_internal.compressed_data,
    q3 _timescaledb_internal.compressed_data,
    s1 _timescaledb_internal.compressed_data,
    s2 _timescaledb_internal.compressed_data,
    s3 _timescaledb_internal.compressed_data,
    f2 _timescaledb_internal.compressed_data,
    f3 _timescaledb_internal.compressed_data,
    v_neutral _timescaledb_internal.compressed_data,
    i_neutral _timescaledb_internal.compressed_data,
    cos1 _timescaledb_internal.compressed_data,
    cos2 _timescaledb_internal.compressed_data,
    cos3 _timescaledb_internal.compressed_data,
    pf1 _timescaledb_internal.compressed_data,
    pf2 _timescaledb_internal.compressed_data,
    pf3 _timescaledb_internal.compressed_data,
    thd1 _timescaledb_internal.compressed_data,
    thd2 _timescaledb_internal.compressed_data,
    thd3 _timescaledb_internal.compressed_data,
    thvd1 _timescaledb_internal.compressed_data,
    thvd2 _timescaledb_internal.compressed_data,
    thvd3 _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN v1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN i1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN p1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN f1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN v2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN i2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN p2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN v3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN i3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN p3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN vl12 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN vl23 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN vl31 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN q1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN q2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN q3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN s1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN s2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN s3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN f2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN f3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN v_neutral SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN i_neutral SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN cos1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN cos2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN cos3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN pf1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN pf2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN pf3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN thd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN thd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN thd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN thvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN thvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk_compressed ALTER COLUMN thvd3 SET STATISTICS 0;


--
-- Name: _hyper_1_24_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_24_chunk (
    CONSTRAINT constraint_24 CHECK ((("time" >= '2026-08-31 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-01 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_25_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_25_chunk (
    CONSTRAINT constraint_25 CHECK ((("time" >= '2026-09-01 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-02 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_26_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_26_chunk (
    CONSTRAINT constraint_26 CHECK ((("time" >= '2026-09-02 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_27_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_27_chunk (
    CONSTRAINT constraint_27 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_2_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_2_chunk (
    CONSTRAINT constraint_2 CHECK ((("time" >= '2026-08-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_2_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_2_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    v1 _timescaledb_internal.compressed_data,
    i1 _timescaledb_internal.compressed_data,
    p1 _timescaledb_internal.compressed_data,
    f1 _timescaledb_internal.compressed_data,
    v2 _timescaledb_internal.compressed_data,
    i2 _timescaledb_internal.compressed_data,
    p2 _timescaledb_internal.compressed_data,
    v3 _timescaledb_internal.compressed_data,
    i3 _timescaledb_internal.compressed_data,
    p3 _timescaledb_internal.compressed_data,
    vl12 _timescaledb_internal.compressed_data,
    vl23 _timescaledb_internal.compressed_data,
    vl31 _timescaledb_internal.compressed_data,
    q1 _timescaledb_internal.compressed_data,
    q2 _timescaledb_internal.compressed_data,
    q3 _timescaledb_internal.compressed_data,
    s1 _timescaledb_internal.compressed_data,
    s2 _timescaledb_internal.compressed_data,
    s3 _timescaledb_internal.compressed_data,
    f2 _timescaledb_internal.compressed_data,
    f3 _timescaledb_internal.compressed_data,
    v_neutral _timescaledb_internal.compressed_data,
    i_neutral _timescaledb_internal.compressed_data,
    cos1 _timescaledb_internal.compressed_data,
    cos2 _timescaledb_internal.compressed_data,
    cos3 _timescaledb_internal.compressed_data,
    pf1 _timescaledb_internal.compressed_data,
    pf2 _timescaledb_internal.compressed_data,
    pf3 _timescaledb_internal.compressed_data,
    thd1 _timescaledb_internal.compressed_data,
    thd2 _timescaledb_internal.compressed_data,
    thd3 _timescaledb_internal.compressed_data,
    thvd1 _timescaledb_internal.compressed_data,
    thvd2 _timescaledb_internal.compressed_data,
    thvd3 _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN v1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN i1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN p1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN f1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN v2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN i2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN p2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN v3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN i3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN p3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN vl12 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN vl23 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN vl31 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN q1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN q2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN q3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN s1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN s2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN s3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN f2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN f3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN v_neutral SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN i_neutral SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN cos1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN cos2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN cos3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN pf1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN pf2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN pf3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN thd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN thd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN thd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN thvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN thvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk_compressed ALTER COLUMN thvd3 SET STATISTICS 0;


--
-- Name: _hyper_1_33_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_33_chunk (
    CONSTRAINT constraint_33 CHECK ((("time" >= '2026-09-04 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-05 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_5_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_5_chunk (
    CONSTRAINT constraint_5 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.measurements);


--
-- Name: _hyper_1_5_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_5_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    v1 _timescaledb_internal.compressed_data,
    i1 _timescaledb_internal.compressed_data,
    p1 _timescaledb_internal.compressed_data,
    f1 _timescaledb_internal.compressed_data,
    v2 _timescaledb_internal.compressed_data,
    i2 _timescaledb_internal.compressed_data,
    p2 _timescaledb_internal.compressed_data,
    v3 _timescaledb_internal.compressed_data,
    i3 _timescaledb_internal.compressed_data,
    p3 _timescaledb_internal.compressed_data,
    vl12 _timescaledb_internal.compressed_data,
    vl23 _timescaledb_internal.compressed_data,
    vl31 _timescaledb_internal.compressed_data,
    q1 _timescaledb_internal.compressed_data,
    q2 _timescaledb_internal.compressed_data,
    q3 _timescaledb_internal.compressed_data,
    s1 _timescaledb_internal.compressed_data,
    s2 _timescaledb_internal.compressed_data,
    s3 _timescaledb_internal.compressed_data,
    f2 _timescaledb_internal.compressed_data,
    f3 _timescaledb_internal.compressed_data,
    v_neutral _timescaledb_internal.compressed_data,
    i_neutral _timescaledb_internal.compressed_data,
    cos1 _timescaledb_internal.compressed_data,
    cos2 _timescaledb_internal.compressed_data,
    cos3 _timescaledb_internal.compressed_data,
    pf1 _timescaledb_internal.compressed_data,
    pf2 _timescaledb_internal.compressed_data,
    pf3 _timescaledb_internal.compressed_data,
    thd1 _timescaledb_internal.compressed_data,
    thd2 _timescaledb_internal.compressed_data,
    thd3 _timescaledb_internal.compressed_data,
    thvd1 _timescaledb_internal.compressed_data,
    thvd2 _timescaledb_internal.compressed_data,
    thvd3 _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN v1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN i1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN p1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN f1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN v2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN i2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN p2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN v3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN i3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN p3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN vl12 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN vl23 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN vl31 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN q1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN q2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN q3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN s1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN s2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN s3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN f2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN f3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN v_neutral SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN i_neutral SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN cos1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN cos2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN cos3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN pf1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN pf2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN pf3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN thd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN thd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN thd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN thvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN thvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk_compressed ALTER COLUMN thvd3 SET STATISTICS 0;


--
-- Name: _hyper_3_16_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_3_16_chunk (
    CONSTRAINT constraint_16 CHECK ((("time" >= '2026-08-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_energy);


--
-- Name: _hyper_3_28_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_3_28_chunk (
    CONSTRAINT constraint_28 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_energy);


--
-- Name: _hyper_3_3_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_3_3_chunk (
    CONSTRAINT constraint_3 CHECK ((("time" >= '2026-08-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_energy);


--
-- Name: _hyper_3_3_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_3_3_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    active_wh_tuketim _timescaledb_internal.compressed_data,
    inductive_varh_tuketim _timescaledb_internal.compressed_data,
    capacitive_varh_tuketim _timescaledb_internal.compressed_data,
    active_wh_uretim _timescaledb_internal.compressed_data,
    inductive_varh_uretim _timescaledb_internal.compressed_data,
    capacitive_varh_uretim _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN active_wh_tuketim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN inductive_varh_tuketim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN capacitive_varh_tuketim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN active_wh_uretim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN inductive_varh_uretim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk_compressed ALTER COLUMN capacitive_varh_uretim SET STATISTICS 0;


--
-- Name: _hyper_3_4_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_3_4_chunk (
    CONSTRAINT constraint_4 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_energy);


--
-- Name: _hyper_3_4_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_3_4_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    active_wh_tuketim _timescaledb_internal.compressed_data,
    inductive_varh_tuketim _timescaledb_internal.compressed_data,
    capacitive_varh_tuketim _timescaledb_internal.compressed_data,
    active_wh_uretim _timescaledb_internal.compressed_data,
    inductive_varh_uretim _timescaledb_internal.compressed_data,
    capacitive_varh_uretim _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN active_wh_tuketim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN inductive_varh_tuketim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN capacitive_varh_tuketim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN active_wh_uretim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN inductive_varh_uretim SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk_compressed ALTER COLUMN capacitive_varh_uretim SET STATISTICS 0;


--
-- Name: device_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_stats (
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    device_id text NOT NULL,
    p_active_imp double precision,
    p_reactive_imp double precision,
    p_inductive_imp double precision,
    p_capacitive_imp double precision,
    p_apparent_imp double precision,
    p_active_exp double precision,
    p_reactive_exp double precision,
    p_inductive_exp double precision,
    p_capacitive_exp double precision,
    p_apparent_exp double precision,
    avg_current_imp double precision,
    avg_active_power_imp double precision,
    avg_cos_imp double precision,
    avg_tan_imp double precision,
    avg_pf_imp double precision,
    avg_current_exp double precision,
    avg_active_power_exp double precision,
    avg_cos_exp double precision,
    avg_tan_exp double precision,
    avg_pf_exp double precision,
    avg_voltage_ln double precision,
    avg_voltage_ll double precision,
    avg_frequency double precision,
    avg_thid double precision,
    avg_thvd double precision
);


--
-- Name: _hyper_4_17_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_4_17_chunk (
    CONSTRAINT constraint_17 CHECK ((("time" >= '2026-08-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_stats);


--
-- Name: _hyper_4_29_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_4_29_chunk (
    CONSTRAINT constraint_29 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_stats);


--
-- Name: _hyper_4_6_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_4_6_chunk (
    CONSTRAINT constraint_6 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_stats);


--
-- Name: _hyper_4_6_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_4_6_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    p_active_imp _timescaledb_internal.compressed_data,
    p_reactive_imp _timescaledb_internal.compressed_data,
    p_inductive_imp _timescaledb_internal.compressed_data,
    p_capacitive_imp _timescaledb_internal.compressed_data,
    p_apparent_imp _timescaledb_internal.compressed_data,
    p_active_exp _timescaledb_internal.compressed_data,
    p_reactive_exp _timescaledb_internal.compressed_data,
    p_inductive_exp _timescaledb_internal.compressed_data,
    p_capacitive_exp _timescaledb_internal.compressed_data,
    p_apparent_exp _timescaledb_internal.compressed_data,
    avg_current_imp _timescaledb_internal.compressed_data,
    avg_active_power_imp _timescaledb_internal.compressed_data,
    avg_cos_imp _timescaledb_internal.compressed_data,
    avg_tan_imp _timescaledb_internal.compressed_data,
    avg_pf_imp _timescaledb_internal.compressed_data,
    avg_current_exp _timescaledb_internal.compressed_data,
    avg_active_power_exp _timescaledb_internal.compressed_data,
    avg_cos_exp _timescaledb_internal.compressed_data,
    avg_tan_exp _timescaledb_internal.compressed_data,
    avg_pf_exp _timescaledb_internal.compressed_data,
    avg_voltage_ln _timescaledb_internal.compressed_data,
    avg_voltage_ll _timescaledb_internal.compressed_data,
    avg_frequency _timescaledb_internal.compressed_data,
    avg_thid _timescaledb_internal.compressed_data,
    avg_thvd _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_active_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_reactive_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_inductive_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_capacitive_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_apparent_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_active_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_reactive_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_inductive_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_capacitive_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN p_apparent_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_current_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_active_power_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_cos_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_tan_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_pf_imp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_current_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_active_power_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_cos_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_tan_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_pf_exp SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_voltage_ln SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_voltage_ll SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_frequency SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_thid SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk_compressed ALTER COLUMN avg_thvd SET STATISTICS 0;


--
-- Name: device_peaks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_peaks (
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    device_id text NOT NULL,
    direction text NOT NULL,
    min_vln1 double precision,
    min_vln2 double precision,
    min_vln3 double precision,
    min_vn double precision,
    max_vln1 double precision,
    max_vln2 double precision,
    max_vln3 double precision,
    max_vn double precision,
    min_vll1 double precision,
    min_vll2 double precision,
    min_vll3 double precision,
    max_vll1 double precision,
    max_vll2 double precision,
    max_vll3 double precision,
    min_i1 double precision,
    min_i2 double precision,
    min_i3 double precision,
    min_in double precision,
    max_i1 double precision,
    max_i2 double precision,
    max_i3 double precision,
    max_in double precision,
    min_p1 double precision,
    min_p2 double precision,
    min_p3 double precision,
    max_p1 double precision,
    max_p2 double precision,
    max_p3 double precision,
    min_q1 double precision,
    min_q2 double precision,
    min_q3 double precision,
    max_q1 double precision,
    max_q2 double precision,
    max_q3 double precision,
    min_s1 double precision,
    min_s2 double precision,
    min_s3 double precision,
    max_s1 double precision,
    max_s2 double precision,
    max_s3 double precision,
    min_thvd1 double precision,
    min_thvd2 double precision,
    min_thvd3 double precision,
    max_thvd1 double precision,
    max_thvd2 double precision,
    max_thvd3 double precision,
    min_thid1 double precision,
    min_thid2 double precision,
    min_thid3 double precision,
    max_thid1 double precision,
    max_thid2 double precision,
    max_thid3 double precision,
    min_freq double precision,
    max_freq double precision,
    min_v_unbal double precision,
    max_v_unbal double precision,
    min_i_unbal double precision,
    max_i_unbal double precision
);


--
-- Name: _hyper_5_18_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_5_18_chunk (
    CONSTRAINT constraint_18 CHECK ((("time" >= '2026-08-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_peaks);


--
-- Name: _hyper_5_30_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_5_30_chunk (
    CONSTRAINT constraint_30 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_peaks);


--
-- Name: _hyper_5_7_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_5_7_chunk (
    CONSTRAINT constraint_7 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_peaks);


--
-- Name: _hyper_5_7_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_5_7_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    direction text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    min_vln1 _timescaledb_internal.compressed_data,
    min_vln2 _timescaledb_internal.compressed_data,
    min_vln3 _timescaledb_internal.compressed_data,
    min_vn _timescaledb_internal.compressed_data,
    max_vln1 _timescaledb_internal.compressed_data,
    max_vln2 _timescaledb_internal.compressed_data,
    max_vln3 _timescaledb_internal.compressed_data,
    max_vn _timescaledb_internal.compressed_data,
    min_vll1 _timescaledb_internal.compressed_data,
    min_vll2 _timescaledb_internal.compressed_data,
    min_vll3 _timescaledb_internal.compressed_data,
    max_vll1 _timescaledb_internal.compressed_data,
    max_vll2 _timescaledb_internal.compressed_data,
    max_vll3 _timescaledb_internal.compressed_data,
    min_i1 _timescaledb_internal.compressed_data,
    min_i2 _timescaledb_internal.compressed_data,
    min_i3 _timescaledb_internal.compressed_data,
    min_in _timescaledb_internal.compressed_data,
    max_i1 _timescaledb_internal.compressed_data,
    max_i2 _timescaledb_internal.compressed_data,
    max_i3 _timescaledb_internal.compressed_data,
    max_in _timescaledb_internal.compressed_data,
    min_p1 _timescaledb_internal.compressed_data,
    min_p2 _timescaledb_internal.compressed_data,
    min_p3 _timescaledb_internal.compressed_data,
    max_p1 _timescaledb_internal.compressed_data,
    max_p2 _timescaledb_internal.compressed_data,
    max_p3 _timescaledb_internal.compressed_data,
    min_q1 _timescaledb_internal.compressed_data,
    min_q2 _timescaledb_internal.compressed_data,
    min_q3 _timescaledb_internal.compressed_data,
    max_q1 _timescaledb_internal.compressed_data,
    max_q2 _timescaledb_internal.compressed_data,
    max_q3 _timescaledb_internal.compressed_data,
    min_s1 _timescaledb_internal.compressed_data,
    min_s2 _timescaledb_internal.compressed_data,
    min_s3 _timescaledb_internal.compressed_data,
    max_s1 _timescaledb_internal.compressed_data,
    max_s2 _timescaledb_internal.compressed_data,
    max_s3 _timescaledb_internal.compressed_data,
    min_thvd1 _timescaledb_internal.compressed_data,
    min_thvd2 _timescaledb_internal.compressed_data,
    min_thvd3 _timescaledb_internal.compressed_data,
    max_thvd1 _timescaledb_internal.compressed_data,
    max_thvd2 _timescaledb_internal.compressed_data,
    max_thvd3 _timescaledb_internal.compressed_data,
    min_thid1 _timescaledb_internal.compressed_data,
    min_thid2 _timescaledb_internal.compressed_data,
    min_thid3 _timescaledb_internal.compressed_data,
    max_thid1 _timescaledb_internal.compressed_data,
    max_thid2 _timescaledb_internal.compressed_data,
    max_thid3 _timescaledb_internal.compressed_data,
    min_freq _timescaledb_internal.compressed_data,
    max_freq _timescaledb_internal.compressed_data,
    min_v_unbal _timescaledb_internal.compressed_data,
    max_v_unbal _timescaledb_internal.compressed_data,
    min_i_unbal _timescaledb_internal.compressed_data,
    max_i_unbal _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN direction SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vln1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vln2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vln3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vn SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vln1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vln2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vln3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vn SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vll1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vll2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_vll3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vll1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vll2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_vll3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_i1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_i2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_i3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_in SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_i1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_i2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_i3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_in SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_p1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_p2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_p3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_p1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_p2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_p3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_q1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_q2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_q3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_q1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_q2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_q3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_s1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_s2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_s3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_s1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_s2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_s3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_thvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_thvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_thvd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_thvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_thvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_thvd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_thid1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_thid2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_thid3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_thid1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_thid2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_thid3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_freq SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_freq SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_v_unbal SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_v_unbal SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN min_i_unbal SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk_compressed ALTER COLUMN max_i_unbal SET STATISTICS 0;


--
-- Name: device_demand; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_demand (
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    device_id text NOT NULL,
    direction text NOT NULL,
    max_dv1 double precision,
    max_dv2 double precision,
    max_dv3 double precision,
    min_dv1 double precision,
    min_dv2 double precision,
    min_dv3 double precision,
    max_di1 double precision,
    max_di2 double precision,
    max_di3 double precision,
    min_di1 double precision,
    min_di2 double precision,
    min_di3 double precision,
    max_dp1 double precision,
    max_dp2 double precision,
    max_dp3 double precision,
    min_dp1 double precision,
    min_dp2 double precision,
    min_dp3 double precision,
    max_dq1 double precision,
    max_dq2 double precision,
    max_dq3 double precision,
    min_dq1 double precision,
    min_dq2 double precision,
    min_dq3 double precision,
    max_ds1 double precision,
    max_ds2 double precision,
    max_ds3 double precision,
    min_ds1 double precision,
    min_ds2 double precision,
    min_ds3 double precision,
    max_dthvd1 double precision,
    max_dthvd2 double precision,
    max_dthvd3 double precision,
    min_dthvd1 double precision,
    min_dthvd2 double precision,
    min_dthvd3 double precision,
    max_dthid1 double precision,
    max_dthid2 double precision,
    max_dthid3 double precision,
    min_dthid1 double precision,
    min_dthid2 double precision,
    min_dthid3 double precision
);


--
-- Name: _hyper_6_19_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_6_19_chunk (
    CONSTRAINT constraint_19 CHECK ((("time" >= '2026-08-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_demand);


--
-- Name: _hyper_6_31_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_6_31_chunk (
    CONSTRAINT constraint_31 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_demand);


--
-- Name: _hyper_6_8_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_6_8_chunk (
    CONSTRAINT constraint_8 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_demand);


--
-- Name: _hyper_6_8_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_6_8_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    direction _timescaledb_internal.compressed_data,
    max_dv1 _timescaledb_internal.compressed_data,
    max_dv2 _timescaledb_internal.compressed_data,
    max_dv3 _timescaledb_internal.compressed_data,
    min_dv1 _timescaledb_internal.compressed_data,
    min_dv2 _timescaledb_internal.compressed_data,
    min_dv3 _timescaledb_internal.compressed_data,
    max_di1 _timescaledb_internal.compressed_data,
    max_di2 _timescaledb_internal.compressed_data,
    max_di3 _timescaledb_internal.compressed_data,
    min_di1 _timescaledb_internal.compressed_data,
    min_di2 _timescaledb_internal.compressed_data,
    min_di3 _timescaledb_internal.compressed_data,
    max_dp1 _timescaledb_internal.compressed_data,
    max_dp2 _timescaledb_internal.compressed_data,
    max_dp3 _timescaledb_internal.compressed_data,
    min_dp1 _timescaledb_internal.compressed_data,
    min_dp2 _timescaledb_internal.compressed_data,
    min_dp3 _timescaledb_internal.compressed_data,
    max_dq1 _timescaledb_internal.compressed_data,
    max_dq2 _timescaledb_internal.compressed_data,
    max_dq3 _timescaledb_internal.compressed_data,
    min_dq1 _timescaledb_internal.compressed_data,
    min_dq2 _timescaledb_internal.compressed_data,
    min_dq3 _timescaledb_internal.compressed_data,
    max_ds1 _timescaledb_internal.compressed_data,
    max_ds2 _timescaledb_internal.compressed_data,
    max_ds3 _timescaledb_internal.compressed_data,
    min_ds1 _timescaledb_internal.compressed_data,
    min_ds2 _timescaledb_internal.compressed_data,
    min_ds3 _timescaledb_internal.compressed_data,
    max_dthvd1 _timescaledb_internal.compressed_data,
    max_dthvd2 _timescaledb_internal.compressed_data,
    max_dthvd3 _timescaledb_internal.compressed_data,
    min_dthvd1 _timescaledb_internal.compressed_data,
    min_dthvd2 _timescaledb_internal.compressed_data,
    min_dthvd3 _timescaledb_internal.compressed_data,
    max_dthid1 _timescaledb_internal.compressed_data,
    max_dthid2 _timescaledb_internal.compressed_data,
    max_dthid3 _timescaledb_internal.compressed_data,
    min_dthid1 _timescaledb_internal.compressed_data,
    min_dthid2 _timescaledb_internal.compressed_data,
    min_dthid3 _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN direction SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN direction SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dv1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dv2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dv3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dv1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dv2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dv3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_di1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_di2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_di3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_di1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_di2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_di3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dp1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dp2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dp3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dp1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dp2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dp3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dq1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dq2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dq3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dq1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dq2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dq3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_ds1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_ds2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_ds3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_ds1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_ds2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_ds3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dthvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dthvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dthvd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dthvd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dthvd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dthvd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dthid1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dthid2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN max_dthid3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dthid1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dthid2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk_compressed ALTER COLUMN min_dthid3 SET STATISTICS 0;


--
-- Name: device_harmonics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_harmonics (
    "time" timestamp with time zone DEFAULT now() NOT NULL,
    device_id text NOT NULL,
    signal_type text NOT NULL,
    thd1 double precision,
    thd2 double precision,
    thd3 double precision,
    h3_l1 double precision,
    h3_l2 double precision,
    h3_l3 double precision,
    h5_l1 double precision,
    h5_l2 double precision,
    h5_l3 double precision,
    h7_l1 double precision,
    h7_l2 double precision,
    h7_l3 double precision,
    h9_l1 double precision,
    h9_l2 double precision,
    h9_l3 double precision,
    h11_l1 double precision,
    h11_l2 double precision,
    h11_l3 double precision,
    h13_l1 double precision,
    h13_l2 double precision,
    h13_l3 double precision,
    h15_l1 double precision,
    h15_l2 double precision,
    h15_l3 double precision,
    h17_l1 double precision,
    h17_l2 double precision,
    h17_l3 double precision,
    h19_l1 double precision,
    h19_l2 double precision,
    h19_l3 double precision,
    h21_l1 double precision,
    h21_l2 double precision,
    h21_l3 double precision,
    h23_l1 double precision,
    h23_l2 double precision,
    h23_l3 double precision,
    h25_l1 double precision,
    h25_l2 double precision,
    h25_l3 double precision,
    h27_l1 double precision,
    h27_l2 double precision,
    h27_l3 double precision,
    h29_l1 double precision,
    h29_l2 double precision,
    h29_l3 double precision,
    h31_l1 double precision,
    h31_l2 double precision,
    h31_l3 double precision
);


--
-- Name: _hyper_7_20_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_7_20_chunk (
    CONSTRAINT constraint_20 CHECK ((("time" >= '2026-08-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_harmonics);


--
-- Name: _hyper_7_32_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_7_32_chunk (
    CONSTRAINT constraint_32 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_harmonics);


--
-- Name: _hyper_7_9_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_7_9_chunk (
    CONSTRAINT constraint_9 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.device_harmonics);


--
-- Name: _hyper_7_9_chunk_compressed; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_7_9_chunk_compressed (
    _ts_meta_count integer,
    device_id text,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    _ts_meta_v2_first_time timestamp with time zone,
    _ts_meta_v2_last_time timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    signal_type _timescaledb_internal.compressed_data,
    thd1 _timescaledb_internal.compressed_data,
    thd2 _timescaledb_internal.compressed_data,
    thd3 _timescaledb_internal.compressed_data,
    h3_l1 _timescaledb_internal.compressed_data,
    h3_l2 _timescaledb_internal.compressed_data,
    h3_l3 _timescaledb_internal.compressed_data,
    h5_l1 _timescaledb_internal.compressed_data,
    h5_l2 _timescaledb_internal.compressed_data,
    h5_l3 _timescaledb_internal.compressed_data,
    h7_l1 _timescaledb_internal.compressed_data,
    h7_l2 _timescaledb_internal.compressed_data,
    h7_l3 _timescaledb_internal.compressed_data,
    h9_l1 _timescaledb_internal.compressed_data,
    h9_l2 _timescaledb_internal.compressed_data,
    h9_l3 _timescaledb_internal.compressed_data,
    h11_l1 _timescaledb_internal.compressed_data,
    h11_l2 _timescaledb_internal.compressed_data,
    h11_l3 _timescaledb_internal.compressed_data,
    h13_l1 _timescaledb_internal.compressed_data,
    h13_l2 _timescaledb_internal.compressed_data,
    h13_l3 _timescaledb_internal.compressed_data,
    h15_l1 _timescaledb_internal.compressed_data,
    h15_l2 _timescaledb_internal.compressed_data,
    h15_l3 _timescaledb_internal.compressed_data,
    h17_l1 _timescaledb_internal.compressed_data,
    h17_l2 _timescaledb_internal.compressed_data,
    h17_l3 _timescaledb_internal.compressed_data,
    h19_l1 _timescaledb_internal.compressed_data,
    h19_l2 _timescaledb_internal.compressed_data,
    h19_l3 _timescaledb_internal.compressed_data,
    h21_l1 _timescaledb_internal.compressed_data,
    h21_l2 _timescaledb_internal.compressed_data,
    h21_l3 _timescaledb_internal.compressed_data,
    h23_l1 _timescaledb_internal.compressed_data,
    h23_l2 _timescaledb_internal.compressed_data,
    h23_l3 _timescaledb_internal.compressed_data,
    h25_l1 _timescaledb_internal.compressed_data,
    h25_l2 _timescaledb_internal.compressed_data,
    h25_l3 _timescaledb_internal.compressed_data,
    h27_l1 _timescaledb_internal.compressed_data,
    h27_l2 _timescaledb_internal.compressed_data,
    h27_l3 _timescaledb_internal.compressed_data,
    h29_l1 _timescaledb_internal.compressed_data,
    h29_l2 _timescaledb_internal.compressed_data,
    h29_l3 _timescaledb_internal.compressed_data,
    h31_l1 _timescaledb_internal.compressed_data,
    h31_l2 _timescaledb_internal.compressed_data,
    h31_l3 _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN device_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN _ts_meta_v2_first_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN _ts_meta_v2_last_time SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN signal_type SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN signal_type SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN thd1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN thd2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN thd3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h3_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h3_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h3_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h5_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h5_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h5_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h7_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h7_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h7_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h9_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h9_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h9_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h11_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h11_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h11_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h13_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h13_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h13_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h15_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h15_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h15_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h17_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h17_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h17_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h19_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h19_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h19_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h21_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h21_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h21_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h23_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h23_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h23_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h25_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h25_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h25_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h27_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h27_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h27_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h29_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h29_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h29_l3 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h31_l1 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h31_l2 SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk_compressed ALTER COLUMN h31_l3 SET STATISTICS 0;


--
-- Name: _materialized_hypertable_9; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_9 (
    device_id text,
    bucket timestamp with time zone NOT NULL,
    sample_count bigint,
    avg_total_p double precision,
    max_total_p double precision,
    avg_total_q double precision,
    avg_total_s double precision,
    avg_v1 double precision,
    min_v1 double precision,
    max_v1 double precision,
    avg_v2 double precision,
    min_v2 double precision,
    max_v2 double precision,
    avg_v3 double precision,
    min_v3 double precision,
    max_v3 double precision,
    avg_i1 double precision,
    max_i1 double precision,
    avg_i2 double precision,
    max_i2 double precision,
    avg_i3 double precision,
    max_i3 double precision,
    avg_i_neutral double precision,
    max_i_neutral double precision,
    avg_f double precision,
    min_f double precision,
    max_f double precision,
    avg_pf1 double precision,
    avg_pf2 double precision,
    avg_pf3 double precision,
    avg_thd1 double precision,
    max_thd1 double precision,
    avg_thd2 double precision,
    max_thd2 double precision,
    avg_thd3 double precision,
    max_thd3 double precision,
    avg_thvd1 double precision,
    max_thvd1 double precision,
    avg_thvd2 double precision,
    max_thvd2 double precision,
    avg_thvd3 double precision,
    max_thvd3 double precision
);


--
-- Name: _hyper_9_11_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_9_11_chunk (
    CONSTRAINT constraint_11 CHECK (((bucket >= '2026-08-25 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-09-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_9);


--
-- Name: _hyper_9_12_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_9_12_chunk (
    CONSTRAINT constraint_12 CHECK (((bucket >= '2026-08-15 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-08-25 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_9);


--
-- Name: _hyper_9_13_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_9_13_chunk (
    CONSTRAINT constraint_13 CHECK (((bucket >= '2026-08-05 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-08-15 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_9);


--
-- Name: _hyper_9_35_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_9_35_chunk (
    CONSTRAINT constraint_35 CHECK (((bucket >= '2026-09-04 00:00:00+00'::timestamp with time zone) AND (bucket < '2026-09-14 00:00:00+00'::timestamp with time zone)))
)
INHERITS (_timescaledb_internal._materialized_hypertable_9);


--
-- Name: _partial_view_10; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._partial_view_10 AS
 SELECT device_id,
    public.time_bucket('01:00:00'::interval, "time") AS bucket,
    public.last("time", "time") AS reading_time,
    public.first(active_wh_tuketim, "time") AS first_active_tuketim,
    public.last(active_wh_tuketim, "time") AS active_wh_tuketim,
    max(active_wh_tuketim) AS max_active_tuketim,
    public.first(inductive_varh_tuketim, "time") AS first_inductive_tuketim,
    public.last(inductive_varh_tuketim, "time") AS inductive_varh_tuketim,
    max(inductive_varh_tuketim) AS max_inductive_tuketim,
    public.first(capacitive_varh_tuketim, "time") AS first_capacitive_tuketim,
    public.last(capacitive_varh_tuketim, "time") AS capacitive_varh_tuketim,
    max(capacitive_varh_tuketim) AS max_capacitive_tuketim,
    public.first(active_wh_uretim, "time") AS first_active_uretim,
    public.last(active_wh_uretim, "time") AS active_wh_uretim,
    max(active_wh_uretim) AS max_active_uretim,
    public.first(inductive_varh_uretim, "time") AS first_inductive_uretim,
    public.last(inductive_varh_uretim, "time") AS inductive_varh_uretim,
    max(inductive_varh_uretim) AS max_inductive_uretim,
    public.first(capacitive_varh_uretim, "time") AS first_capacitive_uretim,
    public.last(capacitive_varh_uretim, "time") AS capacitive_varh_uretim,
    max(capacitive_varh_uretim) AS max_capacitive_uretim
   FROM public.device_energy
  GROUP BY device_id, (public.time_bucket('01:00:00'::interval, "time"));


--
-- Name: _partial_view_11; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._partial_view_11 AS
 SELECT device_id,
    public.time_bucket('00:10:00'::interval, "time") AS bucket,
    count(*) AS sample_count,
    avg(v1) AS avg_v1,
    min(v1) AS min_v1,
    max(v1) AS max_v1,
    avg(v2) AS avg_v2,
    min(v2) AS min_v2,
    max(v2) AS max_v2,
    avg(v3) AS avg_v3,
    min(v3) AS min_v3,
    max(v3) AS max_v3,
    avg(f1) AS avg_f,
    min(f1) AS min_f,
    max(f1) AS max_f,
    avg(thvd1) AS avg_thvd1,
    max(thvd1) AS max_thvd1,
    avg(thvd2) AS avg_thvd2,
    max(thvd2) AS max_thvd2,
    avg(thvd3) AS avg_thvd3,
    max(thvd3) AS max_thvd3
   FROM public.measurements
  GROUP BY device_id, (public.time_bucket('00:10:00'::interval, "time"));


--
-- Name: _partial_view_9; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._partial_view_9 AS
 SELECT device_id,
    public.time_bucket('00:15:00'::interval, "time") AS bucket,
    count(*) AS sample_count,
    avg(((COALESCE(p1, (0)::double precision) + COALESCE(p2, (0)::double precision)) + COALESCE(p3, (0)::double precision))) AS avg_total_p,
    max(((COALESCE(p1, (0)::double precision) + COALESCE(p2, (0)::double precision)) + COALESCE(p3, (0)::double precision))) AS max_total_p,
    avg(((COALESCE(q1, (0)::double precision) + COALESCE(q2, (0)::double precision)) + COALESCE(q3, (0)::double precision))) AS avg_total_q,
    avg(((COALESCE(s1, (0)::double precision) + COALESCE(s2, (0)::double precision)) + COALESCE(s3, (0)::double precision))) AS avg_total_s,
    avg(v1) AS avg_v1,
    min(v1) AS min_v1,
    max(v1) AS max_v1,
    avg(v2) AS avg_v2,
    min(v2) AS min_v2,
    max(v2) AS max_v2,
    avg(v3) AS avg_v3,
    min(v3) AS min_v3,
    max(v3) AS max_v3,
    avg(i1) AS avg_i1,
    max(i1) AS max_i1,
    avg(i2) AS avg_i2,
    max(i2) AS max_i2,
    avg(i3) AS avg_i3,
    max(i3) AS max_i3,
    avg(i_neutral) AS avg_i_neutral,
    max(i_neutral) AS max_i_neutral,
    avg(f1) AS avg_f,
    min(f1) AS min_f,
    max(f1) AS max_f,
    avg(pf1) AS avg_pf1,
    avg(pf2) AS avg_pf2,
    avg(pf3) AS avg_pf3,
    avg(thd1) AS avg_thd1,
    max(thd1) AS max_thd1,
    avg(thd2) AS avg_thd2,
    max(thd2) AS max_thd2,
    avg(thd3) AS avg_thd3,
    max(thd3) AS max_thd3,
    avg(thvd1) AS avg_thvd1,
    max(thvd1) AS max_thvd1,
    avg(thvd2) AS avg_thvd2,
    max(thvd2) AS max_thvd2,
    avg(thvd3) AS avg_thvd3,
    max(thvd3) AS max_thvd3
   FROM public.measurements
  GROUP BY device_id, (public.time_bucket('00:15:00'::interval, "time"));


--
-- Name: alarm_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alarm_events (
    id integer NOT NULL,
    rule_id integer,
    device_id text NOT NULL,
    triggered_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    trigger_value double precision,
    message text NOT NULL
);


--
-- Name: alarm_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alarm_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alarm_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alarm_events_id_seq OWNED BY public.alarm_events.id;


--
-- Name: alarm_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alarm_rules (
    id integer NOT NULL,
    device_id text NOT NULL,
    metric text NOT NULL,
    phase text DEFAULT 'any'::text NOT NULL,
    condition text NOT NULL,
    threshold double precision,
    offline_minutes integer,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT false NOT NULL,
    last_triggered_at timestamp with time zone,
    offline_stage integer DEFAULT 0 NOT NULL
);


--
-- Name: alarm_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alarm_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alarm_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alarm_rules_id_seq OWNED BY public.alarm_rules.id;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    actor text,
    organization_id integer,
    action text NOT NULL,
    entity_type text,
    entity_id text,
    detail jsonb,
    ip text
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: deletion_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deletion_requests (
    id bigint NOT NULL,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    user_hash text NOT NULL,
    note text
);


--
-- Name: deletion_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deletion_requests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: deletion_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deletion_requests_id_seq OWNED BY public.deletion_requests.id;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id integer NOT NULL,
    facility_id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: departments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departments_id_seq OWNED BY public.departments.id;


--
-- Name: device_energy_hourly; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.device_energy_hourly AS
 SELECT _materialized_hypertable_10.device_id,
    _materialized_hypertable_10.bucket,
    _materialized_hypertable_10.reading_time,
    _materialized_hypertable_10.first_active_tuketim,
    _materialized_hypertable_10.active_wh_tuketim,
    _materialized_hypertable_10.max_active_tuketim,
    _materialized_hypertable_10.first_inductive_tuketim,
    _materialized_hypertable_10.inductive_varh_tuketim,
    _materialized_hypertable_10.max_inductive_tuketim,
    _materialized_hypertable_10.first_capacitive_tuketim,
    _materialized_hypertable_10.capacitive_varh_tuketim,
    _materialized_hypertable_10.max_capacitive_tuketim,
    _materialized_hypertable_10.first_active_uretim,
    _materialized_hypertable_10.active_wh_uretim,
    _materialized_hypertable_10.max_active_uretim,
    _materialized_hypertable_10.first_inductive_uretim,
    _materialized_hypertable_10.inductive_varh_uretim,
    _materialized_hypertable_10.max_inductive_uretim,
    _materialized_hypertable_10.first_capacitive_uretim,
    _materialized_hypertable_10.capacitive_varh_uretim,
    _materialized_hypertable_10.max_capacitive_uretim
   FROM _timescaledb_internal._materialized_hypertable_10
  WHERE (_materialized_hypertable_10.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(10)), '-infinity'::timestamp with time zone))
UNION ALL
 SELECT device_energy.device_id,
    public.time_bucket('01:00:00'::interval, device_energy."time") AS bucket,
    public.last(device_energy."time", device_energy."time") AS reading_time,
    public.first(device_energy.active_wh_tuketim, device_energy."time") AS first_active_tuketim,
    public.last(device_energy.active_wh_tuketim, device_energy."time") AS active_wh_tuketim,
    max(device_energy.active_wh_tuketim) AS max_active_tuketim,
    public.first(device_energy.inductive_varh_tuketim, device_energy."time") AS first_inductive_tuketim,
    public.last(device_energy.inductive_varh_tuketim, device_energy."time") AS inductive_varh_tuketim,
    max(device_energy.inductive_varh_tuketim) AS max_inductive_tuketim,
    public.first(device_energy.capacitive_varh_tuketim, device_energy."time") AS first_capacitive_tuketim,
    public.last(device_energy.capacitive_varh_tuketim, device_energy."time") AS capacitive_varh_tuketim,
    max(device_energy.capacitive_varh_tuketim) AS max_capacitive_tuketim,
    public.first(device_energy.active_wh_uretim, device_energy."time") AS first_active_uretim,
    public.last(device_energy.active_wh_uretim, device_energy."time") AS active_wh_uretim,
    max(device_energy.active_wh_uretim) AS max_active_uretim,
    public.first(device_energy.inductive_varh_uretim, device_energy."time") AS first_inductive_uretim,
    public.last(device_energy.inductive_varh_uretim, device_energy."time") AS inductive_varh_uretim,
    max(device_energy.inductive_varh_uretim) AS max_inductive_uretim,
    public.first(device_energy.capacitive_varh_uretim, device_energy."time") AS first_capacitive_uretim,
    public.last(device_energy.capacitive_varh_uretim, device_energy."time") AS capacitive_varh_uretim,
    max(device_energy.capacitive_varh_uretim) AS max_capacitive_uretim
   FROM public.device_energy
  WHERE (device_energy."time" >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(10)), '-infinity'::timestamp with time zone))
  GROUP BY device_energy.device_id, (public.time_bucket('01:00:00'::interval, device_energy."time"));


--
-- Name: device_info; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_info (
    device_id text NOT NULL,
    seri_no bigint,
    urun_id bigint,
    kart_id bigint,
    sistem_versiyon bigint,
    ulke_kodu bigint,
    firma_kodu bigint,
    besleme_tipi bigint,
    ekran_tipi bigint,
    keyboard_tipi bigint,
    kutu_tipi bigint,
    klemens_tipi bigint,
    connections bigint,
    storage bigint,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: device_mqtt_credentials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_mqtt_credentials (
    device_id text NOT NULL,
    mqtt_username text NOT NULL,
    mqtt_password text NOT NULL,
    applied boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    applied_at timestamp with time zone
);


--
-- Name: device_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_settings (
    device_id text NOT NULL,
    ct_ratio integer,
    updated_at timestamp with time zone,
    fw_version text,
    nominal_voltage numeric DEFAULT 230 NOT NULL
);


--
-- Name: device_tariff; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_tariff (
    device_id text NOT NULL,
    inductive_limit_pct numeric DEFAULT 20 NOT NULL,
    capacitive_limit_pct numeric DEFAULT 15 NOT NULL,
    reactive_price numeric DEFAULT 0 NOT NULL,
    active_price numeric DEFAULT 0 NOT NULL,
    billing_mode text DEFAULT 'full'::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text,
    t1_start smallint DEFAULT 6 NOT NULL,
    t2_start smallint DEFAULT 17 NOT NULL,
    t3_start smallint DEFAULT 22 NOT NULL,
    t1_price numeric DEFAULT 0 NOT NULL,
    t2_price numeric DEFAULT 0 NOT NULL,
    t3_price numeric DEFAULT 0 NOT NULL,
    contract_power_kw numeric,
    demand_price numeric DEFAULT 0 NOT NULL,
    tariff_verified boolean DEFAULT false NOT NULL,
    tariff_source text
);


--
-- Name: devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.devices (
    id integer NOT NULL,
    device_id text NOT NULL,
    name text NOT NULL,
    owner_username text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    facility_id integer,
    department_id integer
);


--
-- Name: devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.devices_id_seq OWNED BY public.devices.id;


--
-- Name: facilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.facilities (
    id integer NOT NULL,
    organization_id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: facilities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.facilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: facilities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.facilities_id_seq OWNED BY public.facilities.id;


--
-- Name: firmware_builds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.firmware_builds (
    id integer NOT NULL,
    device_type text NOT NULL,
    version text NOT NULL,
    filename text NOT NULL,
    sha256 text NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text
);


--
-- Name: firmware_builds_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.firmware_builds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: firmware_builds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.firmware_builds_id_seq OWNED BY public.firmware_builds.id;


--
-- Name: iyzico_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iyzico_payments (
    id integer NOT NULL,
    organization_id integer NOT NULL,
    token text NOT NULL,
    conversation_id text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    months integer NOT NULL,
    device_count_at_purchase integer NOT NULL,
    device_price_at_purchase numeric NOT NULL,
    price numeric NOT NULL,
    iyzico_payment_id text,
    raw_response jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone
);


--
-- Name: iyzico_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iyzico_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iyzico_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iyzico_payments_id_seq OWNED BY public.iyzico_payments.id;


--
-- Name: measurements_10min; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.measurements_10min AS
 SELECT _materialized_hypertable_11.device_id,
    _materialized_hypertable_11.bucket,
    _materialized_hypertable_11.sample_count,
    _materialized_hypertable_11.avg_v1,
    _materialized_hypertable_11.min_v1,
    _materialized_hypertable_11.max_v1,
    _materialized_hypertable_11.avg_v2,
    _materialized_hypertable_11.min_v2,
    _materialized_hypertable_11.max_v2,
    _materialized_hypertable_11.avg_v3,
    _materialized_hypertable_11.min_v3,
    _materialized_hypertable_11.max_v3,
    _materialized_hypertable_11.avg_f,
    _materialized_hypertable_11.min_f,
    _materialized_hypertable_11.max_f,
    _materialized_hypertable_11.avg_thvd1,
    _materialized_hypertable_11.max_thvd1,
    _materialized_hypertable_11.avg_thvd2,
    _materialized_hypertable_11.max_thvd2,
    _materialized_hypertable_11.avg_thvd3,
    _materialized_hypertable_11.max_thvd3
   FROM _timescaledb_internal._materialized_hypertable_11
  WHERE (_materialized_hypertable_11.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(11)), '-infinity'::timestamp with time zone))
UNION ALL
 SELECT measurements.device_id,
    public.time_bucket('00:10:00'::interval, measurements."time") AS bucket,
    count(*) AS sample_count,
    avg(measurements.v1) AS avg_v1,
    min(measurements.v1) AS min_v1,
    max(measurements.v1) AS max_v1,
    avg(measurements.v2) AS avg_v2,
    min(measurements.v2) AS min_v2,
    max(measurements.v2) AS max_v2,
    avg(measurements.v3) AS avg_v3,
    min(measurements.v3) AS min_v3,
    max(measurements.v3) AS max_v3,
    avg(measurements.f1) AS avg_f,
    min(measurements.f1) AS min_f,
    max(measurements.f1) AS max_f,
    avg(measurements.thvd1) AS avg_thvd1,
    max(measurements.thvd1) AS max_thvd1,
    avg(measurements.thvd2) AS avg_thvd2,
    max(measurements.thvd2) AS max_thvd2,
    avg(measurements.thvd3) AS avg_thvd3,
    max(measurements.thvd3) AS max_thvd3
   FROM public.measurements
  WHERE (measurements."time" >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(11)), '-infinity'::timestamp with time zone))
  GROUP BY measurements.device_id, (public.time_bucket('00:10:00'::interval, measurements."time"));


--
-- Name: measurements_15min; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.measurements_15min AS
 SELECT _materialized_hypertable_9.device_id,
    _materialized_hypertable_9.bucket,
    _materialized_hypertable_9.sample_count,
    _materialized_hypertable_9.avg_total_p,
    _materialized_hypertable_9.max_total_p,
    _materialized_hypertable_9.avg_total_q,
    _materialized_hypertable_9.avg_total_s,
    _materialized_hypertable_9.avg_v1,
    _materialized_hypertable_9.min_v1,
    _materialized_hypertable_9.max_v1,
    _materialized_hypertable_9.avg_v2,
    _materialized_hypertable_9.min_v2,
    _materialized_hypertable_9.max_v2,
    _materialized_hypertable_9.avg_v3,
    _materialized_hypertable_9.min_v3,
    _materialized_hypertable_9.max_v3,
    _materialized_hypertable_9.avg_i1,
    _materialized_hypertable_9.max_i1,
    _materialized_hypertable_9.avg_i2,
    _materialized_hypertable_9.max_i2,
    _materialized_hypertable_9.avg_i3,
    _materialized_hypertable_9.max_i3,
    _materialized_hypertable_9.avg_i_neutral,
    _materialized_hypertable_9.max_i_neutral,
    _materialized_hypertable_9.avg_f,
    _materialized_hypertable_9.min_f,
    _materialized_hypertable_9.max_f,
    _materialized_hypertable_9.avg_pf1,
    _materialized_hypertable_9.avg_pf2,
    _materialized_hypertable_9.avg_pf3,
    _materialized_hypertable_9.avg_thd1,
    _materialized_hypertable_9.max_thd1,
    _materialized_hypertable_9.avg_thd2,
    _materialized_hypertable_9.max_thd2,
    _materialized_hypertable_9.avg_thd3,
    _materialized_hypertable_9.max_thd3,
    _materialized_hypertable_9.avg_thvd1,
    _materialized_hypertable_9.max_thvd1,
    _materialized_hypertable_9.avg_thvd2,
    _materialized_hypertable_9.max_thvd2,
    _materialized_hypertable_9.avg_thvd3,
    _materialized_hypertable_9.max_thvd3
   FROM _timescaledb_internal._materialized_hypertable_9
  WHERE (_materialized_hypertable_9.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(9)), '-infinity'::timestamp with time zone))
UNION ALL
 SELECT measurements.device_id,
    public.time_bucket('00:15:00'::interval, measurements."time") AS bucket,
    count(*) AS sample_count,
    avg(((COALESCE(measurements.p1, (0)::double precision) + COALESCE(measurements.p2, (0)::double precision)) + COALESCE(measurements.p3, (0)::double precision))) AS avg_total_p,
    max(((COALESCE(measurements.p1, (0)::double precision) + COALESCE(measurements.p2, (0)::double precision)) + COALESCE(measurements.p3, (0)::double precision))) AS max_total_p,
    avg(((COALESCE(measurements.q1, (0)::double precision) + COALESCE(measurements.q2, (0)::double precision)) + COALESCE(measurements.q3, (0)::double precision))) AS avg_total_q,
    avg(((COALESCE(measurements.s1, (0)::double precision) + COALESCE(measurements.s2, (0)::double precision)) + COALESCE(measurements.s3, (0)::double precision))) AS avg_total_s,
    avg(measurements.v1) AS avg_v1,
    min(measurements.v1) AS min_v1,
    max(measurements.v1) AS max_v1,
    avg(measurements.v2) AS avg_v2,
    min(measurements.v2) AS min_v2,
    max(measurements.v2) AS max_v2,
    avg(measurements.v3) AS avg_v3,
    min(measurements.v3) AS min_v3,
    max(measurements.v3) AS max_v3,
    avg(measurements.i1) AS avg_i1,
    max(measurements.i1) AS max_i1,
    avg(measurements.i2) AS avg_i2,
    max(measurements.i2) AS max_i2,
    avg(measurements.i3) AS avg_i3,
    max(measurements.i3) AS max_i3,
    avg(measurements.i_neutral) AS avg_i_neutral,
    max(measurements.i_neutral) AS max_i_neutral,
    avg(measurements.f1) AS avg_f,
    min(measurements.f1) AS min_f,
    max(measurements.f1) AS max_f,
    avg(measurements.pf1) AS avg_pf1,
    avg(measurements.pf2) AS avg_pf2,
    avg(measurements.pf3) AS avg_pf3,
    avg(measurements.thd1) AS avg_thd1,
    max(measurements.thd1) AS max_thd1,
    avg(measurements.thd2) AS avg_thd2,
    max(measurements.thd2) AS max_thd2,
    avg(measurements.thd3) AS avg_thd3,
    max(measurements.thd3) AS max_thd3,
    avg(measurements.thvd1) AS avg_thvd1,
    max(measurements.thvd1) AS max_thvd1,
    avg(measurements.thvd2) AS avg_thvd2,
    max(measurements.thvd2) AS max_thvd2,
    avg(measurements.thvd3) AS avg_thvd3,
    max(measurements.thvd3) AS max_thvd3
   FROM public.measurements
  WHERE (measurements."time" >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(9)), '-infinity'::timestamp with time zone))
  GROUP BY measurements.device_id, (public.time_bucket('00:15:00'::interval, measurements."time"));


--
-- Name: member_departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.member_departments (
    member_id integer NOT NULL,
    department_id integer NOT NULL
);


--
-- Name: member_facilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.member_facilities (
    member_id integer NOT NULL,
    facility_id integer NOT NULL
);


--
-- Name: org_invites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.org_invites (
    id integer NOT NULL,
    organization_id integer NOT NULL,
    email text NOT NULL,
    role text NOT NULL,
    facility_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    department_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    token text NOT NULL,
    invited_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone
);


--
-- Name: org_invites_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.org_invites_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: org_invites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.org_invites_id_seq OWNED BY public.org_invites.id;


--
-- Name: org_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.org_members (
    id integer NOT NULL,
    organization_id integer NOT NULL,
    username text NOT NULL,
    role text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: org_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.org_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: org_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.org_members_id_seq OWNED BY public.org_members.id;


--
-- Name: organization_billing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_billing (
    organization_id integer NOT NULL,
    contact_name text NOT NULL,
    identity_number text NOT NULL,
    email text NOT NULL,
    phone text NOT NULL,
    address text NOT NULL,
    city text NOT NULL,
    country text DEFAULT 'Turkey'::text NOT NULL,
    zip_code text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organizations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organizations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organizations_id_seq OWNED BY public.organizations.id;


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscriptions (
    id integer NOT NULL,
    username text NOT NULL,
    transport text DEFAULT 'webpush'::text NOT NULL,
    endpoint text NOT NULL,
    p256dh text,
    auth text,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_success timestamp with time zone,
    failure_count integer DEFAULT 0 NOT NULL
);


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.push_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.push_subscriptions_id_seq OWNED BY public.push_subscriptions.id;


--
-- Name: subscription_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscription_events (
    id integer NOT NULL,
    organization_id integer NOT NULL,
    action text NOT NULL,
    valid_until timestamp with time zone,
    device_count integer,
    device_price numeric,
    amount numeric,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text
);


--
-- Name: subscription_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.subscription_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: subscription_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.subscription_events_id_seq OWNED BY public.subscription_events.id;


--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscriptions (
    organization_id integer NOT NULL,
    status text DEFAULT 'trial'::text NOT NULL,
    device_price numeric DEFAULT 0 NOT NULL,
    period text DEFAULT 'yearly'::text NOT NULL,
    valid_until timestamp with time zone,
    device_limit integer,
    note text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    first_name text,
    last_name text,
    email text,
    phone text,
    is_verified boolean DEFAULT false NOT NULL,
    verification_token text,
    avatar_updated_at timestamp with time zone,
    pending_email text,
    pending_email_token text,
    role text DEFAULT 'user'::text NOT NULL,
    monthly_report boolean DEFAULT true NOT NULL,
    alarm_email boolean DEFAULT true NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: _hyper_1_15_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_15_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_1_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_24_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_24_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_25_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_25_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_26_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_26_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_27_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_27_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_2_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_33_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_33_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_1_5_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_3_16_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_3_16_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_3_28_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_3_28_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_3_3_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_3_3_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_3_4_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_3_4_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_4_17_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_4_17_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_4_29_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_4_29_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_4_6_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_4_6_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_5_18_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_18_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_5_30_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_30_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_5_7_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_7_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_6_19_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_6_19_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_6_31_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_6_31_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_6_8_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_6_8_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_7_20_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_7_20_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_7_32_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_7_32_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: _hyper_7_9_chunk time; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_7_9_chunk ALTER COLUMN "time" SET DEFAULT now();


--
-- Name: alarm_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alarm_events ALTER COLUMN id SET DEFAULT nextval('public.alarm_events_id_seq'::regclass);


--
-- Name: alarm_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alarm_rules ALTER COLUMN id SET DEFAULT nextval('public.alarm_rules_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: deletion_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deletion_requests ALTER COLUMN id SET DEFAULT nextval('public.deletion_requests_id_seq'::regclass);


--
-- Name: departments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments ALTER COLUMN id SET DEFAULT nextval('public.departments_id_seq'::regclass);


--
-- Name: devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices ALTER COLUMN id SET DEFAULT nextval('public.devices_id_seq'::regclass);


--
-- Name: facilities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facilities ALTER COLUMN id SET DEFAULT nextval('public.facilities_id_seq'::regclass);


--
-- Name: firmware_builds id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firmware_builds ALTER COLUMN id SET DEFAULT nextval('public.firmware_builds_id_seq'::regclass);


--
-- Name: iyzico_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iyzico_payments ALTER COLUMN id SET DEFAULT nextval('public.iyzico_payments_id_seq'::regclass);


--
-- Name: org_invites id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_invites ALTER COLUMN id SET DEFAULT nextval('public.org_invites_id_seq'::regclass);


--
-- Name: org_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_members ALTER COLUMN id SET DEFAULT nextval('public.org_members_id_seq'::regclass);


--
-- Name: organizations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations ALTER COLUMN id SET DEFAULT nextval('public.organizations_id_seq'::regclass);


--
-- Name: push_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.push_subscriptions_id_seq'::regclass);


--
-- Name: subscription_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_events ALTER COLUMN id SET DEFAULT nextval('public.subscription_events_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: alarm_events alarm_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alarm_events
    ADD CONSTRAINT alarm_events_pkey PRIMARY KEY (id);


--
-- Name: alarm_rules alarm_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alarm_rules
    ADD CONSTRAINT alarm_rules_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: deletion_requests deletion_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deletion_requests
    ADD CONSTRAINT deletion_requests_pkey PRIMARY KEY (id);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: device_info device_info_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_info
    ADD CONSTRAINT device_info_pkey PRIMARY KEY (device_id);


--
-- Name: device_mqtt_credentials device_mqtt_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_mqtt_credentials
    ADD CONSTRAINT device_mqtt_credentials_pkey PRIMARY KEY (device_id);


--
-- Name: device_settings device_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_settings
    ADD CONSTRAINT device_settings_pkey PRIMARY KEY (device_id);


--
-- Name: device_tariff device_tariff_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_tariff
    ADD CONSTRAINT device_tariff_pkey PRIMARY KEY (device_id);


--
-- Name: devices devices_device_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_device_id_key UNIQUE (device_id);


--
-- Name: devices devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (id);


--
-- Name: facilities facilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facilities
    ADD CONSTRAINT facilities_pkey PRIMARY KEY (id);


--
-- Name: firmware_builds firmware_builds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firmware_builds
    ADD CONSTRAINT firmware_builds_pkey PRIMARY KEY (id);


--
-- Name: iyzico_payments iyzico_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iyzico_payments
    ADD CONSTRAINT iyzico_payments_pkey PRIMARY KEY (id);


--
-- Name: iyzico_payments iyzico_payments_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iyzico_payments
    ADD CONSTRAINT iyzico_payments_token_key UNIQUE (token);


--
-- Name: member_departments member_departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_departments
    ADD CONSTRAINT member_departments_pkey PRIMARY KEY (member_id, department_id);


--
-- Name: member_facilities member_facilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_facilities
    ADD CONSTRAINT member_facilities_pkey PRIMARY KEY (member_id, facility_id);


--
-- Name: org_invites org_invites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_invites
    ADD CONSTRAINT org_invites_pkey PRIMARY KEY (id);


--
-- Name: org_invites org_invites_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_invites
    ADD CONSTRAINT org_invites_token_key UNIQUE (token);


--
-- Name: org_members org_members_organization_id_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_members
    ADD CONSTRAINT org_members_organization_id_username_key UNIQUE (organization_id, username);


--
-- Name: org_members org_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_members
    ADD CONSTRAINT org_members_pkey PRIMARY KEY (id);


--
-- Name: organization_billing organization_billing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_billing
    ADD CONSTRAINT organization_billing_pkey PRIMARY KEY (organization_id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: push_subscriptions push_subscriptions_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: subscription_events subscription_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_events
    ADD CONSTRAINT subscription_events_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (organization_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_phone_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_phone_unique UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: _hyper_10_14_chunk__materialized_hypertable_10_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_10_14_chunk__materialized_hypertable_10_bucket_idx ON _timescaledb_internal._hyper_10_14_chunk USING btree (bucket DESC);


--
-- Name: _hyper_10_14_chunk__materialized_hypertable_10_device_id_bucket; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_10_14_chunk__materialized_hypertable_10_device_id_bucket ON _timescaledb_internal._hyper_10_14_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_11_21_chunk__materialized_hypertable_11_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_21_chunk__materialized_hypertable_11_bucket_idx ON _timescaledb_internal._hyper_11_21_chunk USING btree (bucket DESC);


--
-- Name: _hyper_11_21_chunk__materialized_hypertable_11_device_id_bucket; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_21_chunk__materialized_hypertable_11_device_id_bucket ON _timescaledb_internal._hyper_11_21_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_11_22_chunk__materialized_hypertable_11_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_22_chunk__materialized_hypertable_11_bucket_idx ON _timescaledb_internal._hyper_11_22_chunk USING btree (bucket DESC);


--
-- Name: _hyper_11_22_chunk__materialized_hypertable_11_device_id_bucket; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_22_chunk__materialized_hypertable_11_device_id_bucket ON _timescaledb_internal._hyper_11_22_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_11_23_chunk__materialized_hypertable_11_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_23_chunk__materialized_hypertable_11_bucket_idx ON _timescaledb_internal._hyper_11_23_chunk USING btree (bucket DESC);


--
-- Name: _hyper_11_23_chunk__materialized_hypertable_11_device_id_bucket; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_23_chunk__materialized_hypertable_11_device_id_bucket ON _timescaledb_internal._hyper_11_23_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_11_34_chunk__materialized_hypertable_11_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_34_chunk__materialized_hypertable_11_bucket_idx ON _timescaledb_internal._hyper_11_34_chunk USING btree (bucket DESC);


--
-- Name: _hyper_11_34_chunk__materialized_hypertable_11_device_id_bucket; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_11_34_chunk__materialized_hypertable_11_device_id_bucket ON _timescaledb_internal._hyper_11_34_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_1_15_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_15_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_15_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_15_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_15_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_15_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_1_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_1_1_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_1_1_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_1_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_1_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_1_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_24_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_24_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_24_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_24_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_24_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_24_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_25_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_25_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_25_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_25_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_25_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_25_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_26_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_26_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_26_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_26_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_26_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_26_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_27_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_27_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_27_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_27_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_27_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_27_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_2_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_2_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_1_2_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_1_2_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_2_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_2_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_2_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_2_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_2_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_33_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_33_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_33_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_33_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_33_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_33_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_5_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_5_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_1_5_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_1_5_chunk_measurements_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_5_chunk_measurements_device_time_idx ON _timescaledb_internal._hyper_1_5_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_1_5_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_5_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_5_chunk USING btree ("time" DESC);


--
-- Name: _hyper_3_16_chunk_device_energy_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_16_chunk_device_energy_device_time_idx ON _timescaledb_internal._hyper_3_16_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_3_16_chunk_device_energy_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_16_chunk_device_energy_time_idx ON _timescaledb_internal._hyper_3_16_chunk USING btree ("time" DESC);


--
-- Name: _hyper_3_28_chunk_device_energy_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_28_chunk_device_energy_device_time_idx ON _timescaledb_internal._hyper_3_28_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_3_28_chunk_device_energy_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_28_chunk_device_energy_time_idx ON _timescaledb_internal._hyper_3_28_chunk USING btree ("time" DESC);


--
-- Name: _hyper_3_3_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_3_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_3_3_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_3_3_chunk_device_energy_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_3_chunk_device_energy_device_time_idx ON _timescaledb_internal._hyper_3_3_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_3_3_chunk_device_energy_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_3_chunk_device_energy_time_idx ON _timescaledb_internal._hyper_3_3_chunk USING btree ("time" DESC);


--
-- Name: _hyper_3_4_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_4_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_3_4_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_3_4_chunk_device_energy_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_4_chunk_device_energy_device_time_idx ON _timescaledb_internal._hyper_3_4_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_3_4_chunk_device_energy_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_3_4_chunk_device_energy_time_idx ON _timescaledb_internal._hyper_3_4_chunk USING btree ("time" DESC);


--
-- Name: _hyper_4_17_chunk_device_stats_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_17_chunk_device_stats_device_time_idx ON _timescaledb_internal._hyper_4_17_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_4_17_chunk_device_stats_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_17_chunk_device_stats_time_idx ON _timescaledb_internal._hyper_4_17_chunk USING btree ("time" DESC);


--
-- Name: _hyper_4_29_chunk_device_stats_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_29_chunk_device_stats_device_time_idx ON _timescaledb_internal._hyper_4_29_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_4_29_chunk_device_stats_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_29_chunk_device_stats_time_idx ON _timescaledb_internal._hyper_4_29_chunk USING btree ("time" DESC);


--
-- Name: _hyper_4_6_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_6_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_4_6_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_4_6_chunk_device_stats_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_6_chunk_device_stats_device_time_idx ON _timescaledb_internal._hyper_4_6_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_4_6_chunk_device_stats_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_4_6_chunk_device_stats_time_idx ON _timescaledb_internal._hyper_4_6_chunk USING btree ("time" DESC);


--
-- Name: _hyper_5_18_chunk_device_peaks_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_18_chunk_device_peaks_device_time_idx ON _timescaledb_internal._hyper_5_18_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_5_18_chunk_device_peaks_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_18_chunk_device_peaks_time_idx ON _timescaledb_internal._hyper_5_18_chunk USING btree ("time" DESC);


--
-- Name: _hyper_5_30_chunk_device_peaks_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_30_chunk_device_peaks_device_time_idx ON _timescaledb_internal._hyper_5_30_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_5_30_chunk_device_peaks_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_30_chunk_device_peaks_time_idx ON _timescaledb_internal._hyper_5_30_chunk USING btree ("time" DESC);


--
-- Name: _hyper_5_7_chunk_compressed_device_id_direction__ts_meta_v2_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_7_chunk_compressed_device_id_direction__ts_meta_v2_idx ON _timescaledb_internal._hyper_5_7_chunk_compressed USING btree (device_id, direction, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_5_7_chunk_device_peaks_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_7_chunk_device_peaks_device_time_idx ON _timescaledb_internal._hyper_5_7_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_5_7_chunk_device_peaks_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_5_7_chunk_device_peaks_time_idx ON _timescaledb_internal._hyper_5_7_chunk USING btree ("time" DESC);


--
-- Name: _hyper_6_19_chunk_device_demand_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_19_chunk_device_demand_device_time_idx ON _timescaledb_internal._hyper_6_19_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_6_19_chunk_device_demand_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_19_chunk_device_demand_time_idx ON _timescaledb_internal._hyper_6_19_chunk USING btree ("time" DESC);


--
-- Name: _hyper_6_31_chunk_device_demand_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_31_chunk_device_demand_device_time_idx ON _timescaledb_internal._hyper_6_31_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_6_31_chunk_device_demand_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_31_chunk_device_demand_time_idx ON _timescaledb_internal._hyper_6_31_chunk USING btree ("time" DESC);


--
-- Name: _hyper_6_8_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_8_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_6_8_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_6_8_chunk_device_demand_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_8_chunk_device_demand_device_time_idx ON _timescaledb_internal._hyper_6_8_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_6_8_chunk_device_demand_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_6_8_chunk_device_demand_time_idx ON _timescaledb_internal._hyper_6_8_chunk USING btree ("time" DESC);


--
-- Name: _hyper_7_20_chunk_device_harmonics_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_20_chunk_device_harmonics_device_time_idx ON _timescaledb_internal._hyper_7_20_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_7_20_chunk_device_harmonics_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_20_chunk_device_harmonics_time_idx ON _timescaledb_internal._hyper_7_20_chunk USING btree ("time" DESC);


--
-- Name: _hyper_7_32_chunk_device_harmonics_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_32_chunk_device_harmonics_device_time_idx ON _timescaledb_internal._hyper_7_32_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_7_32_chunk_device_harmonics_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_32_chunk_device_harmonics_time_idx ON _timescaledb_internal._hyper_7_32_chunk USING btree ("time" DESC);


--
-- Name: _hyper_7_9_chunk_compressed_device_id__ts_meta_v2_first_tim_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_9_chunk_compressed_device_id__ts_meta_v2_first_tim_idx ON _timescaledb_internal._hyper_7_9_chunk_compressed USING btree (device_id, _ts_meta_v2_first_time DESC, _ts_meta_v2_last_time DESC);


--
-- Name: _hyper_7_9_chunk_device_harmonics_device_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_9_chunk_device_harmonics_device_time_idx ON _timescaledb_internal._hyper_7_9_chunk USING btree (device_id, "time" DESC);


--
-- Name: _hyper_7_9_chunk_device_harmonics_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_7_9_chunk_device_harmonics_time_idx ON _timescaledb_internal._hyper_7_9_chunk USING btree ("time" DESC);


--
-- Name: _hyper_9_11_chunk__materialized_hypertable_9_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_11_chunk__materialized_hypertable_9_bucket_idx ON _timescaledb_internal._hyper_9_11_chunk USING btree (bucket DESC);


--
-- Name: _hyper_9_11_chunk__materialized_hypertable_9_device_id_bucket_i; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_11_chunk__materialized_hypertable_9_device_id_bucket_i ON _timescaledb_internal._hyper_9_11_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_9_12_chunk__materialized_hypertable_9_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_12_chunk__materialized_hypertable_9_bucket_idx ON _timescaledb_internal._hyper_9_12_chunk USING btree (bucket DESC);


--
-- Name: _hyper_9_12_chunk__materialized_hypertable_9_device_id_bucket_i; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_12_chunk__materialized_hypertable_9_device_id_bucket_i ON _timescaledb_internal._hyper_9_12_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_9_13_chunk__materialized_hypertable_9_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_13_chunk__materialized_hypertable_9_bucket_idx ON _timescaledb_internal._hyper_9_13_chunk USING btree (bucket DESC);


--
-- Name: _hyper_9_13_chunk__materialized_hypertable_9_device_id_bucket_i; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_13_chunk__materialized_hypertable_9_device_id_bucket_i ON _timescaledb_internal._hyper_9_13_chunk USING btree (device_id, bucket DESC);


--
-- Name: _hyper_9_35_chunk__materialized_hypertable_9_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_35_chunk__materialized_hypertable_9_bucket_idx ON _timescaledb_internal._hyper_9_35_chunk USING btree (bucket DESC);


--
-- Name: _hyper_9_35_chunk__materialized_hypertable_9_device_id_bucket_i; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_9_35_chunk__materialized_hypertable_9_device_id_bucket_i ON _timescaledb_internal._hyper_9_35_chunk USING btree (device_id, bucket DESC);


--
-- Name: _materialized_hypertable_10_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_10_bucket_idx ON _timescaledb_internal._materialized_hypertable_10 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_10_device_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_10_device_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_10 USING btree (device_id, bucket DESC);


--
-- Name: _materialized_hypertable_11_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_11_bucket_idx ON _timescaledb_internal._materialized_hypertable_11 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_11_device_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_11_device_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_11 USING btree (device_id, bucket DESC);


--
-- Name: _materialized_hypertable_9_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_9_bucket_idx ON _timescaledb_internal._materialized_hypertable_9 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_9_device_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_9_device_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_9 USING btree (device_id, bucket DESC);


--
-- Name: alarm_events_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX alarm_events_device_time_idx ON public.alarm_events USING btree (device_id, triggered_at DESC);


--
-- Name: alarm_rules_device_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX alarm_rules_device_idx ON public.alarm_rules USING btree (device_id) WHERE enabled;


--
-- Name: audit_log_actor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_actor_idx ON public.audit_log USING btree (actor, at DESC);


--
-- Name: audit_log_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_org_idx ON public.audit_log USING btree (organization_id, at DESC);


--
-- Name: departments_facility_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX departments_facility_idx ON public.departments USING btree (facility_id);


--
-- Name: device_demand_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_demand_device_time_idx ON public.device_demand USING btree (device_id, "time" DESC);


--
-- Name: device_demand_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_demand_time_idx ON public.device_demand USING btree ("time" DESC);


--
-- Name: device_energy_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_energy_device_time_idx ON public.device_energy USING btree (device_id, "time" DESC);


--
-- Name: device_energy_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_energy_time_idx ON public.device_energy USING btree ("time" DESC);


--
-- Name: device_harmonics_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_harmonics_device_time_idx ON public.device_harmonics USING btree (device_id, "time" DESC);


--
-- Name: device_harmonics_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_harmonics_time_idx ON public.device_harmonics USING btree ("time" DESC);


--
-- Name: device_peaks_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_peaks_device_time_idx ON public.device_peaks USING btree (device_id, "time" DESC);


--
-- Name: device_peaks_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_peaks_time_idx ON public.device_peaks USING btree ("time" DESC);


--
-- Name: device_stats_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_stats_device_time_idx ON public.device_stats USING btree (device_id, "time" DESC);


--
-- Name: device_stats_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX device_stats_time_idx ON public.device_stats USING btree ("time" DESC);


--
-- Name: devices_department_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX devices_department_idx ON public.devices USING btree (department_id);


--
-- Name: devices_facility_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX devices_facility_idx ON public.devices USING btree (facility_id);


--
-- Name: facilities_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX facilities_org_idx ON public.facilities USING btree (organization_id);


--
-- Name: iyzico_payments_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX iyzico_payments_org_idx ON public.iyzico_payments USING btree (organization_id);


--
-- Name: measurements_device_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX measurements_device_time_idx ON public.measurements USING btree (device_id, "time" DESC);


--
-- Name: measurements_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX measurements_time_idx ON public.measurements USING btree ("time" DESC);


--
-- Name: org_invites_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX org_invites_org_idx ON public.org_invites USING btree (organization_id) WHERE (accepted_at IS NULL);


--
-- Name: org_members_username_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX org_members_username_idx ON public.org_members USING btree (username);


--
-- Name: push_subscriptions_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX push_subscriptions_user_idx ON public.push_subscriptions USING btree (username);


--
-- Name: subscription_events_org_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_org_idx ON public.subscription_events USING btree (organization_id, created_at DESC);


--
-- Name: alarm_events alarm_events_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alarm_events
    ADD CONSTRAINT alarm_events_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.alarm_rules(id) ON DELETE CASCADE;


--
-- Name: alarm_rules alarm_rules_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alarm_rules
    ADD CONSTRAINT alarm_rules_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(device_id) ON DELETE CASCADE;


--
-- Name: departments departments_facility_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facilities(id) ON DELETE CASCADE;


--
-- Name: device_mqtt_credentials device_mqtt_credentials_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_mqtt_credentials
    ADD CONSTRAINT device_mqtt_credentials_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(device_id) ON DELETE CASCADE;


--
-- Name: devices devices_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: devices devices_facility_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: devices devices_owner_username_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_owner_username_fkey FOREIGN KEY (owner_username) REFERENCES public.users(username);


--
-- Name: facilities facilities_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facilities
    ADD CONSTRAINT facilities_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: iyzico_payments iyzico_payments_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iyzico_payments
    ADD CONSTRAINT iyzico_payments_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: member_departments member_departments_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_departments
    ADD CONSTRAINT member_departments_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE;


--
-- Name: member_departments member_departments_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_departments
    ADD CONSTRAINT member_departments_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.org_members(id) ON DELETE CASCADE;


--
-- Name: member_facilities member_facilities_facility_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_facilities
    ADD CONSTRAINT member_facilities_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facilities(id) ON DELETE CASCADE;


--
-- Name: member_facilities member_facilities_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_facilities
    ADD CONSTRAINT member_facilities_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.org_members(id) ON DELETE CASCADE;


--
-- Name: org_invites org_invites_invited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_invites
    ADD CONSTRAINT org_invites_invited_by_fkey FOREIGN KEY (invited_by) REFERENCES public.users(username) ON DELETE CASCADE;


--
-- Name: org_invites org_invites_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_invites
    ADD CONSTRAINT org_invites_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: org_members org_members_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_members
    ADD CONSTRAINT org_members_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: org_members org_members_username_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.org_members
    ADD CONSTRAINT org_members_username_fkey FOREIGN KEY (username) REFERENCES public.users(username) ON DELETE CASCADE;


--
-- Name: organization_billing organization_billing_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_billing
    ADD CONSTRAINT organization_billing_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: push_subscriptions push_subscriptions_username_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_username_fkey FOREIGN KEY (username) REFERENCES public.users(username) ON DELETE CASCADE;


--
-- Name: subscription_events subscription_events_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_events
    ADD CONSTRAINT subscription_events_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: subscriptions subscriptions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict JP3bEwbYm6ddAfSRXGpyypebSgrL7s1p7X2TxF9NPvFyfjqdDhvn5tK5JsRfNwn

