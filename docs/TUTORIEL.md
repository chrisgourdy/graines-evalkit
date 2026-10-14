# EVALKIT — Tutoriel d'utilisation

Ce tutoriel est la référence d'usage pour Christophe. Il décrit ce qui fonctionne **à la fin de
la Phase 8** (voir `docs/STATUS.md` pour le détail vérifié / non vérifié). Tout ce qui est
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
`required_keys`, `numeric_tolerance`, `max_length`, `trace_rules`, `injection_guard` (dimension
`security` : FAIL si la sortie contient des marqueurs d'injection d'instructions). `blocking: true` rend la
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

## 10. Amélioration continue : tickets, rétrofit, apprentissages

Tout ce chapitre tourne sur des agents simulés et sur une **copie isolée** de ton projet.
EVALKIT ne modifie jamais ton `evalkit.yaml` réel : il observe, diagnostique, teste et décide.
Appliquer la correction reste ton geste.

### 10.1 Détecter les incidents d'une campagne

Une campagne dont la scorecard contient un échec éliminatoire, une régression par rapport à
sa baseline ou un taux d'erreur d'adaptateur supérieur à 20 % produit des tickets :

```bash
evalkit tickets detect <campaign_id> --data-dir data --project-dir mon-projet
evalkit tickets list --project mon-projet --data-dir data
evalkit tickets show <ticket_id> --data-dir data
```

Chaque ticket porte l'attendu, l'observé, l'impact, la criticité du scénario, les références
de preuve (ids de runs, de résultats, de scorecard) et un historique append-only. Relancer la
détection sur la même campagne ne crée pas de doublon aveugle : le nouveau ticket est créé en
statut `DUPLICATE` et lié à l'original dans les deux sens, rien n'est effacé.

Le workflow (version 1.0.0) est `OPEN → TRIAGED → DIAGNOSED → FIX_PROPOSED → TESTING →
VALIDATED | REJECTED → CLOSED`. Une transition hors workflow est refusée :

```bash
evalkit tickets transition <ticket_id> TRIAGED --note "pris en charge" --data-dir data
evalkit tickets transition <ticket_id> CLOSED --note "won't fix" --decision WONTFIX --data-dir data
evalkit backlog export --project mon-projet --out BACKLOG.md --data-dir data
```

### 10.2 Lancer le cycle de rétrofit sur une régression

Prérequis : une campagne « bonne » (dernier état connu correct) et une campagne « cassée » du
**même agent**. Sur la démo, `greeter` 1.0.0 puis `greeter` reconfiguré en `behavior: wrong` :

```bash
evalkit run mon-projet --agent greeter --data-dir data            # bonne → note l'id
# ... tu casses la config de greeter dans evalkit.yaml, puis :
evalkit run mon-projet --agent greeter --data-dir data            # cassée → note l'id
evalkit retrofit run --project-dir mon-projet --agent greeter \
  --broken <cmp_cassee> --good <cmp_bonne> --data-dir data
```

Le cycle enchaîne `OBSERVE > CLASSIFY > DIAGNOSE > PRIORITIZE > PROPOSE > ISOLATE > TEST >
COMPARE > DECIDE > RECORD > LEARN`, chaque étape étant un événement d'audit (`payload.step`,
`payload.experiment_id`). Concrètement : il construit la scorecard de la campagne cassée avec
la bonne en baseline, ouvre les tickets, formule des hypothèses **à partir des faits
enregistrés** (différence de configuration ou de version entre les deux campagnes — jamais
inventées par un LLM), propose une correction (par défaut : revenir à la configuration de la
bonne campagne ; sinon `--params '{"behavior": "reference"}' --version 1.0.1`), copie le
projet dans un répertoire temporaire **sans les scénarios HOLDOUT**, y applique la
correction, lance une campagne STANDARD candidate, la compare à la cassée (doit s'améliorer)
et à la bonne (ne doit pas régresser), puis décide :

| Décision | Sens |
|---|---|
| `HUMAN_VALIDATION_REQUIRED` | correction validée sur le set DEVELOPMENT, mais l'application dépasse le niveau d'autonomie du projet (défaut `max_level: 2`) : c'est toi qui appliques |
| `APPLY_ALLOWED` | idem, et le projet a ouvert un périmètre de niveau 3 (`autonomy.apply_perimeter: [apply_fix_low_risk]`, `max_level: 3`) — EVALKIT n'écrit toujours pas dans ton projet (EK-0033), il enregistre l'autorisation |
| `REJECTED` | aucune candidate acceptable après `--max-iterations` (défaut 2) |
| `NOTHING_TO_FIX` | la scorecard ne montre aucun incident |
| `ALREADY_DECIDED` | le ticket est déjà VALIDATED ou CLOSED : un ticket décidé n'est jamais retravaillé |

Un acteur `agent:*` (`--actor agent:xyz`) n'obtient jamais `APPLY_ALLOWED`, quelle que soit la
configuration : les agents proposent, ils n'appliquent pas.

### 10.3 Confirmer un apprentissage sur le HOLDOUT

Une correction validée produit un apprentissage en statut `observed` : elle n'a été vue que
sur le set DEVELOPMENT. Après avoir appliqué toi-même la correction dans `evalkit.yaml` :

```bash
evalkit retrofit confirm --project-dir mon-projet --agent greeter \
  --good <cmp_bonne> --learning <lrn_id> --data-dir data
evalkit learnings list --project mon-projet --data-dir data
evalkit learnings set-status <lrn_id> adopted --data-dir data     # décision humaine
evalkit learnings export --project mon-projet --out LEARNINGS.md --data-dir data
```

`confirm` lance une campagne DEEP (HOLDOUT inclus) sur le projet réel ; sans échec
éliminatoire ni régression contre la bonne campagne, l'apprentissage passe `verified`, sinon
`rejected`. Rien n'est une règle avant `adopted`, et `adopted` est une décision humaine.

### 10.4 EVALKIT se vérifie lui-même

```bash
evalkit self-check --data-dir data
```

Sept contrôles déterministes (couverture Wilson par simulation, non double-comptage des
tokens Anthropic/OpenAI, coût tenant compte des sous-ensembles, blocage budgétaire, intégrité
de la chaîne d'audit de ta base, export des 11 schémas, présence des documents obligatoires)
produisent une scorecard de l'agent `evalkit` (projet `evalkit-self`). Un contrôle qui ne
peut pas tourner est `NOT_EVALUATED`, jamais masqué ; le code de sortie est 1 si un contrôle
échoue.

## 11. Autonomie : planificateur, reprise, sauvegarde, application contrôlée

### 11.1 Faire tourner EVALKIT sans Cowork ni humain

Un plan YAML (modèle : `scenarios/examples/schedule.example.yaml`) décrit des jobs : projet,
agent, profil, intervalle, politique de baseline, rétrofit ou non, application ou non,
plafond de coût par cycle, garde-fous. Trois façons de l'exécuter :

```bash
evalkit schedule run plan.yaml --once --data-dir data      # cron / timer systemd : un tick puis sortie
evalkit schedule run plan.yaml --poll-seconds 300          # processus long
docker run … graines/evalkit scheduler /projects/plan.yaml --once   # image (CI uniquement ici)
evalkit schedule status plan.yaml --data-dir data
```

À chaque tick, pour chaque job dû : reprise d'une campagne interrompue s'il y en a une, sinon
campagne → scorecard ; saine (PASS ou WARNING sans régression) ⇒ elle devient `last_good`,
baseline des campagnes suivantes ; incident ⇒ cycle de rétrofit seulement si `retrofit:
true`, si une baseline saine existe et si les garde-fous le permettent (`max_retrofits_per_day`,
`cooldown_minutes_after_retrofit`). Un job qui échoue `max_consecutive_failures` fois de suite
se met en pause (événement `human.intervention`) jusqu'à ce que tu le relances :

```bash
evalkit schedule resume-job plan.yaml <job> --note "agent corrigé" --data-dir data
```

Un seul planificateur par répertoire de données (`scheduler.lock`) ; l'état de chaque job
est en base (`schedule_state`), donc un planificateur tué reprend là où il en était.

### 11.2 Application contrôlée d'une correction (niveau 3)

Quand le cycle décide `APPLY_ALLOWED` (projet avec `autonomy.max_level: 3` et
`apply_perimeter: [apply_fix_low_risk]`), tu peux appliquer, ou laisser le planificateur le
faire (`apply_when_allowed: true`) :

```bash
evalkit retrofit apply <exp_id> --project-dir mon-projet --data-dir data
evalkit retrofit rollback --project-dir mon-projet --data-dir data
```

L'application réécrit l'entrée de l'agent dans `evalkit.yaml` après avoir copié l'ancien
fichier dans `.evalkit-backups/`, re-vérifie la politique **au moment d'appliquer** (un
acteur `agent:*` ou un périmètre refermé ⇒ refus), et recharge le projet (sinon retour
arrière immédiat). Le planificateur enchaîne par défaut une confirmation DEEP (HOLDOUT
inclus) et annule l'application si elle échoue (`confirm_after_apply`). Tout est tracé :
`fix.applied`, `fix.rolled_back`, avec avant/après.

### 11.3 Reprendre une campagne interrompue

```bash
evalkit campaign resume <campaign_id> --project-dir mon-projet --data-dir data
```

Les runs restés RUNNING sont conservés en CANCELLED (sans `error` : jamais comptés comme
échec de l'agent), les réservations budgétaires non réglées sont libérées, les tentatives
manquantes sont replanifiées sous de nouveaux numéros (chaque seed est enregistré sur son
run) et la campagne se termine normalement, scorecard et rapports compris. Refus si la
campagne est déjà terminée, si la version de l'agent a changé ou si des scénarios ont
disparu.

### 11.4 Sauvegarder et restaurer

```bash
evalkit db backup sauvegardes/$(date +%F) --data-dir data
evalkit db restore sauvegardes/2026-10-14 --yes --data-dir data
```

La sauvegarde est faite à chaud par l'API de sauvegarde SQLite (cohérente même pendant une
campagne), avec `artifacts/`, `reports/` et un `manifest.json` (migrations, verdict de la
chaîne d'audit). La restauration refuse une base corrompue ou une chaîne cassée, remplace le
répertoire de données, rejoue les migrations et ajoute un événement `db.restore`. Arrête le
planificateur et l'API avant de restaurer.

## 12. Recette : les 30 scénarios et leur rapport

```bash
evalkit acceptance list                         # scénarios, mode, tests couvrants
evalkit acceptance run                          # exécute toute la suite, écrit docs/ACCEPTANCE_REPORT.md
evalkit acceptance run --junit docs/evidence/acceptance-junit.xml
```

Le rapport n'est jamais écrit à la main : il est produit depuis le JUnit d'une vraie
exécution. Un scénario est PASS seulement si **tous** ses tests couvrants ont passé dans cette
exécution, BLOCKED quand l'environnement ne permet pas de l'exécuter (la raison est écrite :
aujourd'hui le seul bloqué est l'exécution Docker, faute de daemon ici), FAIL sinon, et NOT_RUN
si un test couvrant manque — jamais PASS par défaut. Le scénario 28 (suite complète hors
ligne) est jugé sur l'exécution elle-même : zéro échec et aucune clé fournisseur dans
l'environnement. Chaque ligne cite les identifiants de tests, leur résultat et leur durée ;
l'en-tête donne la version, le commit (suffixé `+dirty` si l'arbre de travail diffère), Python
et la plateforme. `tests/test_acceptance.py` vérifie que le registre des scénarios est
identique, mot pour mot, aux critères de `docs/ACCEPTANCE_SCENARIOS.md` et que chaque test
cité existe. La checklist de release est dans `docs/RELEASE_CHECKLIST.md` : rien n'est publié
sans ton feu vert explicite, poste par poste.

## 13. Ce qui n'existe pas encore

Exécution réelle du planificateur sur un cron ou un conteneur et image Docker construite
(câblage présent, CI jamais exécutée faute de dépôt distant), expressions cron et
notifications (EK-0035/0036), hypothèses de diagnostic par LLM (EK-0034), adaptateurs
Anthropic/OpenAI natifs, pont OpenTelemetry, tarifs réels, publication PyPI/npm.
`docs/STATUS.md` fait foi, ligne par ligne.
