-- =====================================================================
-- Binary Enerji — TAM ŞEMA TEMELİ (baseline)
--
-- Bu dosya, üretimdeki public şemasının `pg_dump --schema-only` çıktısıdır.
-- Şimdiye kadar tablolar tek tek elle oluşturuldu ve şemanın bütününün
-- tanımlı olduğu tek bir yer yoktu: sunucu kaybolsaydı yeniden kurmanın tek
-- yolu bir yedeği geri yüklemekti.
--
-- İki yerde kullanılıyor:
--   1. Test veritabanı kurulumu (tests/)
--   2. Felaket senaryosunda sıfırdan kurulum
--
-- TIMESCALEDB'YE ÖZEL KISIMLAR BURADA YOK. Hypertable dönüşümleri, sürekli
-- toplamalar (device_energy_hourly, measurements_10min, measurements_15min),
-- sıkıştırma ve saklama politikaları ops/schema/ altındaki tarihli göç
-- dosyalarında. Sıfırdan kurulumda önce bu dosya, sonra o göçler uygulanmalı.
--
-- Yeniden üretmek için:
--   ssh binaryenerji "docker exec \$(docker ps -qf name=timescaledb) \
--     pg_dump -U postgres --schema-only --no-owner --no-privileges \
--     --schema=public postgres"
--   (çıktıdan CREATE VIEW ile başlayan 3 sürekli toplama bloğu çıkarılır)
-- =====================================================================

--
-- PostgreSQL database dump
--

\restrict ORZpet7MrYcgP1vAoMvkjVvYfWFwgazar84vxLKAIPq2RYeG6FhbWp1edX0CwHm

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
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- 'CREATE SCHEMA public' cikarildi: yeni veritabaninda zaten mevcut.
-- CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


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
    last_triggered_at timestamp with time zone
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
    demand_price numeric DEFAULT 0 NOT NULL
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
-- Name: measurements_10min; Type: VIEW; Schema: public; Owner: -
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

\unrestrict ORZpet7MrYcgP1vAoMvkjVvYfWFwgazar84vxLKAIPq2RYeG6FhbWp1edX0CwHm

