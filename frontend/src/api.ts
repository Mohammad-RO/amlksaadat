import type { Agent, Listing, Report, Role } from "./types";

const TOKEN_KEY = "amlak_token";

export class ApiError extends Error {}

export function token() {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(value: string) {
  localStorage.setItem(TOKEN_KEY, value);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  const current = token();
  if (current) headers.set("Authorization", `Bearer ${current}`);
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : "خطا در ارتباط با سرور";
    throw new ApiError(detail);
  }
  return body as T;
}

export async function loginAdmin(username: string, password: string) {
  const data = await request<{ token: string; role: Role; name: string }>("/auth/admin", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  saveToken(data.token);
  return data;
}

export async function loginAgent(phone: string) {
  const data = await request<{ token: string; role: Role; name: string }>("/auth/agent", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
  saveToken(data.token);
  return data;
}

export async function currentSession() {
  return request<{ role: Role; name: string }>("/auth/me");
}

export async function listAgents() {
  return request<Agent[]>("/admin/agents");
}

export async function createAgent(name: string, phone: string) {
  return request<Agent>("/admin/agents", {
    method: "POST",
    body: JSON.stringify({ name, phone }),
  });
}

export async function updateAgent(id: number, payload: Partial<Pick<Agent, "name" | "phone" | "is_active">>) {
  return request<Agent>(`/admin/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function loadReport(dateFrom: string, dateTo: string) {
  const params = new URLSearchParams();
  if (dateFrom) params.set("from", dateFrom);
  if (dateTo) params.set("to", dateTo);
  const query = params.toString();
  return request<Report>(`/admin/reports${query ? `?${query}` : ""}`);
}

export async function systemHealth() {
  return request<{ ok: boolean; bot_configured: boolean; archive_configured: boolean }>("/health");
}

export async function myListings() {
  return request<Listing[]>("/listings");
}

export async function createListing(divarUrl: string) {
  return request<Listing>("/listings", {
    method: "POST",
    body: JSON.stringify({ divar_url: divarUrl }),
  });
}

export async function deleteListing(id: number) {
  return request<void>(`/listings/${id}`, { method: "DELETE" });
}
