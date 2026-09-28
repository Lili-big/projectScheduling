const apiBase = normalizeApiBase(import.meta.env.VITE_API_BASE_URL ?? "");
const DEFAULT_TIMEOUT_MS = 90_000;

export async function apiGet<T>(path: string): Promise<T> {
  const response = await apiFetch(path);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

export async function readNdjsonStream(body: ReadableStream<Uint8Array>, onValue: (value: unknown) => void): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let pending = "";
  const line = (value: string) => { if (value.trim()) onValue(JSON.parse(value)); };
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let end: number;
      while ((end = pending.indexOf("\n")) >= 0) {
        line(pending.slice(0, end));
        pending = pending.slice(end + 1);
      }
      if (done) { line(pending); break; }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function apiPostStream(path: string, payload: unknown, onValue: (value: unknown) => void,
  signal: AbortSignal, timeoutMs: number): Promise<void> {
  ensureApiBaseConfiguredForNetlify();
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  let timedOut = false;
  signal.addEventListener("abort", abort, { once: true });
  if (signal.aborted) abort();
  const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    const response = await fetch(`${apiBase}${path}`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload), signal: controller.signal });
    if (!response.ok) throw new Error(await responseErrorText(response));
    if (!response.body || !response.headers.get("content-type")?.includes("application/x-ndjson")) {
      throw new Error("后端未返回实时求解数据，请检查服务版本。");
    }
    await readNdjsonStream(response.body, onValue);
  } catch (error) {
    if (timedOut) throw new Error("实时求解连接超时，本次优化未完成；保留最后收到的方案。");
    throw error;
  } finally {
    window.clearTimeout(timer);
    signal.removeEventListener("abort", abort);
  }
}

export async function apiPut<T>(path: string, payload: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

export async function apiPostFormData<T>(path: string, payload: FormData): Promise<T> {
  const response = await apiFetch(path, {
    method: "POST",
    body: payload,
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

export async function apiGetBlob(path: string): Promise<Blob> {
  const response = await apiFetch(path);
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.blob();
}

async function apiFetch(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  ensureApiBaseConfiguredForNetlify();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(`${apiBase}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`接口请求超过 ${Math.round(timeoutMs / 1000)} 秒未返回，请检查后端服务是否卡住或重启服务。`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function normalizeApiBase(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function ensureApiBaseConfiguredForNetlify(): void {
  if (apiBase || !import.meta.env.PROD || !/\.netlify\.app$/i.test(window.location.hostname)) {
    return;
  }
  throw new Error("Netlify 生产环境未配置 VITE_API_BASE_URL，无法连接完整 FastAPI/OR-Tools 后端。");
}

async function responseErrorText(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (payload.detail && typeof payload.detail === "object") {
      const detail = payload.detail as { code?: unknown; message?: unknown };
      if (typeof detail.message === "string") {
        return typeof detail.code === "string" ? `${detail.message}（${detail.code}）` : detail.message;
      }
    }
    return text;
  } catch {
    return text;
  }
}
