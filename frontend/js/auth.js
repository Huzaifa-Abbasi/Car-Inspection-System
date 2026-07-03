/**
 * Authentication — login, register, session management.
 */

let selectedLoginRole = 'inspector';
let selectedRegRole = 'inspector';

function selectRole(role) {
    selectedLoginRole = role;
    document.querySelectorAll('#login-form .role-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.role === role);
    });
}

function selectRegRole(role) {
    selectedRegRole = role;
    document.querySelectorAll('#register-form .role-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.role === role);
    });
}

function togglePassword() {
    const input = document.getElementById('login-password');
    input.type = input.type === 'password' ? 'text' : 'password';
}

function showRegister(e) {
    e.preventDefault();
    document.getElementById('login-card').style.display = 'none';
    document.getElementById('register-card').style.display = '';
}

function showLogin(e) {
    e.preventDefault();
    document.getElementById('login-card').style.display = '';
    document.getElementById('register-card').style.display = 'none';
}

// Login form handler
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById('login-error');
    errorEl.style.display = 'none';

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        errorEl.textContent = 'Please enter email and password';
        errorEl.style.display = '';
        return;
    }

    const btn = document.getElementById('login-btn');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'Signing in...';

    try {
        const data = await api.post('/api/auth/login', { email, password });
        api.setToken(data.access_token);
        localStorage.setItem('auth_user', JSON.stringify(data.user));
        enterApp(data.user);
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = '';
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Sign In';
    }
});

// Register form handler
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById('register-error');
    const successEl = document.getElementById('register-success');
    errorEl.style.display = 'none';
    successEl.style.display = 'none';

    const name = document.getElementById('reg-name').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;

    if (!name || !email || !password) {
        errorEl.textContent = 'All fields are required';
        errorEl.style.display = '';
        return;
    }

    try {
        await api.post('/api/auth/register', {
            name,
            email,
            password,
            role: selectedRegRole,
        });
        successEl.textContent = 'Account created! You can now sign in.';
        successEl.style.display = '';
        document.getElementById('register-form').reset();

        setTimeout(() => showLogin({ preventDefault: () => {} }), 2000);
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = '';
    }
});

function logout() {
    api.setToken(null);
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_token');

    document.getElementById('screen-app').classList.remove('active');
    document.getElementById('screen-app').style.display = 'none';
    document.getElementById('screen-login').classList.add('active');
    document.getElementById('screen-login').style.display = '';

    // Reset form
    document.getElementById('login-form').reset();
    document.getElementById('login-error').style.display = 'none';
}

function enterApp(user) {
    // Hide login, show app
    document.getElementById('screen-login').classList.remove('active');
    document.getElementById('screen-login').style.display = 'none';
    document.getElementById('screen-app').style.display = 'flex';
    document.getElementById('screen-app').classList.add('active');

    // Update user info in sidebar
    document.getElementById('user-name').textContent = user.name;
    document.getElementById('user-role-badge').textContent = user.role;
    document.getElementById('user-avatar').textContent = user.name.charAt(0).toUpperCase();

    // Load dashboard
    navigateTo('dashboard');
}
