# ADR-0007 — Charts: server-rendered inline SVG for V1 reports (Chart.js/ECharts deferred)

Status: accepted · 2026-10-14

## Context
The specification asks for a professional, minimal, responsive, accessible visual report and
to evaluate a chart library (Chart.js or Apache ECharts) with justification. Constraints that
matter here: reports must open from `file://` without network or build step; values must be
traceable to stored records and testable; error bars (confidence intervals) are a first-class
need; the dev/CI environment must render pages without a browser runtime.

## Options considered
| Option | Size / deps | Offline | Error bars | Testability | Interactivity |
|---|---|---|---|---|---|
| Chart.js 4 | ~70 kB min, canvas | needs the JS inlined or a CDN | plugin required | values live in JS data, assertable but rendered client-side | tooltips, legends |
| Apache ECharts 5 | ~1 MB min, canvas/SVG | needs the JS inlined | native | same as above | rich (zoom, brush) |
| Server-rendered inline SVG | 0 runtime deps (Python only) | yes, from `file://` | trivial (lines) | every number is in the HTML string: tests assert it directly | hover titles only |

## Decision
V1 campaign reports and the static dashboard render inline SVG from Python
(`reporting/svg.py`): horizontal bars with interval error bars, line trends, stacked bars,
histograms. Rules enforced in code: rate/count axes start at 0 (no truncated axes), intervals
always drawn when available, missing values drawn as "n/a", neutral palette with status colours
only for PASS/WARNING/FAIL, labels escaped. Pages carry no `<script>`.

Chart.js is the designated option for a V1.1 dynamic dashboard if interactivity (filtering,
zoom) proves necessary; ECharts is rejected for V1 because of its weight relative to the need.
Mermaid remains the tool for architecture/workflow/state diagrams in Markdown docs.

## Consequences
+ zero dependency, deterministic output, provable "no invented value" (tests compare the HTML
  with the store), works in CI and air-gapped environments.
− no client-side interactivity; very large campaigns (hundreds of scenarios) need pagination
  or aggregation before rendering (backlog EK-0023).
