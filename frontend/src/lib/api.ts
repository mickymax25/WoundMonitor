import type {
  PatientResponse,
  PatientCreate,
  AssessmentResponse,
  AnalysisResult,
  TrajectoryPoint,
  Referral,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch {
      // Could not parse error body
    }
    throw new ApiError(message, res.status);
  }

  return res.json() as Promise<T>;
}

export async function listPatients(): Promise<PatientResponse[]> {
  return request<PatientResponse[]>("/api/v1/patients");
}

export async function createPatient(
  data: PatientCreate
): Promise<PatientResponse> {
  return request<PatientResponse>("/api/v1/patients", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getPatient(
  id: string
): Promise<PatientResponse> {
  return request<PatientResponse>(`/api/v1/patients/${id}`);
}

export async function createAssessment(
  patientId: string,
  image: File,
  additionalImages?: File[],
  audio?: File,
  visitDate?: string,
  textNotes?: string
): Promise<AssessmentResponse> {
  const formData = new FormData();
  formData.append("patient_id", patientId);
  formData.append("image", image);
  if (additionalImages) {
    for (const img of additionalImages) {
      formData.append("additional_images", img);
    }
  }
  if (audio) {
    formData.append("audio", audio);
  }
  if (visitDate) {
    formData.append("visit_date", visitDate);
  }
  if (textNotes) {
    formData.append("text_notes", textNotes);
  }

  return request<AssessmentResponse>("/api/v1/assessments", {
    method: "POST",
    body: formData,
  });
}

export async function addAssessmentImages(
  assessmentId: string,
  images: File[]
): Promise<AssessmentResponse> {
  const formData = new FormData();
  for (const img of images) {
    formData.append("images", img);
  }
  return request<AssessmentResponse>(
    `/api/v1/assessments/${assessmentId}/images`,
    { method: "POST", body: formData }
  );
}

export async function analyzeAssessment(
  id: string
): Promise<AnalysisResult> {
  return request<AnalysisResult>(
    `/api/v1/assessments/${id}/analyze`,
    { method: "POST" }
  );
}

export async function getAssessment(
  id: string
): Promise<AssessmentResponse> {
  return request<AssessmentResponse>(`/api/v1/assessments/${id}`);
}

export async function getTrajectory(
  patientId: string
): Promise<TrajectoryPoint[]> {
  return request<TrajectoryPoint[]>(
    `/api/v1/patients/${patientId}/trajectory`
  );
}

export async function listPatientAssessments(
  patientId: string
): Promise<AssessmentResponse[]> {
  return request<AssessmentResponse[]>(
    `/api/v1/patients/${patientId}/assessments`
  );
}

export async function createReferral(data: {
  assessment_id: string;
  patient_id: string;
  urgency: string;
  physician_name?: string;
  physician_contact?: string;
  referral_notes?: string;
}): Promise<Referral> {
  return request<Referral>("/api/v1/referrals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function getReferralSummaryUrl(referralId: string): string {
  return `${API_BASE}/api/v1/referrals/${referralId}/summary`;
}

// ---------------------------------------------------------------------------
// Patient self-reporting
// ---------------------------------------------------------------------------

export async function getPatientReportInfo(
  token: string
): Promise<{ patient_name: string; wound_type: string | null; wound_location: string | null }> {
  return request(`/api/v1/patient-report/${token}/info`);
}

export async function submitPatientReport(
  token: string,
  image: File,
  note?: string
): Promise<{ assessment_id: string; message: string }> {
  const formData = new FormData();
  formData.append("image", image);
  if (note) {
    formData.append("note", note);
  }
  return request(`/api/v1/patient-report/${token}`, {
    method: "POST",
    body: formData,
  });
}

export { ApiError };
