const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8040";

export async function api<T>(
  path: string,
  init: RequestInit & {token?: string} = {},
): Promise<T> {
  const {token, ...rest} = init;
  const r = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? {Authorization: `Bearer ${token}`} : {}),
      ...(rest.headers || {}),
    },
    cache: "no-store",
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`API ${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}