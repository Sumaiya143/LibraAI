const $ = (id) => document.getElementById(id);
let mode = new URLSearchParams(location.search).get('mode') === 'signup' ? 'signup' : 'login';
let csrfToken = '';

async function getCsrfToken() {
  const response = await fetch('/api/csrf', { credentials: 'same-origin', cache: 'no-store' });
  const result = await response.json();
  if (!response.ok || !result.csrfToken) throw new Error('Could not start a secure session. Refresh the page and try again.');
  csrfToken = result.csrfToken;
  return csrfToken;
}

function setMode(nextMode) {
  mode = nextMode;
  const signUp = mode === 'signup';
  $('name-field').hidden = !signUp;
  $('username-field').hidden = !signUp;
  $('role-field').hidden = !signUp;
  $('name-field').querySelector('input').required = signUp;
  $('store-name-field').hidden = !signUp || $('account-role').value !== 'merchant';
  const identity = $('identity');
  identity.name = signUp ? 'email' : 'identifier';
  identity.type = signUp ? 'email' : 'text';
  identity.autocomplete = signUp ? 'email' : 'username';
  identity.placeholder = signUp ? 'you@example.com' : 'Username or email address';
  identity.maxLength = signUp ? 254 : 254;
  $('password').minLength = signUp ? 12 : 1;
  $('password').maxLength = 128;
  $('password').autocomplete = signUp ? 'new-password' : 'current-password';
  $('heading').textContent = signUp ? 'Create your account' : 'Welcome back';
  $('sub').textContent = signUp ? 'Choose a reader or seller account.' : 'Sign in with your username or email.';
  $('submit').textContent = signUp ? 'Create Account →' : 'Sign In →';
  $('login-tab').classList.toggle('active', !signUp);
  $('signup-tab').classList.toggle('active', signUp);
  $('message').textContent = '';
  history.replaceState(null, '', '?mode=' + mode);
}

$('login-tab').addEventListener('click', () => setMode('login'));
$('signup-tab').addEventListener('click', () => setMode('signup'));
$('account-role').addEventListener('change', () => {
  $('store-name-field').hidden = mode !== 'signup' || $('account-role').value !== 'merchant';
});

$('auth-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = $('submit');
  const message = $('message');
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  submit.disabled = true;
  message.textContent = 'Verifying your details…';
  message.setAttribute('aria-busy', 'true');
  try {
    if (!csrfToken) await getCsrfToken();
    const response = await fetch('/api/' + (mode === 'signup' ? 'signup' : 'login'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.message || result.error || 'Authentication failed. Please try again.');
    if (result.redirect) {
      message.textContent = mode === 'signup' ? 'Account created. Opening your workspace…' : 'Signed in. Opening your workspace…';
      location.assign(result.redirect);
      return;
    }
    throw new Error('The server did not return a valid sign-in response.');
  } catch (error) {
    message.textContent = error.message || 'Something went wrong. Please try again.';
    message.removeAttribute('aria-busy');
    submit.disabled = false;
  }
});

getCsrfToken().then(async () => {
  const response = await fetch('/api/me', { credentials: 'same-origin', cache: 'no-store' });
  if (response.ok) {
    const user = await response.json();
    if (user) location.replace(user.redirect || '/');
  }
}).catch((error) => {
  $('message').textContent = error.message;
});
setMode(mode);
