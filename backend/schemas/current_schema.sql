--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: video_generation_mode; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.video_generation_mode AS ENUM (
    'standard',
    'target'
);


--
-- Name: videoautomationmode; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.videoautomationmode AS ENUM (
    'manual',
    'per_capture',
    'scheduled',
    'milestone'
);


--
-- Name: notify_sse_event(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notify_sse_event() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        payload TEXT;
    BEGIN
        -- Create JSON payload with basic event info
        payload := json_build_object(
            'id', NEW.id,
            'event_type', NEW.event_type,
            'priority', NEW.priority,
            'source', NEW.source,
            'created_at', NEW.created_at
        )::TEXT;
        
        -- Send notification on 'sse_events' channel
        PERFORM pg_notify('sse_events', payload);
        
        RETURN NEW;
    END;
    $$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END; $$;


SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: cameras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cameras (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    rtsp_url text NOT NULL,
    status character varying(20) DEFAULT 'inactive'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    health_status character varying(20) DEFAULT 'unknown'::character varying,
    last_capture_at timestamp without time zone,
    last_capture_success boolean DEFAULT true,
    consecutive_failures integer DEFAULT 0,
    next_capture_at timestamp without time zone,
    active_timelapse_id integer,
    lifetime_glitch_count integer DEFAULT 0 NOT NULL,
    consecutive_corruption_failures integer DEFAULT 0 NOT NULL,
    corruption_detection_heavy boolean DEFAULT false NOT NULL,
    last_degraded_at timestamp with time zone,
    degraded_mode_active boolean DEFAULT false,
    enabled boolean DEFAULT true,
    is_connected boolean DEFAULT false,
    last_error text,
    last_error_message text,
    corruption_score integer DEFAULT 100 NOT NULL,
    rotation integer DEFAULT 0 NOT NULL,
    crop_rotation_settings jsonb DEFAULT '{}'::jsonb,
    crop_rotation_enabled boolean DEFAULT false NOT NULL,
    source_resolution jsonb DEFAULT '{}'::jsonb,
    is_flagged boolean DEFAULT false NOT NULL,
    CONSTRAINT cameras_health_status_check CHECK (((health_status)::text = ANY ((ARRAY['online'::character varying, 'offline'::character varying, 'unknown'::character varying])::text[]))),
    CONSTRAINT cameras_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying])::text[]))),
    CONSTRAINT ck_cameras_rotation_valid CHECK ((rotation = ANY (ARRAY[0, 90, 180, 270])))
);


--
-- Name: COLUMN cameras.rotation; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cameras.rotation IS 'Camera rotation in degrees (0, 90, 180, 270)';


--
-- Name: COLUMN cameras.crop_rotation_settings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cameras.crop_rotation_settings IS 'Camera crop, rotation, and aspect ratio settings';


--
-- Name: COLUMN cameras.crop_rotation_enabled; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cameras.crop_rotation_enabled IS 'Whether camera has custom crop/rotation settings enabled';


--
-- Name: COLUMN cameras.source_resolution; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cameras.source_resolution IS 'Original camera resolution (width, height) before any processing';


--
-- Name: cameras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cameras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cameras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cameras_id_seq OWNED BY public.cameras.id;


--
-- Name: corruption_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.corruption_logs (
    id integer NOT NULL,
    camera_id integer,
    image_id integer,
    corruption_score integer NOT NULL,
    fast_score integer,
    heavy_score integer,
    detection_details jsonb NOT NULL,
    action_taken character varying(50) NOT NULL,
    processing_time_ms integer,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT corruption_logs_corruption_score_check CHECK (((corruption_score >= 0) AND (corruption_score <= 100))),
    CONSTRAINT corruption_logs_fast_score_check CHECK (((fast_score >= 0) AND (fast_score <= 100))),
    CONSTRAINT corruption_logs_heavy_score_check CHECK (((heavy_score >= 0) AND (heavy_score <= 100)))
);


--
-- Name: corruption_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.corruption_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: corruption_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.corruption_logs_id_seq OWNED BY public.corruption_logs.id;


--
-- Name: images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.images (
    id integer NOT NULL,
    camera_id integer NOT NULL,
    timelapse_id integer NOT NULL,
    file_path text NOT NULL,
    captured_at timestamp without time zone NOT NULL,
    day_number integer NOT NULL,
    file_size bigint,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    date_directory character varying(255),
    file_name character varying(255),
    thumbnail_path text,
    small_path text,
    thumbnail_size bigint,
    small_size bigint,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    corruption_score integer DEFAULT 100,
    is_flagged boolean DEFAULT false,
    corruption_details jsonb,
    overlay_path text,
    has_valid_overlay boolean DEFAULT false NOT NULL,
    overlay_updated_at timestamp with time zone,
    corruption_detected boolean,
    weather_temperature numeric(5,2),
    weather_conditions text,
    weather_icon character varying(50),
    weather_fetched_at timestamp with time zone,
    CONSTRAINT images_corruption_score_check CHECK (((corruption_score >= 0) AND (corruption_score <= 100)))
);


--
-- Name: COLUMN images.overlay_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.images.overlay_path IS 'Path to generated overlay image file';


--
-- Name: COLUMN images.has_valid_overlay; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.images.has_valid_overlay IS 'Whether image has successfully generated overlay';


--
-- Name: COLUMN images.overlay_updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.images.overlay_updated_at IS 'Timestamp of last overlay generation';


--
-- Name: images_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.images_id_seq OWNED BY public.images.id;


--
-- Name: logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.logs (
    id integer NOT NULL,
    level character varying(20) NOT NULL,
    message text NOT NULL,
    camera_id integer,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    source text,
    logger_name character varying(255),
    extra_data jsonb
);


--
-- Name: logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.logs_id_seq OWNED BY public.logs.id;


--
-- Name: overlay_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overlay_assets (
    id integer NOT NULL,
    filename character varying(255) NOT NULL,
    original_name character varying(255) NOT NULL,
    file_path text NOT NULL,
    file_size integer NOT NULL,
    mime_type character varying(100) NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_overlay_assets_file_size CHECK (((file_size > 0) AND (file_size <= 104857600))),
    CONSTRAINT ck_overlay_assets_mime_type CHECK (((mime_type)::text = ANY ((ARRAY['image/png'::character varying, 'image/jpeg'::character varying, 'image/webp'::character varying])::text[])))
);


--
-- Name: TABLE overlay_assets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.overlay_assets IS 'Uploaded watermark and logo assets for overlays';


--
-- Name: overlay_assets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.overlay_assets ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.overlay_assets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: overlay_generation_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overlay_generation_jobs (
    id integer NOT NULL,
    image_id integer NOT NULL,
    priority character varying(20) DEFAULT 'medium'::character varying NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    job_type character varying(20) DEFAULT 'single'::character varying NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    CONSTRAINT ck_overlay_generation_jobs_job_type CHECK (((job_type)::text = ANY ((ARRAY['single'::character varying, 'batch'::character varying, 'priority'::character varying])::text[]))),
    CONSTRAINT ck_overlay_generation_jobs_priority CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying])::text[]))),
    CONSTRAINT ck_overlay_generation_jobs_retry_count CHECK (((retry_count >= 0) AND (retry_count <= 5))),
    CONSTRAINT ck_overlay_generation_jobs_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT ck_overlay_generation_jobs_valid_timing CHECK ((((started_at IS NULL) OR (started_at >= created_at)) AND ((completed_at IS NULL) OR (completed_at >= COALESCE(started_at, created_at)))))
);


--
-- Name: TABLE overlay_generation_jobs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.overlay_generation_jobs IS 'Job queue for overlay generation processing';


--
-- Name: overlay_generation_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.overlay_generation_jobs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.overlay_generation_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: overlay_presets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overlay_presets (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    overlay_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_builtin boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE overlay_presets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.overlay_presets IS 'System-wide overlay presets for timelapse configuration';


--
-- Name: overlay_presets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.overlay_presets ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.overlay_presets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: scheduled_job_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scheduled_job_executions (
    id integer NOT NULL,
    job_id character varying(100) NOT NULL,
    scheduled_job_id integer NOT NULL,
    execution_start timestamp with time zone NOT NULL,
    execution_end timestamp with time zone,
    status character varying(20) NOT NULL,
    result_message text,
    error_message text,
    execution_duration_ms integer,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE scheduled_job_executions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.scheduled_job_executions IS 'Detailed log of job executions for monitoring and debugging';


--
-- Name: COLUMN scheduled_job_executions.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_job_executions.status IS 'Execution status: running, completed, failed, timeout';


--
-- Name: scheduled_job_executions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scheduled_job_executions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scheduled_job_executions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scheduled_job_executions_id_seq OWNED BY public.scheduled_job_executions.id;


--
-- Name: scheduled_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scheduled_jobs (
    id integer NOT NULL,
    job_id character varying(100) NOT NULL,
    job_type character varying(50) NOT NULL,
    schedule_pattern character varying(100),
    interval_seconds integer,
    next_run_time timestamp with time zone,
    last_run_time timestamp with time zone,
    last_success_time timestamp with time zone,
    last_failure_time timestamp with time zone,
    entity_id integer,
    entity_type character varying(50),
    config jsonb,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    execution_count integer DEFAULT 0 NOT NULL,
    success_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    last_error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE scheduled_jobs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.scheduled_jobs IS 'Tracks APScheduler jobs for visibility and persistence across restarts';


--
-- Name: COLUMN scheduled_jobs.job_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.job_id IS 'Unique job identifier matching APScheduler job_id';


--
-- Name: COLUMN scheduled_jobs.job_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.job_type IS 'Type of job (timelapse_capture, health_check, video_automation, etc.)';


--
-- Name: COLUMN scheduled_jobs.schedule_pattern; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.schedule_pattern IS 'Cron expression or interval description';


--
-- Name: COLUMN scheduled_jobs.interval_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.interval_seconds IS 'Interval in seconds for interval-based jobs';


--
-- Name: COLUMN scheduled_jobs.entity_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.entity_id IS 'ID of related entity (camera_id, timelapse_id, etc.)';


--
-- Name: COLUMN scheduled_jobs.entity_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.entity_type IS 'Type of related entity (camera, timelapse, system)';


--
-- Name: COLUMN scheduled_jobs.config; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.config IS 'Job-specific configuration and parameters';


--
-- Name: COLUMN scheduled_jobs.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.scheduled_jobs.status IS 'Job status: active, paused, disabled, error';


--
-- Name: scheduled_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scheduled_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scheduled_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scheduled_jobs_id_seq OWNED BY public.scheduled_jobs.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.settings (
    id integer NOT NULL,
    key character varying(100) NOT NULL,
    value text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.settings_id_seq OWNED BY public.settings.id;


--
-- Name: sse_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sse_events (
    id integer NOT NULL,
    event_type character varying(100) NOT NULL,
    event_data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone,
    retry_count integer NOT NULL,
    priority character varying(20) NOT NULL,
    source character varying(50) NOT NULL
);


--
-- Name: sse_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sse_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sse_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sse_events_id_seq OWNED BY public.sse_events.id;


--
-- Name: thumbnail_generation_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.thumbnail_generation_jobs (
    id integer NOT NULL,
    image_id integer NOT NULL,
    priority character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    job_type character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_message text,
    processing_time_ms integer,
    retry_count integer NOT NULL
);


--
-- Name: thumbnail_generation_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.thumbnail_generation_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: thumbnail_generation_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.thumbnail_generation_jobs_id_seq OWNED BY public.thumbnail_generation_jobs.id;


--
-- Name: timelapse_overlays; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.timelapse_overlays (
    id integer NOT NULL,
    timelapse_id integer NOT NULL,
    preset_id integer,
    overlay_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE timelapse_overlays; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.timelapse_overlays IS 'Overlay configurations for individual timelapses';


--
-- Name: timelapse_overlays_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.timelapse_overlays ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.timelapse_overlays_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: timelapses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.timelapses (
    id integer NOT NULL,
    camera_id integer,
    status character varying(20) DEFAULT 'stopped'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    start_date date,
    image_count integer DEFAULT 0,
    last_capture_at timestamp without time zone,
    auto_stop_at timestamp with time zone,
    name character varying(255),
    time_window_start time without time zone,
    time_window_end time without time zone,
    use_custom_time_window boolean DEFAULT false,
    video_automation_mode public.videoautomationmode,
    standard_fps integer,
    enable_time_limits boolean,
    min_time_seconds integer,
    max_time_seconds integer,
    target_time_seconds integer,
    fps_bounds_min integer,
    fps_bounds_max integer,
    glitch_count integer DEFAULT 0,
    total_corruption_score bigint DEFAULT 0,
    time_window_type character varying(20) DEFAULT 'none'::character varying NOT NULL,
    sunrise_offset_minutes integer,
    sunset_offset_minutes integer,
    generation_schedule jsonb,
    milestone_config jsonb,
    video_generation_mode character varying(20),
    thumbnail_count integer DEFAULT 0 NOT NULL,
    small_count integer DEFAULT 0 NOT NULL,
    starred boolean,
    capture_interval_seconds integer DEFAULT 300 NOT NULL,
    CONSTRAINT ck_timelapses_capture_interval_range CHECK (((capture_interval_seconds >= 30) AND (capture_interval_seconds <= 86400))),
    CONSTRAINT ck_timelapses_time_window_type CHECK (((time_window_type)::text = ANY ((ARRAY['none'::character varying, 'time'::character varying, 'sunrise_sunset'::character varying])::text[]))),
    CONSTRAINT timelapses_status_check CHECK (((status)::text = ANY ((ARRAY['running'::character varying, 'paused'::character varying, 'completed'::character varying])::text[])))
);


--
-- Name: timelapses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.timelapses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: timelapses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.timelapses_id_seq OWNED BY public.timelapses.id;


--
-- Name: video_generation_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.video_generation_jobs (
    id integer NOT NULL,
    timelapse_id integer NOT NULL,
    trigger_type character varying(20) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    priority character varying(10) DEFAULT 'medium'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_message text,
    video_path character varying(500),
    video_id integer,
    settings jsonb
);


--
-- Name: video_generation_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.video_generation_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: video_generation_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.video_generation_jobs_id_seq OWNED BY public.video_generation_jobs.id;


--
-- Name: videos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.videos (
    id integer NOT NULL,
    camera_id integer NOT NULL,
    name character varying(255) NOT NULL,
    file_path text,
    status character varying(20) DEFAULT 'generating'::character varying,
    settings jsonb DEFAULT '{}'::jsonb,
    image_count integer DEFAULT 0,
    file_size bigint DEFAULT 0,
    duration_seconds numeric(10,2) DEFAULT 0,
    images_start_date date,
    images_end_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    calculated_fps numeric(6,2),
    target_duration integer,
    actual_duration numeric(8,2),
    fps_was_adjusted boolean NOT NULL,
    adjustment_reason text,
    timelapse_id integer,
    trigger_type character varying(20),
    job_id integer,
    CONSTRAINT videos_status_check CHECK (((status)::text = ANY ((ARRAY['generating'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: videos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.videos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: videos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.videos_id_seq OWNED BY public.videos.id;


--
-- Name: weather_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather_data (
    id integer NOT NULL,
    weather_date_fetched timestamp with time zone,
    current_temp double precision,
    current_weather_icon character varying(50),
    current_weather_description character varying(255),
    sunrise_timestamp timestamp with time zone,
    sunset_timestamp timestamp with time zone,
    api_key_valid boolean DEFAULT true,
    api_failing boolean DEFAULT false,
    error_response_code integer,
    last_error_message text,
    consecutive_failures integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    single_row_enforcer integer DEFAULT 1,
    CONSTRAINT weather_data_single_row_enforcer_check CHECK ((single_row_enforcer = 1))
);


--
-- Name: TABLE weather_data; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.weather_data IS 'Single-row table for current weather state. Uses UPSERT pattern to maintain only one row.';


--
-- Name: COLUMN weather_data.single_row_enforcer; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.weather_data.single_row_enforcer IS 'Ensures only one row can exist in this table';


--
-- Name: weather_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weather_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_data_id_seq OWNED BY public.weather_data.id;


--
-- Name: cameras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras ALTER COLUMN id SET DEFAULT nextval('public.cameras_id_seq'::regclass);


--
-- Name: corruption_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corruption_logs ALTER COLUMN id SET DEFAULT nextval('public.corruption_logs_id_seq'::regclass);


--
-- Name: images id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images ALTER COLUMN id SET DEFAULT nextval('public.images_id_seq'::regclass);


--
-- Name: logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logs ALTER COLUMN id SET DEFAULT nextval('public.logs_id_seq'::regclass);


--
-- Name: scheduled_job_executions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_job_executions ALTER COLUMN id SET DEFAULT nextval('public.scheduled_job_executions_id_seq'::regclass);


--
-- Name: scheduled_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_jobs ALTER COLUMN id SET DEFAULT nextval('public.scheduled_jobs_id_seq'::regclass);


--
-- Name: settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings ALTER COLUMN id SET DEFAULT nextval('public.settings_id_seq'::regclass);


--
-- Name: sse_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sse_events ALTER COLUMN id SET DEFAULT nextval('public.sse_events_id_seq'::regclass);


--
-- Name: thumbnail_generation_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.thumbnail_generation_jobs ALTER COLUMN id SET DEFAULT nextval('public.thumbnail_generation_jobs_id_seq'::regclass);


--
-- Name: timelapses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapses ALTER COLUMN id SET DEFAULT nextval('public.timelapses_id_seq'::regclass);


--
-- Name: video_generation_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_generation_jobs ALTER COLUMN id SET DEFAULT nextval('public.video_generation_jobs_id_seq'::regclass);


--
-- Name: videos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos ALTER COLUMN id SET DEFAULT nextval('public.videos_id_seq'::regclass);


--
-- Name: weather_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_data ALTER COLUMN id SET DEFAULT nextval('public.weather_data_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: cameras cameras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT cameras_pkey PRIMARY KEY (id);


--
-- Name: corruption_logs corruption_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corruption_logs
    ADD CONSTRAINT corruption_logs_pkey PRIMARY KEY (id);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- Name: logs logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logs
    ADD CONSTRAINT logs_pkey PRIMARY KEY (id);


--
-- Name: overlay_assets overlay_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overlay_assets
    ADD CONSTRAINT overlay_assets_pkey PRIMARY KEY (id);


--
-- Name: overlay_generation_jobs overlay_generation_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overlay_generation_jobs
    ADD CONSTRAINT overlay_generation_jobs_pkey PRIMARY KEY (id);


--
-- Name: overlay_presets overlay_presets_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overlay_presets
    ADD CONSTRAINT overlay_presets_name_key UNIQUE (name);


--
-- Name: overlay_presets overlay_presets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overlay_presets
    ADD CONSTRAINT overlay_presets_pkey PRIMARY KEY (id);


--
-- Name: scheduled_job_executions scheduled_job_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_job_executions
    ADD CONSTRAINT scheduled_job_executions_pkey PRIMARY KEY (id);


--
-- Name: scheduled_jobs scheduled_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_jobs
    ADD CONSTRAINT scheduled_jobs_pkey PRIMARY KEY (id);


--
-- Name: settings settings_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_key_key UNIQUE (key);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (id);


--
-- Name: sse_events sse_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sse_events
    ADD CONSTRAINT sse_events_pkey PRIMARY KEY (id);


--
-- Name: thumbnail_generation_jobs thumbnail_generation_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.thumbnail_generation_jobs
    ADD CONSTRAINT thumbnail_generation_jobs_pkey PRIMARY KEY (id);


--
-- Name: timelapse_overlays timelapse_overlays_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapse_overlays
    ADD CONSTRAINT timelapse_overlays_pkey PRIMARY KEY (id);


--
-- Name: timelapses timelapses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapses
    ADD CONSTRAINT timelapses_pkey PRIMARY KEY (id);


--
-- Name: scheduled_jobs uq_scheduled_jobs_job_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_jobs
    ADD CONSTRAINT uq_scheduled_jobs_job_id UNIQUE (job_id);


--
-- Name: timelapse_overlays uq_timelapse_overlays_timelapse_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapse_overlays
    ADD CONSTRAINT uq_timelapse_overlays_timelapse_id UNIQUE (timelapse_id);


--
-- Name: weather_data uq_weather_data_single_row; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_data
    ADD CONSTRAINT uq_weather_data_single_row UNIQUE (single_row_enforcer);


--
-- Name: video_generation_jobs video_generation_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_generation_jobs
    ADD CONSTRAINT video_generation_jobs_pkey PRIMARY KEY (id);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: weather_data weather_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_data
    ADD CONSTRAINT weather_data_pkey PRIMARY KEY (id);


--
-- Name: idx_cameras_crop_rotation_settings; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cameras_crop_rotation_settings ON public.cameras USING gin (crop_rotation_settings);


--
-- Name: idx_cameras_next_capture_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cameras_next_capture_at ON public.cameras USING btree (next_capture_at);


--
-- Name: idx_corruption_logs_camera_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_corruption_logs_camera_id ON public.corruption_logs USING btree (camera_id);


--
-- Name: idx_corruption_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_corruption_logs_created_at ON public.corruption_logs USING btree (created_at);


--
-- Name: idx_corruption_logs_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_corruption_logs_score ON public.corruption_logs USING btree (corruption_score);


--
-- Name: idx_images_camera_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_camera_day ON public.images USING btree (camera_id, day_number);


--
-- Name: idx_images_has_valid_overlay; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_has_valid_overlay ON public.images USING btree (has_valid_overlay);


--
-- Name: idx_images_overlay_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_overlay_updated_at ON public.images USING btree (overlay_updated_at);


--
-- Name: idx_images_timelapse; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_timelapse ON public.images USING btree (timelapse_id, day_number);


--
-- Name: idx_one_active_timelapse_per_camera; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_one_active_timelapse_per_camera ON public.timelapses USING btree (camera_id) WHERE ((status)::text = ANY ((ARRAY['running'::character varying, 'paused'::character varying])::text[]));


--
-- Name: idx_overlay_assets_images; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overlay_assets_images ON public.overlay_assets USING btree (mime_type) WHERE ((mime_type)::text ~~ 'image/%'::text);


--
-- Name: idx_overlay_generation_jobs_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overlay_generation_jobs_active ON public.overlay_generation_jobs USING btree (priority, created_at) INCLUDE (image_id, job_type) WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying])::text[]));


--
-- Name: idx_overlay_generation_jobs_completed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overlay_generation_jobs_completed ON public.overlay_generation_jobs USING btree (completed_at) WHERE ((status)::text = ANY ((ARRAY['completed'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[]));


--
-- Name: idx_overlay_presets_builtin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overlay_presets_builtin ON public.overlay_presets USING btree (name) WHERE (is_builtin = true);


--
-- Name: idx_overlay_presets_config_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overlay_presets_config_gin ON public.overlay_presets USING gin (overlay_config);


--
-- Name: idx_scheduled_job_executions_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_job_executions_job_id ON public.scheduled_job_executions USING btree (job_id);


--
-- Name: idx_scheduled_job_executions_scheduled_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_job_executions_scheduled_job_id ON public.scheduled_job_executions USING btree (scheduled_job_id);


--
-- Name: idx_scheduled_job_executions_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_job_executions_start_time ON public.scheduled_job_executions USING btree (execution_start);


--
-- Name: idx_scheduled_job_executions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_job_executions_status ON public.scheduled_job_executions USING btree (status);


--
-- Name: idx_scheduled_jobs_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_jobs_entity ON public.scheduled_jobs USING btree (entity_type, entity_id);


--
-- Name: idx_scheduled_jobs_job_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_jobs_job_type ON public.scheduled_jobs USING btree (job_type);


--
-- Name: idx_scheduled_jobs_last_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_jobs_last_run ON public.scheduled_jobs USING btree (last_run_time);


--
-- Name: idx_scheduled_jobs_next_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_jobs_next_run ON public.scheduled_jobs USING btree (next_run_time);


--
-- Name: idx_scheduled_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scheduled_jobs_status ON public.scheduled_jobs USING btree (status);


--
-- Name: idx_sse_events_priority_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sse_events_priority_created ON public.sse_events USING btree (priority, created_at);


--
-- Name: idx_sse_events_type_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sse_events_type_created ON public.sse_events USING btree (event_type, created_at);


--
-- Name: idx_sse_events_unprocessed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sse_events_unprocessed ON public.sse_events USING btree (created_at, processed_at) WHERE (processed_at IS NULL);


--
-- Name: idx_thumbnail_jobs_cleanup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_thumbnail_jobs_cleanup ON public.thumbnail_generation_jobs USING btree (status, completed_at);


--
-- Name: idx_thumbnail_jobs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_thumbnail_jobs_created_at ON public.thumbnail_generation_jobs USING btree (created_at);


--
-- Name: idx_thumbnail_jobs_image_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_thumbnail_jobs_image_id ON public.thumbnail_generation_jobs USING btree (image_id);


--
-- Name: idx_thumbnail_jobs_status_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_thumbnail_jobs_status_priority ON public.thumbnail_generation_jobs USING btree (status, priority, created_at);


--
-- Name: idx_timelapse_overlays_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timelapse_overlays_active ON public.timelapse_overlays USING btree (timelapse_id) INCLUDE (preset_id, enabled) WHERE (enabled = true);


--
-- Name: idx_timelapse_overlays_config_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timelapse_overlays_config_gin ON public.timelapse_overlays USING gin (overlay_config);


--
-- Name: idx_timelapses_scheduling; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timelapses_scheduling ON public.timelapses USING btree (status, capture_interval_seconds);


--
-- Name: idx_video_jobs_status_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_jobs_status_created ON public.video_generation_jobs USING btree (status, created_at);


--
-- Name: idx_video_jobs_timelapse_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_jobs_timelapse_id ON public.video_generation_jobs USING btree (timelapse_id);


--
-- Name: idx_video_jobs_trigger_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_video_jobs_trigger_type ON public.video_generation_jobs USING btree (trigger_type);


--
-- Name: idx_weather_date_fetched; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weather_date_fetched ON public.weather_data USING btree (weather_date_fetched);


--
-- Name: ix_sse_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sse_events_created_at ON public.sse_events USING btree (created_at);


--
-- Name: ix_sse_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sse_events_event_type ON public.sse_events USING btree (event_type);


--
-- Name: ix_sse_events_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sse_events_priority ON public.sse_events USING btree (priority);


--
-- Name: ix_sse_events_processed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sse_events_processed_at ON public.sse_events USING btree (processed_at);


--
-- Name: sse_events sse_events_notify_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER sse_events_notify_trigger AFTER INSERT ON public.sse_events FOR EACH ROW EXECUTE FUNCTION public.notify_sse_event();


--
-- Name: cameras update_cameras_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_cameras_updated_at BEFORE UPDATE ON public.cameras FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: images update_images_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_images_updated_at BEFORE UPDATE ON public.images FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: settings update_settings_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON public.settings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: timelapses update_timelapses_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_timelapses_updated_at BEFORE UPDATE ON public.timelapses FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: videos update_videos_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON public.videos FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: corruption_logs corruption_logs_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corruption_logs
    ADD CONSTRAINT corruption_logs_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: corruption_logs corruption_logs_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corruption_logs
    ADD CONSTRAINT corruption_logs_image_id_fkey FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


--
-- Name: cameras fk_active_timelapse; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT fk_active_timelapse FOREIGN KEY (active_timelapse_id) REFERENCES public.timelapses(id) ON DELETE SET NULL;


--
-- Name: images images_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: images images_timelapse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_timelapse_id_fkey FOREIGN KEY (timelapse_id) REFERENCES public.timelapses(id) ON DELETE CASCADE;


--
-- Name: logs logs_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.logs
    ADD CONSTRAINT logs_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE SET NULL;


--
-- Name: overlay_generation_jobs overlay_generation_jobs_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overlay_generation_jobs
    ADD CONSTRAINT overlay_generation_jobs_image_id_fkey FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


--
-- Name: scheduled_job_executions scheduled_job_executions_scheduled_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scheduled_job_executions
    ADD CONSTRAINT scheduled_job_executions_scheduled_job_id_fkey FOREIGN KEY (scheduled_job_id) REFERENCES public.scheduled_jobs(id) ON DELETE CASCADE;


--
-- Name: thumbnail_generation_jobs thumbnail_generation_jobs_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.thumbnail_generation_jobs
    ADD CONSTRAINT thumbnail_generation_jobs_image_id_fkey FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


--
-- Name: timelapse_overlays timelapse_overlays_preset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapse_overlays
    ADD CONSTRAINT timelapse_overlays_preset_id_fkey FOREIGN KEY (preset_id) REFERENCES public.overlay_presets(id) ON DELETE SET NULL;


--
-- Name: timelapse_overlays timelapse_overlays_timelapse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapse_overlays
    ADD CONSTRAINT timelapse_overlays_timelapse_id_fkey FOREIGN KEY (timelapse_id) REFERENCES public.timelapses(id) ON DELETE CASCADE;


--
-- Name: timelapses timelapses_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timelapses
    ADD CONSTRAINT timelapses_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: video_generation_jobs video_generation_jobs_timelapse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_generation_jobs
    ADD CONSTRAINT video_generation_jobs_timelapse_id_fkey FOREIGN KEY (timelapse_id) REFERENCES public.timelapses(id) ON DELETE CASCADE;


--
-- Name: video_generation_jobs video_generation_jobs_video_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_generation_jobs
    ADD CONSTRAINT video_generation_jobs_video_id_fkey FOREIGN KEY (video_id) REFERENCES public.videos(id) ON DELETE SET NULL;


--
-- Name: videos videos_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: videos videos_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.video_generation_jobs(id) ON DELETE SET NULL;


--
-- Name: videos videos_timelapse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_timelapse_id_fkey FOREIGN KEY (timelapse_id) REFERENCES public.timelapses(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

