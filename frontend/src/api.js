const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("access_token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || data.detail || "Request failed";
    throw new Error(message);
  }
  return data;
}

