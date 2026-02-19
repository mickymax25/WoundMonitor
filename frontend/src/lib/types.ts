export interface PatientCreate {
  name: string;
  age?: number | null;
  sex?: string | null;
  phone?: string | null;
  wound_type?: string | null;
  wound_location?: string | null;
  comorbidities?: string[];
  referring_physician?: string | null;
  referring_physician_specialty?: string | null;
  referring_physician_facility?: string | null;
  referring_physician_phone?: string | null;
  referring_physician_email?: string | null;
  referring_physician_preferred_contact?: string | null;
}

export interface PatientResponse {
  id: string;
  name: string;
  age: number | null;
  sex: string | null;
  phone: string | null;
  wound_type: string | null;
  wound_location: string | null;
  comorbidities: string[];
  referring_physician: string | null;
  referring_physician_specialty: string | null;
  referring_physician_facility: string | null;
  referring_physician_phone: string | null;
  referring_physician_email: string | null;
  referring_physician_preferred_contact: string | null;
  patient_token: string;
  created_at: string;
  latest_trajectory: string | null;
  latest_alert_level: string | null;
  assessment_count: number;
  patient_reported_count: number;
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

export interface AssessmentImage {
  id: string;
  image_path: string;
  is_primary: boolean;
  caption: string | null;
  created_at: string;
}

export interface AssessmentResponse {
  id: string;
  patient_id: string;
  visit_date: string;
  image_path: string;
  source: string;
  audio_path: string | null;
  text_notes: string | null;
  images: AssessmentImage[];
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
  healing_comment: string | null;
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
  healing_comment: string | null;
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
  | "thermal_burn"
  | "chemical_burn"
  | "electrical_burn"
  | "other";

export type WoundLocation =
  | "left_foot"
  | "right_foot"
  | "left_heel"
  | "right_heel"
  | "sacrum"
  | "coccyx"
  | "left_ischium"
  | "right_ischium"
  | "left_trochanter"
  | "right_trochanter"
  | "occiput"
  | "left_leg"
  | "right_leg"
  | "hand"
  | "arm"
  | "torso"
  | "face"
  | "other";

export const WOUND_TYPES: { value: WoundType; label: string }[] = [
  { value: "diabetic_ulcer", label: "Diabetic Ulcer" },
  { value: "pressure_ulcer", label: "Pressure Ulcer" },
  { value: "venous_ulcer", label: "Venous Ulcer" },
  { value: "thermal_burn", label: "Thermal Burn" },
  { value: "chemical_burn", label: "Chemical Burn" },
  { value: "electrical_burn", label: "Electrical Burn" },
  { value: "other", label: "Other" },
];

export const WOUND_LOCATIONS: { value: WoundLocation; label: string }[] = [
  { value: "sacrum", label: "Sacrum" },
  { value: "coccyx", label: "Coccyx" },
  { value: "left_heel", label: "Left Heel" },
  { value: "right_heel", label: "Right Heel" },
  { value: "left_ischium", label: "Left Ischium" },
  { value: "right_ischium", label: "Right Ischium" },
  { value: "left_trochanter", label: "Left Trochanter" },
  { value: "right_trochanter", label: "Right Trochanter" },
  { value: "occiput", label: "Occiput" },
  { value: "left_foot", label: "Left Foot" },
  { value: "right_foot", label: "Right Foot" },
  { value: "left_leg", label: "Left Leg" },
  { value: "right_leg", label: "Right Leg" },
  { value: "hand", label: "Hand" },
  { value: "arm", label: "Arm" },
  { value: "torso", label: "Torso" },
  { value: "face", label: "Face / Neck" },
  { value: "other", label: "Other" },
];

export interface Referral {
  id: string;
  assessment_id: string;
  patient_id: string;
  urgency: "routine" | "urgent" | "emergency";
  physician_name: string | null;
  physician_contact: string | null;
  referral_notes: string | null;
  status: "pending" | "sent" | "reviewed";
  created_at: string;
}

export type MobileTab = "patients" | "reports" | "settings";
