# Publishing the pde_metrics site — handover note

A short brief for someone helping enable GitHub Pages. Everything on the repository side is
built and committed; what remains is repository settings and DNS.

## What the site is

`pde_metrics` develops and tests metrics for evaluating machine-learning surrogates of PDEs
(fluid flow, MHD, and others). Its output is not a library but a decision — which metrics
belong on an evaluation panel — so every metric carries the evidence for and against itself.

The site publishes that evidence. It is a **static documentation site**, about 36 pages:

- one page per metric and per degradation, generated from a "card" that lives beside each
  implementation in the repository;
- a filterable catalogue of everything;
- a gallery of figures showing what each degradation does to a real turbulence field;
- `catalog.json` and `llms.txt`, machine-readable indexes intended for AI agents that come
  to the repository to choose a metric.

It is entirely static — no server, no database, no build-time data access. It is intended to
be public and to serve as a reference other scientists can validate their own metrics
against.

## How it is built and deployed

| | |
|---|---|
| Repository | `github.com/khegazy/pde_metrics` |
| Generator | MkDocs with the Material theme (`mkdocs.yml` at the repository root) |
| Build command | `mkdocs build --strict`, output to `site/` (gitignored) |
| Workflow | `.github/workflows/docs.yml` |
| Deploy method | **GitHub Actions**, via `actions/upload-pages-artifact@v3` and `actions/deploy-pages@v4` — *not* a `gh-pages` branch |
| Intended domain | `www.pdemetricspreliminary.ai` |

The workflow builds on every pull request and uploads plus deploys only from `main`. It
already declares the permissions the Actions deployment needs (`pages: write`,
`id-token: write`) and the `github-pages` environment.

## What still needs doing

1. **Set the Pages source to GitHub Actions.**
   Settings → Pages → Build and deployment → Source: **GitHub Actions**.
   This is the most likely sticking point: if Source is set to "Deploy from a branch", the
   `deploy-pages` step fails, because the two mechanisms are mutually exclusive.

2. **Configure the custom domain.**
   Settings → Pages → Custom domain: `www.pdemetricspreliminary.ai`.
   A `CNAME` file containing that domain is already committed at the repository root and at
   `docs/CNAME`, so the built site carries it too.

3. **Add the DNS record at the domain registrar.**
   For a `www` subdomain this is a CNAME record:
   `www.pdemetricspreliminary.ai` → `khegazy.github.io`
   (An apex domain would instead need A/AAAA records pointing at GitHub's Pages IPs, but
   the domain here is a `www` subdomain, so a CNAME is correct.)
   DNS propagation can take up to an hour before GitHub will validate it and issue a TLS
   certificate. "Enforce HTTPS" only becomes available after that validation succeeds.

4. **Merge the work to `main`.**
   The site currently lives on the `standardize_information` branch, 30 commits ahead of
   `main`. The deploy job is gated on `main`, so nothing publishes until that merge happens.
   Pull-request builds will run and pass before then, which is a useful way to confirm the
   build works without publishing anything.

## How to tell it worked

- The `docs` workflow shows two green jobs on `main`: `mkdocs build --strict` and
  `publish to GitHub Pages`.
- Settings → Pages reports the site as live at the custom domain, with a valid certificate.
- `https://www.pdemetricspreliminary.ai/catalog.json` returns JSON, and
  `https://www.pdemetricspreliminary.ai/degradations/gallery/` shows the figure gallery.

## Notes for whoever helps

- The build is verified working locally and needs no data or credentials, so a failing build
  in CI would point at the environment rather than the content.
- `DISABLE_MKDOCS_2_WARNING=true` is set deliberately in the workflow: Material prints an
  advisory about a future MkDocs 2 release that `--strict` would otherwise treat as a
  failure. It is unrelated to the site's content.
- Nothing about the site is secret, but the repository may still be private; Pages on a
  private repository requires a plan that permits it, which is worth checking if the Source
  setting appears unavailable.
