export interface Profile {
  username: string;
  is_admin: boolean;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<{ data: T | null; status: number }> {
  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });
  const status = res.status;
  if (status === 204) return { data: null, status };
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  let data: T | null = null;
  if (isJson) {
    try {
      data = (await res.json()) as T;
    } catch (err) {
      console.warn('[fetchJson] failed to parse JSON', { status, path, contentType, err });
      data = null;
    }
  } else {
    const text = await res.text();
    console.warn('[fetchJson] non-JSON response', { status, path, contentType, sample: text?.slice(0, 200) });
    data = null;
  }
  return { data, status };
}

export async function loadProfile(): Promise<Profile | null> {
  const { data, status } = await fetchJson<Profile>("/account/profile");
  if (status === 200 && data) return data;
  return null;
}

export { fetchJson };
