/**
 * API client — wraps fetch() with auth headers and error handling.
 */

const API_BASE = '';  // Same origin (FastAPI serves both API and frontend)

class ApiClient {
    constructor() {
        this._token = localStorage.getItem('auth_token') || null;
    }

    setToken(token) {
        this._token = token;
        if (token) {
            localStorage.setItem('auth_token', token);
        } else {
            localStorage.removeItem('auth_token');
        }
    }

    getToken() {
        return this._token;
    }

    async _request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        if (this._token) {
            headers['Authorization'] = `Bearer ${this._token}`;
        }

        const opts = { method, headers };
        if (body && method !== 'GET') {
            opts.body = JSON.stringify(body);
        }

        const res = await fetch(`${API_BASE}${path}`, opts);

        if (res.status === 401 && path !== '/api/auth/login') {
            // Token expired or invalid
            this.setToken(null);
            localStorage.removeItem('auth_user');
            window.location.reload();
            throw new Error('Session expired. Please log in again.');
        }

        const data = await res.json().catch(() => null);

        if (!res.ok) {
            const msg = data?.detail || `Request failed (${res.status})`;
            throw new Error(msg);
        }

        return data;
    }

    get(path) { return this._request('GET', path); }
    post(path, body) { return this._request('POST', path, body); }
    patch(path, body) { return this._request('PATCH', path, body); }
    delete(path) { return this._request('DELETE', path); }
}

// Global singleton
const api = new ApiClient();
