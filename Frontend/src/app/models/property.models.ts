export interface Property {
  district_id: number;
  district_name?: string | null;
  mandal_id: number;
  mandal_name?: string | null;
  village_id: number;
  village_name?: string | null;
  survey_no: string;
  khata_id?: number | null;
  khata_label?: number | null;
  pattadar_name_en?: string | null;
  father_or_husband_name_en?: string | null;
  ppb_number?: string | null;
  ekyc_status?: string | null;
  total_extent_ac_gts?: number | null;
  land_status?: string | null;
  land_type?: string | null;
  market_value_inr?: number | null;
}

export interface SearchResponse {
  count: number;
  results: Property[];
}
