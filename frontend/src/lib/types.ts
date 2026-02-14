export interface PatientCreate {
  name: string;
  age?: number | null;
  wound_type?: string | null;
  wound_location?: string | null;
  comorbidities?: string[];
}

export interface PatientResponse {
  id: string;
  name: string;
  age: number | null;
  wound_type: string | null;
  wound_location: string | null;
  comorbidities: string[];
  created_at: string;
  latest_trajectory: string | null;
  latest_alert_level: string | null;
  assessment_count: number;
}

export interface TimeScore {
  type: string;
  score: number;
}

export interface TimeClassification {
  tissue: TimeScore;
  inflammation: TimeScore;
  moisture: TimeScore;
  edge: TimeScore;
}

export interface AssessmentResponse {
  id: string;
  patient_id: string;
  visit_date: string;
  image_path: string;
  time_classification: TimeClassification | null;
  zeroshot_scores: Record<string, number> | null;
  nurse_notes: string | null;
  change_score: number | null;
  trajectory: string | null;
  contradiction_flag: boolean;
  contradiction_detail: string | null;
  report_text: string | null;
  alert_level: string | null;
  alert_detail: string | null;
  created_at: string;
}

export interface AnalysisResult {
  assessment_id: string;
  time_classification: TimeClassification;
  zeroshot_scores: Record<string, number>;
  trajectory: string;
  change_score: number | null;
  contradiction_flag: boolean;
  contradiction_detail: string | null;
  report_text: string;
  alert_level: string;
  alert_detail: string | null;
}

export interface TrajectoryPoint {
  visit_date: string;
  tissue_score: number | null;
  inflammation_score: number | null;
  moisture_score: number | null;
  edge_score: number | null;
  trajectory: string | null;
  change_score: number | null;
}

export type WoundType =
  | "diabetic_ulcer"
  | "pressure_ulcer"
  | "venous_ulcer"
  | "other";

export type WoundLocation =
  | "left_foot"
  | "right_foot"
  | "sacrum"
  | "leg"
  | "other";

export const WOUND_TYPES: { value: WoundType; label: string }[] = [
  { value: "diabetic_ulcer", label: "Diabetic Ulcer" },
  { value: "pressure_ulcer", label: "Pressure Ulcer" },
  { value: "venous_ulcer", label: "Venous Ulcer" },
  { value: "other", label: "Other" },
];

export const WOUND_LOCATIONS: { value: WoundLocation; label: string }[] = [
  { value: "left_foot", label: "Left Foot" },
  { value: "right_foot", label: "Right Foot" },
  { value: "sacrum", label: "Sacrum" },
  { value: "leg", label: "Leg" },
  { value: "other", label: "Other" },
];

export type MobileTab = "patients" | "assessment" | "timeline" | "report";
