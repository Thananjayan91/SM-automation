import { Platform } from 'react-native';

// Default host: 192.168.8.102 (LAN Wi-Fi IP for physical phones like Oppo), or 127.0.0.1 for local/web
const DEFAULT_HOST = Platform.OS === 'android' ? 'http://192.168.8.102:5000' : 'http://127.0.0.1:5000';

class ApiClient {
  private baseUrl: string = DEFAULT_HOST;
  private tenantId: string | null = null;
  private sessionCookie: string | null = null;

  public setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, '');
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  public setTenantId(id: string | null) {
    this.tenantId = id;
  }

  public getTenantId(): string | null {
    return this.tenantId;
  }

  public setSessionCookie(cookie: string | null) {
    this.sessionCookie = cookie;
  }

  public async request<T = any>(
    path: string,
    options: RequestInit = {}
  ): Promise<{ data: T | null; error: string | null; status: number }> {
    const url = `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.tenantId) {
      headers['X-Tenant-ID'] = this.tenantId;
    }

    if (this.sessionCookie) {
      headers['Cookie'] = this.sessionCookie;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',
      });

      // Capture session cookie from headers if returned
      const setCookie = response.headers.get('set-cookie');
      if (setCookie) {
        this.sessionCookie = setCookie.split(';')[0];
      }

      const text = await response.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = text;
      }

      if (!response.ok) {
        const errorMsg =
          (data && typeof data === 'object' && (data.message || data.error)) ||
          `Request failed with status ${response.status}`;
        return { data: null, error: errorMsg, status: response.status };
      }

      return { data, error: null, status: response.status };
    } catch (err: any) {
      return {
        data: null,
        error: err.message || 'Network connection failed. Verify server URL.',
        status: 0,
      };
    }
  }
}

export const apiClient = new ApiClient();

