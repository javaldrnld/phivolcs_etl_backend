--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: intensities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.intensities (
    intensity_id integer NOT NULL,
    eq_id integer NOT NULL,
    intensity_type character varying(20),
    intensity_value character varying(10),
    location text
);


--
-- Name: intensities_intensity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.intensities_intensity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: intensities_intensity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.intensities_intensity_id_seq OWNED BY public.intensities.intensity_id;


--
-- Name: seismic_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seismic_event (
    eq_id integer NOT NULL,
    eq_business_key character varying(50),
    eq_no integer,
    datetime timestamp without time zone,
    latitude_str character varying(20),
    longitude_str character varying(30),
    latitude numeric(10,8),
    longitude numeric(11,8),
    region text,
    location text,
    municipality text,
    province text,
    depth_km numeric(6,2),
    depth_str character varying(6),
    origin text,
    magnitude_type character varying(10),
    magnitude_value numeric(3,2),
    magnitude_str text,
    filename text,
    issued_datetime timestamp without time zone,
    authors json,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: seismic_event_eq_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seismic_event_eq_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seismic_event_eq_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seismic_event_eq_id_seq OWNED BY public.seismic_event.eq_id;


--
-- Name: intensities intensity_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intensities ALTER COLUMN intensity_id SET DEFAULT nextval('public.intensities_intensity_id_seq'::regclass);


--
-- Name: seismic_event eq_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seismic_event ALTER COLUMN eq_id SET DEFAULT nextval('public.seismic_event_eq_id_seq'::regclass);


--
-- Name: intensities intensities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intensities
    ADD CONSTRAINT intensities_pkey PRIMARY KEY (intensity_id);


--
-- Name: seismic_event seismic_event_eq_business_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seismic_event
    ADD CONSTRAINT seismic_event_eq_business_key_key UNIQUE (eq_business_key);


--
-- Name: seismic_event seismic_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seismic_event
    ADD CONSTRAINT seismic_event_pkey PRIMARY KEY (eq_id);


--
-- Name: idx_datetime_province; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_datetime_province ON public.seismic_event USING btree (datetime, province);


--
-- Name: idx_lat_lon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lat_lon ON public.seismic_event USING btree (latitude, longitude);


--
-- Name: idx_magnitudevalue_datetime; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_magnitudevalue_datetime ON public.seismic_event USING btree (magnitude_value, datetime);


--
-- Name: idx_origin_province; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_origin_province ON public.seismic_event USING btree (origin, province);


--
-- Name: idx_province_datetime; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_province_datetime ON public.seismic_event USING btree (province, datetime);


--
-- Name: ix_seismic_event_datetime; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seismic_event_datetime ON public.seismic_event USING btree (datetime);


--
-- Name: ix_seismic_event_latitude; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seismic_event_latitude ON public.seismic_event USING btree (latitude);


--
-- Name: ix_seismic_event_longitude; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seismic_event_longitude ON public.seismic_event USING btree (longitude);


--
-- Name: ix_seismic_event_magnitude_value; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seismic_event_magnitude_value ON public.seismic_event USING btree (magnitude_value);


--
-- Name: ix_seismic_event_origin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seismic_event_origin ON public.seismic_event USING btree (origin);


--
-- Name: ix_seismic_event_province; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seismic_event_province ON public.seismic_event USING btree (province);


--
-- Name: intensities intensities_eq_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intensities
    ADD CONSTRAINT intensities_eq_id_fkey FOREIGN KEY (eq_id) REFERENCES public.seismic_event(eq_id);


--
-- PostgreSQL database dump complete
--

