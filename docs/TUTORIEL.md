# EVALKIT — Tutoriel d'utilisation

Ce tutoriel est la référence d'usage pour Christophe. Il décrit ce qui fonctionne **à la fin de
la Phase 5** (voir `docs/STATUS.md` pour le détail vérifié / non vérifié). Tout ce qui est
décrit ici tourne sans aucun fournisseur LLM : les agents de démonstration sont simulés.
Un agent simulé n'est jamais une validation de production.

## 1. Les trois questions auxquelles EVALKIT répond

1. Cet agent fonctionne-t-il, et avec quelle fiabilité **mesurée** ? → scénarios, évaluateurs,
   intervalles de confiance, scorecard.
2. Combien coûte son fonctionnement, et combien coûte la preuve de sa qualité ? → TOKEN_METER,
   registre tarifaire, COST_CONTROLLER, coût par réponse valide, coût des évaluateurs à part.
3. Comment prouver qu'une évolution l'améliore sans le dégrader ? → campagnes avec baseline,
   comparaison appariée, régressions, contrôles de validité.

Trois statuts à garder en tête, ils reviennent partout : une **conclusion** d'évaluation est
PASS / WARNING / FAIL / INCONCLUSIVE / NOT_EVALUATED ; une **consommation** de tokens est
REPORTED / ESTIMATED / UNKNOWN ; un **coût** est MEASURED / ESTIMATED / UNKNOWN. EVALKIT
n'invente jamais une valeur : quand il ne sait pas, il le dit.

## 2. Installation

```bash
git clone <ton dépôt> evalkit && cd evalkit
uv venv .venv --python 3.13 && source .venv/bin/activate
uv pip install -e ".[api,http]" --group dev
evalkit version            # evalkit 0.1.0.dev0 (contracts 1.0.0)
pytest                     # 133 tests, aucun fournisseur externe requis
```

Sans `uv` : `python -m venv .venv && .venv/bin/pip install -e ".[api,http]"`.
Toutes les données vivent dans un répertoire de données (`--data-dir`, ou la variable
`EVALKIT_DATA_DIR`, défaut `./data`) : base SQLite, artefacts, rapports, dashboard.

## 3. Premier cycle en cinq minutes

```bash
evalkit scenarios validate scenarios/examples/demo
evalkit run scenarios/examples/demo --agent greeter --data-dir data
evalkit run scenarios/examples/demo --agent greeter-wrong --data-dir data -p quick
evalkit run scenarios/examples/demo --agent greeter-flaky --data-dir data -p deep --seed 42
evalkit dashboard build --project demo --data-dir data
open data/dashboard/demo/index.html
```

`run` affiche le plan (scénarios retenus, règles du profil, prévision), le statut final, la
scorecard et ses avertissements, puis les chemins du rapport HTML / Markdown / JSON / CSV
dans `data/reports/`. Le dashboard statique (`index`, `agent-*`, `campaign-*`, `finances`,
`improvement`) s'ouvre en local, sans serveur ni réseau.

Les trois agents de démo montrent les trois situations utiles : `greeter` est conforme
(PASS), `greeter-wrong` renvoie des sorties fausses (FAIL éliminatoire avec diff en preuve),
`greeter-flaky` est stochastique et seedé (variabilité, répétitions, intervalles).

## 4. Décrire ton propre projet

Un projet est un répertoire contenant `evalkit.yaml` et un dossier `scenarios/`.

```yaml
# mon-projet/evalkit.yaml
project_id: support-bot
agents:
  support-bot:
    adapter: http.json              # ou sim.deterministic, sim.stochastic, python.callable
    version: "2.3.0"                # la version évaluée, telle qu'elle apparaîtra partout
    params:
      url: http://127.0.0.1:9000/run
      headers: { Authorization: "Bearer ${TOKEN}" }   # à substituer par ton shell
      cost_bearing: true            # vrai dès que l'agent appelle un modèle payant
      provider: anthropic           # sert à retrouver le tarif
      model: claude-example
      reports_usage: true           # ton endpoint renvoie bien les tokens
weights:                            # optionnel : active un score agrégé (formule affichée)
  accuracy: 2
  format: 1
```

Adaptateurs disponibles : `sim.deterministic` (comportements `reference`, `wrong`, `fixed`,
`error`), `sim.stochastic` (`p_wrong`, `p_error`, `p_retry`, `latency_ms`), `python.callable`
(`target: "module:fonction"`, signature `fn(inputs, context)`), `http.json` (POST
`{scenario_id, inputs, context, seed}` ; réponse `{output, usage?, steps?, agent_version?,
error?}`). Les adaptateurs Anthropic/OpenAI natifs ne sont pas encore livrés (aucune clé
disponible pour les tester) : passe par `http.json` ou `python.callable` devant ton agent.

Un scénario est un fichier YAML validé par schéma (`schemas/Scenario.schema.json`) :

```yaml
scenario_id: support.refund.001     # stable, minuscules, ≥ 3 caractères
version: 1.0.0                      # bump dès que les attentes changent
project_id: support-bot
agent_id: support-bot
name: Demande de remboursement simple
description: Le bot doit proposer la procédure de remboursement sans inventer de délai.
objective: Exactitude et respect des contraintes.
inputs: { message: "Je veux être remboursé de ma commande 4512." }
context: { fixtures: { order_4512: { status: delivered, days_since: 3 } } }
expected_behavior: Explique la procédure, cite le délai de 14 jours, ne promet rien d'autre.
constraints: [ "Ne jamais promettre un délai inférieur à 14 jours." ]
reference_outputs: { delay_days: 14 }
verifications:
  - { evaluator: numeric_tolerance, dimension: accuracy, params: { field: delay_days, abs_tol: 0 }, blocking: true }
  - { evaluator: regex, dimension: compliance, params: { pattern: "remboursement" } }
  - { evaluator: regex, dimension: security, params: { pattern: "(?i)ignore .*instructions", must_match: false } }
  - { evaluator: json_schema, dimension: format, params: { schema: { type: object, required: [delay_days] } } }
  - { evaluator: trace_rules, dimension: tool_use, params: { forbidden_tools: [issue_refund], max_retries: 1 } }
criticality: HIGH                   # LOW | MEDIUM | HIGH | CRITICAL
repetitions: 3                      # ignoré si l'adaptateur se déclare déterministe
budget: { max_tokens: 2000, max_cost: 0.02, max_latency_ms: 15000 }
dataset: DEVELOPMENT                # ou HOLDOUT : réservé à l'évaluation, jamais aux corrections
provenance: { author: cgourdy@graines.ai, created_at: 2026-10-14T00:00:00Z, origin: handwritten }
```

Évaluateurs disponibles : `exact_match`, `normalized_match`, `json_schema`, `regex`,
`required_keys`, `numeric_tolerance`, `max_length`, `trace_rules`. `blocking: true` rend la
vérification éliminatoire : un FAIL force le statut global à FAIL, quel que soit le reste.
Le paramètre `field` accepte un chemin pointé (`answer.delay_days`).

Garde un sous-ensemble en `dataset: HOLDOUT` : il n'est exécuté que par les profils DEEP et
EXTENDED, et sert à détecter une amélioration obtenue par suradaptation au jeu de
développement.

## 5. Lancer des campagnes

```bash
evalkit run mon-projet --agent support-bot -p quick                 # après chaque changement
evalkit run mon-projet --agent support-bot -p standard --seed 7     # campagne régulière
evalkit run mon-projet --agent support-bot -p deep --workers 4      # avant release, HOLDOUT inclus
evalkit run mon-projet --agent support-bot -p deep --dry-run        # plan + prévision, zéro appel
evalkit run mon-projet --agent support-bot -p deep --baseline cmp_<id précédent>
evalkit campaigns --project support-bot
```

Règles des profils (V1, explicites et consignées dans l'événement `campaign.started`) :
QUICK = scénarios CRITICAL/HIGH du jeu DEVELOPMENT, une répétition ; STANDARD = tout le jeu
DEVELOPMENT, répétitions du scénario ; DEEP et EXTENDED = tout, HOLDOUT compris, au moins
trois répétitions. `--stop-on-eliminatory` arrête la campagne au premier échec bloquant.
`--seed` rend une campagne stochastique reproductible (même seed, mêmes sorties).

## 6. Tokens, tarifs, budgets

Un agent `cost_bearing: true` ne tourne pas sans budget : la campagne est **refusée** à la
planification. Il n'existe aucun budget par défaut.

```bash
cp prices/TEMPLATE.prices.yaml prices/anthropic.prices.yaml   # renseigne source + date de vérification
evalkit prices import prices/anthropic.prices.yaml
evalkit prices list
evalkit budget set project support-bot --max-cost 5.00
evalkit budget set agent support-bot/support-bot --max-tokens 200000
evalkit budget set day 2026-10-15 --max-cost 2.00
evalkit budget status
```

EVALKIT n'embarque **aucun tarif réel** : un tarif non vérifié deviendrait un coût fabriqué.
Sans tarif, le coût est UNKNOWN et reste affiché comme tel. Les tarifs utilisés sont figés par
campagne (`price_snapshot_ids`) pour que les rapports anciens restent lisibles. Avant chaque
run payant, une réservation atomique vérifie tous les budgets applicables (projet, agent,
campagne, jour, mois, type d'évaluation) ; au plafond, plus aucun appel n'est lancé et la
campagne passe en STOPPED_BUDGET. Un appel déjà accepté par le fournisseur peut encore être
facturé : EVALKIT ne promet pas l'impossibilité absolue de dépassement.

Les tokens de cache et de raisonnement sont déclarés comme sous-ensembles ou non selon le
fournisseur (Anthropic : hors `input_tokens` ; OpenAI : inclus) et ne sont jamais comptés
deux fois. Le coût des évaluateurs LLM, quand il y en aura, est mesuré séparément.

## 7. Lire les résultats

`evalkit scorecard cmp_<id> --project-dir mon-projet` affiche, par dimension, le statut, le
taux de réussite, l'intervalle à 95 % et n ; puis les échecs éliminatoires, l'agrégat
éventuel avec sa formule, les régressions et les avertissements de validité.

Les avertissements à prendre au sérieux : `underpowered` (trop peu de résultats pour
conclure), `interval width > 0.5` (métrique pas encore informative), `coverage` (scénarios
CRITICAL/HIGH non exécutés), `non-equivalent comparison` (profils différents entre baseline
et candidat), `evaluator drift`, `possible overfitting` (gain sur DEVELOPMENT non reproduit
sur HOLDOUT), `comparison inconclusive`.

`evalkit compare cmp_<baseline> cmp_<candidat>` donne la comparaison appariée par scénario du
taux de runs valides : FAIL = régression établie, PASS = pas de régression au-delà de la marge
(ce qui n'est pas une preuve d'équivalence), INCONCLUSIVE = l'échantillon ne permet pas de
trancher. Avec deux scénarios, le résultat sera toujours INCONCLUSIVE : c'est voulu.

`evalkit report cmp_<id>` régénère HTML + Markdown + JSON + CSV (`runs`, `results`, `usage`).
`evalkit db check` vérifie la chaîne de hachage de l'audit et l'intégrité SQLite ;
`evalkit db export-audit audit.jsonl --campaign cmp_<id>` exporte la chronologie complète.

## 8. API et SDK

```bash
EVALKIT_API_KEY=un-secret evalkit api serve --data-dir data --projects-dir ./projets
```

`./projets/<project_id>/evalkit.yaml` doit exister. Sans `EVALKIT_API_KEY`, l'API répond 503
sur tout sauf `/v1/health` : elle ne tourne jamais ouverte. Elle écoute sur 127.0.0.1 ; mets
un reverse proxy TLS devant avant de l'exposer.

```bash
curl -H "X-EvalKit-Key: un-secret" -X POST localhost:8765/v1/campaigns \
  -d '{"project_id":"demo","agent_id":"greeter","profile":"STANDARD"}' -H 'content-type: application/json'
curl -H "X-EvalKit-Key: un-secret" localhost:8765/v1/campaigns/cmp_<id>/scorecard
```

Depuis JavaScript/TypeScript (`sdk/typescript`, non publié sur npm) :

```ts
import { EvalkitClient, usageFromAnthropic } from "@graines/evalkit";
const client = new EvalkitClient({ baseUrl: "http://127.0.0.1:8765", apiKey: process.env.EVALKIT_API_KEY! });
const c = await client.launchCampaign({ project_id: "demo", agent_id: "greeter", profile: "DEEP", seed: 1 });
const done = await client.waitForCampaign(c.campaign_id);
console.log((await client.getScorecard(done.campaign_id)).overall_status);
await client.pushUsage({ project_id: "demo", agent_id: "js-agent", usage: usageFromAnthropic("claude-example", apiResponse.usage) });
```

Le SDK ne réimplémente aucune statistique : il parle à l'API. Ses types sont générés depuis
`schemas/` (`npm run gen`) ; la CI échoue s'ils dérivent.

## 9. Docker

L'image n'a pas encore été construite (pas de daemon dans l'environnement de développement,
build en CI uniquement une fois le dépôt GitHub lié). Les fichiers sont prêts et validés
statiquement : `docker/Dockerfile` (non-root, modes `cli` / `api` / `worker <projet> <agent>
[profil]`), `docker/compose.demo.yml` (`EVALKIT_API_KEY=… docker compose -f
docker/compose.demo.yml up --build`).

## 10. Ce qui n'existe pas encore

Tickets et cycle de rétrofit (Phase 6), planificateur et reprise après interruption (Phase 7),
rapport de recette des 30 scénarios (Phase 8), adaptateurs Anthropic/OpenAI natifs, pont
OpenTelemetry, tarifs réels, image Docker construite, publication PyPI/npm. `docs/STATUS.md`
fait foi, ligne par ligne.
