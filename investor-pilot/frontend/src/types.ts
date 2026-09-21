export interface WellLogSample {
  well_id: string;

  depth_m: number;

  gamma_ray_api: number;

  resistivity_ohmm: number;

  density_gcc: number;

  neutron_porosity_vv: number;

  sonic_usft: number;

  caliper_in: number;

  lithology?: string;

  hydrocarbon_probability?: number;

  facies?: string;

  porosity?: number;

  water_saturation?: number;

  permeability_md?: number;

  qc_score?: number;

  anomaly_score?: number;

  is_anomaly?: boolean;
};

export type AnalyticsResult = {
  input: WellLogSample;
  qc_score: number;
  hydrocarbon_probability: number;
  lithology: string;
  facies: string;
  anomaly_score: number;
  is_anomaly: boolean;
  porosity: number;
  water_saturation: number;
  shale_volume: number;
  net_to_gross: number;
  permeability_md: number;
  explanation: Record<string, string | number>;
};

export type Alert = {
  id: string;
  severity: string;
  well_id: string;
  message: string;
  created_at: string;
  acknowledged: boolean;
};

