// @ts-check
import { defineConfig } from 'astro/config';

// GitHub Pages project-site config.
// The site is served from https://<username>.github.io/mv1/, so every
// internal link and asset path must be prefixed with the base. In code,
// always build URLs with `import.meta.env.BASE_URL` — never hardcode "/".
//
// TODO(Phase 6): replace GITHUB-USERNAME with the real GitHub username
// before the first deploy (Astro requires a syntactically valid URL here,
// so this placeholder must stay URL-shaped).
export default defineConfig({
  site: 'https://GITHUB-USERNAME.github.io',
  base: '/mv1',
});
