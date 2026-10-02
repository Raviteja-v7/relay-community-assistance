import { getAccessToken, localSubject } from './auth';

export type RequestCategory =
  | 'water'
  | 'food'
  | 'transport'
  | 'pharmacy'
  | 'mobility'
  | 'supplies'
  | 'other';

export type RequestUrgency = 'normal' | 'high' | 'urgent';
export type RequestStatus = 'REQUESTED' | 'CLAIMED' | 'IN_PROGRESS' | 'VOLUNTEER_COMPLETED' | 'REQUESTER_CONFIRMED' | 'RESOLVED';

export interface AssistanceRequest {
  id: string;
  description: string;
  category: RequestCategory;
  urgency: RequestUrgency;
  location: { label: string; latitude?: number; longitude?: number };
  peopleAffected: number;
  status: RequestStatus;
  createdAt: string;
  summary?: string | null;
  requiredSkills?: string[];
  mobilityNeeds?: string;
  isStructured?: boolean;
  claimedBy?: string | null;
  isRequester?: boolean;
  isClaimedByYou?: boolean;
  volunteerCompletedAt?: string | null;
  requesterConfirmedAt?: string | null;
  statusHistory?: string[];
  resolvedAt?: string | null;
}

export interface StructuredRequest {
  category: RequestCategory;
  urgency: RequestUrgency;
  peopleAffected: number;
  requiredSkills: string[];
  mobilityNeeds: 'none' | 'limited' | 'significant' | 'unknown';
  summary: string;
}

export interface Volunteer {
  id: string;
  name: string;
  role: 'REQUESTER' | 'VOLUNTEER' | 'COORDINATOR';
  location: { label: string; latitude?: number; longitude?: number };
  skills: string[];
  availability: 'AVAILABLE' | 'BUSY' | 'OFFLINE';
  activeRequests: number;
  createdAt: string | null;
}

export interface VolunteerMatch {
  volunteerId: string;
  name: string;
  availability: Volunteer['availability'];
  score: number;
  reasons: string[];
  distanceKm: number | null;
  scoreBreakdown: {
    skillMatch: number;
    availability: number;
    proximity: number;
    workload: number;
    urgencySuitability: number;
  };
}

export interface CreateRequestInput {
  description: string;
  category: RequestCategory;
  urgency: RequestUrgency;
  location: { label: string; latitude?: number; longitude?: number };
  peopleAffected: number;
  requiredSkills: string[];
  mobilityNeeds: StructuredRequest['mobilityNeeds'];
  summary: string;
}

export interface CommunityProfile {
  id: string;
  name: string;
  roles: Array<'REQUESTER' | 'VOLUNTEER'>;
  createdAt: string;
}

export interface VolunteerProfile {
  id: string;
  name: string;
  role: 'VOLUNTEER';
  location: { label: string };
  skills: string[];
  availability: Volunteer['availability'];
  activeRequests: number;
  createdAt: string | null;
}

const API_BASE = window.RELAY_CONFIG?.apiBaseUrl || import.meta.env.VITE_API_BASE_URL || '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(token ? { authorization: `Bearer ${token}` } : { 'x-relay-local-sub': localSubject() }),
      ...init?.headers,
    },
  });
  const body = (await response.json()) as T | { message?: string };
  if (!response.ok) {
    const message = typeof body === 'object' && body !== null && 'message' in body && typeof body.message === 'string'
      ? body.message
      : 'Something went wrong. Please try again.';
    throw new Error(message);
  }
  return body as T;
}

export const relayApi = {
  listRequests: async () => (await request<{ requests: AssistanceRequest[] }>('/requests')).requests,
  getRequest: (requestId: string) => request<AssistanceRequest>(`/requests/${requestId}`),
  listVolunteers: async () => (await request<{ volunteers: Volunteer[] }>('/volunteers')).volunteers,
  structureRequest: (description: string) =>
    request<StructuredRequest>('/requests/structure', { method: 'POST', body: JSON.stringify({ description }) }),
  createRequest: (input: CreateRequestInput) =>
    request<AssistanceRequest>('/requests', { method: 'POST', body: JSON.stringify(input) }),
  findMatches: async (requestId: string) =>
    (await request<{ requestId: string; matches: VolunteerMatch[] }>(`/requests/${requestId}/matches`, { method: 'POST', body: '{}' })).matches,
  claimRequest: (requestId: string) =>
    request<AssistanceRequest>(`/requests/${requestId}/claim`, { method: 'POST', body: '{}' }),
  updateStatus: (requestId: string, status: RequestStatus) =>
    request<AssistanceRequest>(`/requests/${requestId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  confirmRequest: (requestId: string) =>
    request<AssistanceRequest>(`/requests/${requestId}/confirm`, { method: 'POST', body: '{}' }),
  getProfile: () => request<CommunityProfile>('/me'),
  saveProfile: (input: { name: string; roles: CommunityProfile['roles'] }) =>
    request<CommunityProfile>('/me', { method: 'PUT', body: JSON.stringify(input) }),
  getVolunteerProfile: () => request<VolunteerProfile>('/me/volunteer'),
  saveVolunteerProfile: (input: { location: Volunteer['location']; skills: string[]; availability: Volunteer['availability'] }) =>
    request<VolunteerProfile>('/me/volunteer', { method: 'PUT', body: JSON.stringify(input) }),
  blockUser: (userId: string) => request<{ blockedUserId: string }>(`/users/${encodeURIComponent(userId)}/block`, { method: 'POST', body: '{}' }),
  unblockUser: (userId: string) => request<void>(`/users/${encodeURIComponent(userId)}/block`, { method: 'DELETE' }),
  listBlocks: async () => (await request<{ userIds: string[] }>('/me/blocks')).userIds,
  report: (targetType: 'REQUEST' | 'USER', targetId: string, reason: string, details: string) =>
    request<{ id: string; createdAt: string }>('/reports', { method: 'POST', body: JSON.stringify({ targetType, targetId, reason, details }) }),
};
