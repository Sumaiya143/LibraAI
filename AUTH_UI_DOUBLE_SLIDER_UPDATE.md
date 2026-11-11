# LibraAI Premium Double-Slider Authentication UI

## Scope
- Rebuilt `/login` and `/signup` as one reusable, responsive double-slider authentication experience.
- Preserved the existing Flask API routes, CSRF bootstrap, request payloads, credentialed fetch behavior, success/error handling, and role-specific redirect data.
- Preserved optional username, required name/email/password/confirmation, customer/seller role choice, terms acceptance, forgot-password link, and existing notice feedback.
- The Google/Facebook actions were not wired to an identity provider in the source project, so they are not presented as active sign-in controls.

## UI
- Desktop double-slider with animated form and promotional panels.
- Mobile layout uses a focused single-form view and a compact promotional panel.
- Canvas particle network with mouse response and click ripples; no external animation assets or dependencies.
- Glass surfaces, layered gradients, micro-interactions, responsive role cards, and reduced-motion support.
- Form data remains mounted when switching between Sign In and Sign Up.

## Security and behavior
- No backend, database, authentication endpoint, session, cookie, token, CSRF, rate-limit, or security-header files were modified.
- Authentication still posts to `/backend/api/login` and `/backend/api/signup` after fetching `/backend/api/csrf`.
- Social login was not invented or mocked.

## Verification
- Static source checks: component routes and both API paths retained.
- ZIP integrity: verified after packaging.
- A full Next.js production build and browser/API integration run require installing the project's dependencies and running the backend; those were not available in this archive-editing environment.
