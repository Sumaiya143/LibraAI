const search = document.querySelector('#question-search');
const questions = [...document.querySelectorAll('.faq-item')];
const status = document.querySelector('#search-status');
const empty = document.querySelector('#no-results');

search?.addEventListener('input', () => {
  const query = search.value.trim().toLocaleLowerCase();
  let matches = 0;
  questions.forEach(item => {
    const matched = !query || item.textContent.toLocaleLowerCase().includes(query);
    item.hidden = !matched;
    if (matched) matches += 1;
  });
  empty.hidden = matches > 0;
  status.textContent = query ? `${matches} ${matches === 1 ? 'answer' : 'answers'} found` : 'Browse common questions';
});

const menuButton = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('.main-nav');
menuButton?.addEventListener('click', () => {
  const opened = mainNav.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(opened));
  menuButton.setAttribute('aria-label', opened ? 'Close navigation' : 'Open navigation');
});
mainNav?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  mainNav.classList.remove('open');
  menuButton?.setAttribute('aria-expanded', 'false');
  menuButton?.setAttribute('aria-label', 'Open navigation');
}));

const themeButton = document.querySelector('.theme-toggle');
try {
  if (localStorage.getItem('libraai-theme') === 'dark') document.body.classList.add('theme-dark');
} catch {}
themeButton?.setAttribute('aria-pressed', String(document.body.classList.contains('theme-dark')));
themeButton?.addEventListener('click', () => {
  const dark = document.body.classList.toggle('theme-dark');
  themeButton.setAttribute('aria-pressed', String(dark));
  themeButton.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
  try {
    localStorage.setItem('libraai-theme', dark ? 'dark' : 'light');
  } catch {}
});

document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    document.querySelector('.header-search input')?.focus();
  }
});


// Account-gated entry points: keep visitors on the page and explain the next step.
(async () => {
  let authenticated = false;
  try { const response = await fetch('/api/auth-status', { credentials: 'same-origin' }); authenticated = response.ok && (await response.json()).authenticated; } catch {}
  document.querySelectorAll('[data-auth-required="ai"]').forEach(link => {
    link.addEventListener('click', event => {
      if (!authenticated) { event.preventDefault(); showAccessNotice('Please sign up first', 'Create a free LibraAI account to use the AI assistant and learning tools.'); }
    });
  });
  function showAccessNotice(title, message) {
    let notice = document.getElementById('access-notice');
    if (!notice) { notice=document.createElement('div'); notice.id='access-notice'; notice.className='access-notice'; notice.setAttribute('role','dialog'); notice.setAttribute('aria-modal','true'); notice.innerHTML='<div class="access-notice-card"><button class="notice-close" aria-label="Close">×</button><span class="notice-emblem">✦</span><p class="eyebrow">A QUICK NOTE</p><h3></h3><p class="notice-copy"></p><a class="button button-dark" href="/register">Create your account ↗</a><a class="notice-login" href="/login">Already a member? Sign in</a></div>'; document.body.appendChild(notice); notice.querySelector('.notice-close').addEventListener('click',()=>notice.remove()); notice.addEventListener('click',e=>{if(e.target===notice)notice.remove()}); }
    notice.querySelector('h3').textContent=title; notice.querySelector('.notice-copy').textContent=message; notice.hidden=false;
  }
})();
