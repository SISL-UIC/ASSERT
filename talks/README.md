# Talks

Follow-along slideshows for ASSERT talks. Each is a static HTML deck —
just **open `index.html` in any browser**, no build step.

> **Serving over a local web server?** Serve from the deck's own folder so the
> relative `assets/` images resolve, e.g. from `aiewf-18min/` run
> `python -m http.server` and open `http://localhost:8000/`. Serving from the
> repo root instead will 404 the chart images (the deck fails loud and tells you).
> Opening `index.html` directly (double-click / `file://`) always works.

| Talk | Deck | Length |
|---|---|---|
| **AI Engineer World's Fair 2026** — *`min_control failure(YOUR agent)`* | [`aiewf-18min/index.html`](aiewf-18min/index.html) | 18 min · 8 slides |

## Navigating a deck

- **← / →** (or Space / Page Up-Down) to move between slides
- Click the **right half** of a slide to advance, **left half** to go back
- **F** toggles fullscreen · dots at the top jump to any slide

The AIEWF deck walks the same three beats as the
[`bank_manager_agent_control`](../examples/bank_manager_agent_control/README.md) example:
baseline → defensive prompting → principled control plane, then the ASSERT + ACS
announcement.
