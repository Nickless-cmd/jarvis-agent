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
  let data: T | null = null;
  try {
    data = (await res.json()) as T;
  } catch {
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
