export interface RelayAuthConfig {
  userPoolId?: string;
  userPoolClientId?: string;
  cognitoDomain?: string;
}

declare global {
  interface Window {
    RELAY_CONFIG?: { apiBaseUrl?: string } & RelayAuthConfig;
  }
}

const accessTokenKey = 'relay.cognito.access-token';
const refreshTokenKey = 'relay.cognito.refresh-token';
const localSubjectKey = 'relay.local.subject';
const verifierKey = 'relay.cognito.pkce-verifier';
const stateKey = 'relay.cognito.oauth-state';

export function authConfig(): RelayAuthConfig {
  return {
    userPoolId: window.RELAY_CONFIG?.userPoolId || import.meta.env.VITE_COGNITO_USER_POOL_ID,
    userPoolClientId: window.RELAY_CONFIG?.userPoolClientId || import.meta.env.VITE_COGNITO_CLIENT_ID,
    cognitoDomain: window.RELAY_CONFIG?.cognitoDomain || import.meta.env.VITE_COGNITO_DOMAIN,
  };
}

export function cognitoEnabled(): boolean {
  const config = authConfig();
  return Boolean(config.userPoolId && config.userPoolClientId && config.cognitoDomain);
}

export function accessToken(): string | null {
  const token = sessionStorage.getItem(accessTokenKey);
  return token && tokenExpiry(token) > Date.now() / 1000 + 30 ? token : null;
}

export async function getAccessToken(): Promise<string | null> {
  const valid = accessToken();
  if (valid) return valid;
  const refreshToken = sessionStorage.getItem(refreshTokenKey);
  const config = authConfig();
  if (!refreshToken || !config.cognitoDomain || !config.userPoolClientId) return null;
  const response = await fetch(new URL('/oauth2/token', normalizeDomain(config.cognitoDomain)), {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'refresh_token', client_id: config.userPoolClientId, refresh_token: refreshToken }),
  });
  if (!response.ok) {
    sessionStorage.removeItem(accessTokenKey);
    sessionStorage.removeItem(refreshTokenKey);
    return null;
  }
  const tokens = await response.json() as { access_token: string };
  sessionStorage.setItem(accessTokenKey, tokens.access_token);
  return tokens.access_token;
}

export function localSubject(): string {
  return sessionStorage.getItem(localSubjectKey) || 'local-requester';
}

export function setLocalSubject(subject: string): void {
  sessionStorage.setItem(localSubjectKey, subject);
}

export function currentSubject(): string | null {
  const token = accessToken();
  if (token) {
    try {
      const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(atob(payload)).sub as string;
    } catch {
      return null;
    }
  }
  return localSubject();
}

export async function startSignIn(): Promise<void> {
  const config = authConfig();
  if (!config.cognitoDomain || !config.userPoolClientId) throw new Error('Cognito sign-in is not configured.');
  const verifier = randomUrlSafe(64);
  const state = randomUrlSafe(32);
  sessionStorage.setItem(verifierKey, verifier);
  sessionStorage.setItem(stateKey, state);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  const challenge = encodeUrlSafe(new Uint8Array(digest));
  const url = new URL('/oauth2/authorize', normalizeDomain(config.cognitoDomain));
  url.search = new URLSearchParams({
    response_type: 'code',
    client_id: config.userPoolClientId,
    redirect_uri: window.location.origin + '/',
    scope: 'openid email profile',
    code_challenge_method: 'S256',
    code_challenge: challenge,
    state,
  }).toString();
  window.location.assign(url.toString());
}

export function signOut(): void {
  const config = authConfig();
  sessionStorage.removeItem(accessTokenKey);
  sessionStorage.removeItem(refreshTokenKey);
  if (config.cognitoDomain && config.userPoolClientId) {
    const url = new URL('/logout', normalizeDomain(config.cognitoDomain));
    url.search = new URLSearchParams({
      client_id: config.userPoolClientId,
      logout_uri: window.location.origin + '/',
    }).toString();
    window.location.assign(url.toString());
  } else {
    window.location.reload();
  }
}

export async function completeSignIn(): Promise<boolean> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  if (!code) return false;
  const config = authConfig();
  const state = params.get('state');
  const expectedState = sessionStorage.getItem(stateKey);
  const verifier = sessionStorage.getItem(verifierKey);
  if (!config.cognitoDomain || !config.userPoolClientId || !verifier || !state || state !== expectedState) {
    throw new Error('Sign-in could not be verified. Please try again.');
  }
  const response = await fetch(new URL('/oauth2/token', normalizeDomain(config.cognitoDomain)), {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: config.userPoolClientId,
      code,
      redirect_uri: window.location.origin + '/',
      code_verifier: verifier,
    }),
  });
  if (!response.ok) throw new Error('Cognito sign-in could not be completed. Please try again.');
  const tokens = await response.json() as { access_token: string; refresh_token?: string; expires_in: number };
  sessionStorage.setItem(accessTokenKey, tokens.access_token);
  if (tokens.refresh_token) sessionStorage.setItem(refreshTokenKey, tokens.refresh_token);
  sessionStorage.removeItem(verifierKey);
  sessionStorage.removeItem(stateKey);
  window.history.replaceState({}, document.title, window.location.pathname);
  return true;
}

function tokenExpiry(token: string): number {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(payload)).exp as number;
  } catch {
    return 0;
  }
}

function normalizeDomain(domain: string): string {
  return domain.startsWith('http') ? domain : `https://${domain}`;
}

function randomUrlSafe(size: number): string {
  const bytes = crypto.getRandomValues(new Uint8Array(size));
  return encodeUrlSafe(bytes);
}

function encodeUrlSafe(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
