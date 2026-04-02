const TOKEN_KEY = "mockwithus_access_token";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

function readAccessTokenCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${TOKEN_KEY}=`));

  if (!cookie) {
    return null;
  }

  return decodeURIComponent(cookie.substring(TOKEN_KEY.length + 1)) || null;
}

function writeAccessTokenCookie(token: string): void {
  if (typeof document === "undefined") {
    return;
  }

  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; Path=/; Max-Age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax${secure}`;
}

function clearAccessTokenCookie(): void {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const localStorageToken = window.localStorage.getItem(TOKEN_KEY);
  if (localStorageToken) {
    return localStorageToken;
  }

  const cookieToken = readAccessTokenCookie();
  if (cookieToken) {
    window.localStorage.setItem(TOKEN_KEY, cookieToken);
  }

  return cookieToken;
}

export function setAccessToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(TOKEN_KEY, token);
  writeAccessTokenCookie(token);
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(TOKEN_KEY);
  clearAccessTokenCookie();
}
