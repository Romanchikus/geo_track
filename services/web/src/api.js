export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body, timeoutMs } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    cache: "no-store",
    signal: timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return null;
  const text = await response.text();
  const data = parseBody(text);
  if (!response.ok) {
    throw new ApiError(response.status, messageFrom(data, text || response.statusText));
  }
  return data;
}

export async function apiBytes(path) {
  const response = await fetch(`/api${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    const data = parseBody(text);
    throw new ApiError(response.status, messageFrom(data, text || response.statusText));
  }
  return response.arrayBuffer();
}

export async function fetchAll(path) {
  const rows = [];
  const limit = 100;
  for (let offset = 0; offset < 2000; offset += limit) {
    const page = await api(`${path}?limit=${limit}&offset=${offset}`);
    rows.push(...page);
    if (page.length < limit) return { rows, truncated: false };
  }
  return { rows, truncated: true };
}

function parseBody(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function messageFrom(data, fallback) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => (typeof item?.msg === "string" ? item.msg : "")).filter(Boolean);
    if (messages.length) return messages.join(", ");
  }
  if (typeof fallback === "string" && !fallback.includes("coordinates") && fallback.length < 200) return fallback;
  return "Request failed";
}
