CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES organizations(id),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  mfa_secret TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS user_roles (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS wells (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES organizations(id),
  well_id TEXT UNIQUE NOT NULL,
  field_name TEXT NOT NULL,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  kb_m DOUBLE PRECISION,
  total_depth_m DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS log_samples (
  time TIMESTAMPTZ NOT NULL,
  well_id TEXT NOT NULL REFERENCES wells(well_id),
  depth_m DOUBLE PRECISION NOT NULL,
  gamma_ray_api DOUBLE PRECISION,
  resistivity_ohmm DOUBLE PRECISION,
  density_gcc DOUBLE PRECISION,
  neutron_porosity_vv DOUBLE PRECISION,
  sonic_usft DOUBLE PRECISION,
  caliper_in DOUBLE PRECISION,
  source_type TEXT NOT NULL,
  PRIMARY KEY (well_id, depth_m, time)
);

SELECT create_hypertable('log_samples', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS analytics_results (
  time TIMESTAMPTZ NOT NULL,
  well_id TEXT NOT NULL REFERENCES wells(well_id),
  depth_m DOUBLE PRECISION NOT NULL,
  qc_score DOUBLE PRECISION NOT NULL,
  hydrocarbon_probability DOUBLE PRECISION NOT NULL,
  lithology TEXT NOT NULL,
  facies TEXT NOT NULL,
  anomaly_score DOUBLE PRECISION NOT NULL,
  porosity DOUBLE PRECISION NOT NULL,
  water_saturation DOUBLE PRECISION NOT NULL,
  shale_volume DOUBLE PRECISION NOT NULL,
  net_to_gross DOUBLE PRECISION NOT NULL,
  permeability_md DOUBLE PRECISION NOT NULL,
  explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (well_id, depth_m, time)
);

SELECT create_hypertable('analytics_results', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  well_id TEXT NOT NULL REFERENCES wells(well_id),
  severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  message TEXT NOT NULL,
  acknowledged BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_name TEXT NOT NULL,
  version TEXT NOT NULL,
  framework TEXT NOT NULL,
  mlflow_run_id TEXT,
  status TEXT NOT NULL DEFAULT 'staging',
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_name, version)
);

INSERT INTO organizations (name)
VALUES ('PetroEdge Demo Organization')
ON CONFLICT DO NOTHING;

INSERT INTO roles (name)
VALUES ('admin'), ('geoscientist'), ('engineer'), ('viewer')
ON CONFLICT DO NOTHING;

INSERT INTO wells (well_id, field_name, latitude, longitude, kb_m, total_depth_m)
VALUES ('PETROEDGE-DEMO-01', 'Niger Delta Demo Field', 4.8156, 6.9814, 42.3, 3560.0)
ON CONFLICT (well_id) DO NOTHING;

