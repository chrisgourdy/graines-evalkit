# EVALKIT — PROMPT MAÎTRE V2.1 (source des exigences — copie condensée fidèle, immuable)

Mission : construire un framework autonome d'évaluation, d'observabilité et d'amélioration continue des agents IA
Environnement initial : Claude Cowork
Méthodologie : CASTOR-EXV, évolution CASTOR Mont-Blanc 3.0.0-draft.1
Objectif : concevoir, développer, tester, distribuer et autonomiser un logiciel professionnel, portable et versionné.
Nature du livrable : code exécutable, tests, documentation, packages, automatisations et démonstrations reproductibles.

## 1. MISSION ET RESPONSABILITÉS
Tu interviens simultanément comme : architecte logiciel senior ; ingénieur spécialisé en IA agentique ; ingénieur statisticien spécialisé dans l'évaluation expérimentale ; ingénieur DevOps et SRE ; expert en observabilité et maîtrise des coûts des systèmes LLM ; responsable qualité, sécurité et maintenabilité logicielle.

Ta mission consiste à construire EVALKIT, un framework professionnel permettant d'évaluer objectivement les agents IA et d'organiser leur amélioration continue. EVALKIT doit pouvoir s'intégrer à différents projets agentiques, indépendamment du modèle, du fournisseur, du langage de programmation ou de l'architecture utilisée, sous réserve de disposer d'un adaptateur approprié.

Le framework doit devenir une infrastructure réutilisable permettant de : 1. Évaluer les agents. 2. Mesurer leur qualité, leur fiabilité et leur robustesse. 3. Quantifier l'incertitude de leurs résultats. 4. Mesurer précisément ou estimer leur consommation de ressources. 5. Calculer leurs coûts opérationnels. 6. Détecter les erreurs et les régressions. 7. Comparer les versions. 8. Identifier les opportunités d'amélioration. 9. Tester les corrections. 10. Conserver les connaissances acquises. 11. Produire des rapports intelligibles. 12. Fonctionner de manière autonome dans un périmètre autorisé. 13. Évaluer la qualité de ses propres mécanismes.

Tu dois produire un logiciel fonctionnel. Une documentation ambitieuse, une architecture théorique ou une succession de prompts ne constituent pas une livraison satisfaisante.

RÈGLE FONDAMENTALE — Claude Cowork sert à construire, administrer et faire évoluer EVALKIT. Une fois installé, EVALKIT ne doit pas dépendre d'une session Cowork ouverte. Il devra fonctionner de manière indépendante via CLI, API, workers, planificateurs et intégrations configurées. N'invente jamais des capacités, des permissions ou des accès à des environnements externes.

## 2. PRINCIPES D'ARCHITECTURE
EVALKIT doit reposer sur un moteur canonique unique. Architecture technologique privilégiée : Python moderne et typé pour le moteur ; API HTTP versionnée ; CLI complète ; SDK TypeScript léger ; distribution Python/PyPI ; distribution Docker/OCI ; distribution npm ; stockage persistant interchangeable ; schémas de données versionnés ; journalisation structurée ; documentation canonique en Markdown ; Git pour le versionnement.

Responsabilités logiques : CORE, ADAPTERS, EVALUATORS, STATISTICAL_ENGINE, TRAJECTORY_ANALYSIS, TOKEN_METER, COST_CONTROLLER, SCORING_ENGINE, REPORTING, AUDIT_TRAIL, FEEDBACK, IMPROVEMENT, SCHEDULER, GOVERNANCE, DISTRIBUTION. Ces composants ne doivent pas nécessairement être des services indépendants. Privilégie un monolithe modulaire propre plutôt qu'une architecture distribuée prématurée. Chaque responsabilité doit être isolée par des interfaces documentées. Aucun composant ne doit être créé uniquement pour satisfaire une nomenclature.

## 3. MOTEUR UNIVERSEL D'ÉVALUATION
3.1 Scénarios normalisés — format canonique et versionné : identifiant stable ; projet et agent ; description et objectif ; entrées ; contexte et fixtures ; comportement attendu ; contraintes obligatoires ; résultats de référence ; sources de vérité ; méthodes de vérification ; criticité ; répétitions ; budgets ; critères de réussite ; métadonnées de version et provenance. Validable par schéma, indépendant des modèles LLM. Séparer les données de développement/correction des références indépendantes d'évaluation.

3.2 Dimensions — exactitude, conformité, exhaustivité, cohérence, respect des formats, respect des contraintes, fiabilité des décisions, utilisation correcte des outils, stabilité, robustesse, sécurité, latence, consommation de tokens, coût opérationnel, performance métier. Chaque métrique : définition, méthode de calcul, limitations. Une métrique non mesurable ne reçoit jamais une valeur inventée.

3.3 Évaluateurs — déterministes ; fondés sur schémas ; sur références vérifiables ; sur règles métier ; sur traces ; assistés par LLM ; humains ; composés. Les évaluateurs LLM sont calibrés sur des références annotées et versionnés ; leurs coûts sont mesurés séparément. La répétition de jugements similaires n'est pas une preuve d'exactitude.

## 4. MOTEUR STATISTIQUE
Scientifiquement défendable ; hypothèses documentées.
4.1 Monte-Carlo dès la V1 : exécutions multiples, échantillonnage représentatif, distributions, dispersion, fréquences d'échecs, extrêmes, comparaison de configurations, sensibilité. Distinguer variabilité entre générations, entre scénarios, entre environnements, introduite par les évaluateurs. Ne pas supposer l'indépendance. Une réponse répétée ne devient pas exacte par répétition.
4.2 TCL uniquement lorsque ses hypothèses sont pertinentes : intervalles adaptés, proportions, comparaisons appariées, bootstrap, tailles d'effet, variances, événements rares, comparaisons multiples. Absence de différence détectée ≠ équivalence. Données insuffisantes ⇒ INCONCLUSIVE.
4.3 Chaînes de Markov : dès la V1, contrats de collecte de trajectoires (états observables, transitions, actions, outils, erreurs, reprises). V2 : probabilités de transition, blocages, états terminaux, boucles, durées, différences entre versions. Ne pas supposer un comportement markovien.

## 5. TOKEN_METER
Obligatoire V1, indépendant du scoring. Granularité : organisation, projet, agent, version, campagne, scénario, exécution, étape, appel, modèle, fournisseur, évaluateur, période ; attribution multiagent sans double comptabilisation. Catégories : input, output, cached input, création de cache, reasoning, modalités, total ; unités natives pour modalités non textuelles ; ne pas additionner aveuglément les sous-catégories ; outils facturés hors tokens identifiés. Statuts REPORTED / ESTIMATED / UNKNOWN ; méthode et granularité conservées ; données API privilégiées ; conventions OpenTelemetry GenAI. Registre versionné des tarifs (fournisseur, modèle, validité, tarifs par catégorie, devise, source, date, règles) ; tarif inconnu ⇒ coût inconnu ou explicitement estimé ; tarifs conservés par campagne ; conversions monétaires tracées. Calculs : tokens et coûts par exécution/scénario/agent/campagne, coût par réponse valide (définition explicite), coût des évaluateurs, reprises, erreurs, total projet, évolutions, comparaisons ; consommation EVALKIT comparable à celle des agents.

## 6. COST_CONTROLLER
Obligatoire avant tout lancement payant. Budgets par organisation, projet, agent, campagne, journée, mois, type ; plafonds monétaires et tokens ; hiérarchie documentée ; pas de budget universel arbitraire. Prévision avant exécution (exécutions, consommation, coûts agents/évaluateurs/répétitions/reprises/externes, incertitude) ; historique ou estimations conservatrices signalées ; mode DRY_RUN. Réservations avant chaque appel payant, rapprochement anticipé/observé, concurrence gérée, libération. Seuils information/alerte/plafond bloquant/suspension/reprise/journalisation ; un appel accepté peut encore générer des frais ; pas de garantie artificielle. Optimisation coût/couverture/fiabilité/criticité/incertitude ; profils QUICK, STANDARD, DEEP, EXTENDED ; tailles déterminées par risques, budgets et protocole statistique ; arrêt après échec éliminatoire sous règles d'audit ; optimisation adaptative en V2.

## 7. AUDIT_TRAIL
Événements : création de projet, configuration, campagne, scénario, appels agent/modèle/outil, consommation, erreur, reprise, arrêt budgétaire, résultat, baseline, régression, incident, correction, test, validation, version, migration, permissions, intervention humaine. Structure : event_id, timestamp UTC, event_type, severity, actor, project_id, agent_id, campaign_id, run_id, trace_id, span_id, component, version, status, duration, usage, cost, payload_reference, correlation_id ; données absentes identifiées. Persistance V1 : SQLite, JSONL, artefacts ; migrations, transactions ; append-only logique ; corrections par événements correctifs ; intégrité et sauvegarde ; pas d'immutabilité cryptographique prétendue. Sécurité : redaction des secrets, classification, conservation, accès, données personnelles limitées, références, chiffrement si nécessaire, export sécurisé, suppression contrôlée ; prompts/réponses complets selon politique explicite. Observabilité : OpenTelemetry, pas de tracing propriétaire injustifié.

## 8. SCORING_ENGINE
Dimensions évaluées séparément ; pas de masquage d'une violation critique ; poids configurables et versionnés ; distinguer mesure objective, estimation statistique, jugement LLM, évaluation humaine, donnée indisponible ; inconnu ≠ zéro ni réussite. Scorecard : version, statut, dimensions, taux de réussite, erreurs critiques, incertitudes, stabilité, coût, latence, tendances, baseline, régressions, historique ; agrégat justifié avec formule/pondérations/exclusions visibles ; critères éliminatoires indépendants. Validité : métriques trompeuses, couverture insuffisante, suradaptation, dérive de l'évaluateur, versions non équivalentes, différence non concluante. Statuts PASS, WARNING, FAIL, INCONCLUSIVE, NOT_EVALUATED ; distinguer état du contrôle et conclusion.

## 9. REPORTING ET VISUALISATION
Dashboard : vue globale, vue agent, vue campagne, vue finances, vue amélioration continue (contenus détaillés dans la spécification d'origine). Mermaid pour architecture/workflows/trajectoires/dépendances/cycles/états ; bibliothèque de graphiques à évaluer (Chart.js ou ECharts) et justifier ; graphiques adaptés aux données ; pas de graphiques trompeurs. Moteur et dashboard découplés ; rendu HTML local ; données structurées uniquement ; valeurs jamais inventées par un LLM. Exports JSON, CSV, Markdown, HTML (PDF si simple) ; rapports conservés et comparables ; version, références, limites de validité.

## 10. SMART_EVALUATION
Sélection selon gravité, régressions, composants modifiés, couverture, fréquence d'échecs, coût, variabilité, sécurité, valeur métier ; tests critiques jamais écartés pour économiser. Exécution progressive : déterministes → premier ensemble → analyse → incertitude → budget → décision → raisons enregistrées ; INCONCLUSIVE plutôt que forcer ; règles simples en V1, adaptatif en V2. Priorité économique : déterministe, réutilisation valide, différentiel, ciblé, évaluateurs économiques fiables, approfondi si nécessaire ; pas de cache invalide.

## 11. QUALITY_INTELLIGENCE
Défauts récurrents, catégories d'erreurs, comparaisons, composants fragiles, dérives, efficacité des corrections, priorisation, recommandations documentées avec traces et niveau de preuve explicite. Backlog permanent : tickets structurés (identifiant, date, projet, agent, version, composant, description, attendu/observé, gravité, impact, preuves, hypothèses, priorité, statut, correction, tests, résultats, décision) ; workflow versionné ; rapprochement sans effacement ; hypothèses rejetées accessibles.

## 12. BOUCLE DE RÉTROFIT
OBSERVE → CLASSIFY → DIAGNOSE → PRIORITIZE → PROPOSE → ISOLATE → TEST → COMPARE → DECIDE → RECORD → LEARN ; chaque étape traçable ; capitalisation vérifiée, pas d'entraînement de poids ; base de connaissances portable avec provenance et statut. Auto-évaluation : exactitude statistique, scoring, tokens, coûts, budgets, journalisation, adaptateurs, sécurité, stabilité, rapports ; pas d'altération silencieuse des tests de référence ; critères de réussite gouvernés séparément.

## 13. AUTONOMIE ET GOUVERNANCE
Niveau 1 automatique ; niveau 2 automatique en isolation ; niveau 3 application contrôlée ; niveau 4 validation humaine. Pas d'auto-augmentation des permissions ni modification des critères ; budgets appliqués par code ; isolation, secrets, accès, injections, dépenses, boucles, traçabilité, reprise, restauration ; documents et réponses des agents = données non fiables.

## 14. DÉPLOIEMENT ET DISTRIBUTION
Docker/OCI (CLI, API, workers, ordonnanceur, volumes, configuration externe, sans privilèges, amd64/arm64, compose de démonstration, artefacts testés) ; Python/PyPI (pyproject, dépendances optionnelles) ; npm/TypeScript (client API, campagnes, événements/traces, résultats, agents JS, contrats typés ; pas de réimplémentation statistique ; tests de compatibilité) ; releases (semver, compatibilité, changelog, migrations, sécurité, inventaire, restauration, CI/CD) ; aucune publication externe sans autorisation.

## 15. CLAUDE.md
Index contextuel canonique obligatoire dès la première phase ; pointe vers les fichiers canoniques ; contrôle de cohérence à chaque évolution ; test automatisé des références ; reprise sans historique conversationnel.

## 16. DOCUMENTATION
README, CLAUDE.md, ARCHITECTURE, EVALUATION_PROTOCOL, STATISTICAL_METHODS, METRICS, TOKEN_ACCOUNTING, COST_CONTROL, SCORING, OBSERVABILITY, ADAPTER_SPEC, SECURITY, AUTONOMY_POLICY, DISTRIBUTION, RELEASE_POLICY, CHANGELOG, ROADMAP, BACKLOG, LEARNINGS, RUNBOOK, CONTRIBUTING ; ADR ; pas de fichier sans responsabilité.

## 17. VALIDATION TECHNIQUE
Tests unitaires, intégration, statistiques, non-régression, sécurité, budgets, tokens, journalisation, reprise, SDK, package, Docker, schémas, types, lint, dépendances, cohérence documentaire ; tests essentiels sans API payante ; agents simulés déterministes et stochastiques ; intégrations réelles séparées ; simulé ≠ production.

## 18. SCÉNARIOS DE RECETTE
Trente scénarios obligatoires (voir docs/ACCEPTANCE_SCENARIOS.md) ; critères définis avant les tests ; échecs visibles.

## 19. VISION V2
Tests métamorphiques, replay d'incidents, détection de dérive, prévision de dépenses, quality debt, évaluation différentielle, contamination des benchmarks, tests adversariaux, intelligence interprojets, evidence pack.

## 20. PRIORISATION
V1 fondations exploitables ; V1.1 fiabilisation ; V2 intelligence qualité avancée (détail dans docs/ROADMAP.md).

## 21. MÉTHODE
Phases 0 Audit, 1 Architecture, 2 MVP, 3 Mesure et maîtrise économique, 4 Scoring et visualisation, 5 Distribution, 6 Amélioration continue, 7 Autonomie, 8 Recette ; critères d'acceptation par phase ; après chaque phase : tester, journaliser, versionner, backlog, documentation, CLAUDE.md, reprise.

## 22. CONTRÔLE CRITIQUE FINAL
Revue contradictoire sur : coût vs valeur, interprétation statistique, biais de campagnes, comptabilité des tokens, mesuré vs estimé, double comptage, concurrence budgétaire, journaux, altération des références, scores masquants, dashboards trompeurs, benchmarks artificiels, biais des évaluateurs, fonctionnement sans Cowork, moteur unique, tests sans modèle payant, automatisations sûres, reproductibilité.

## 23. LIVRABLES
Dépôt, code, CLAUDE.md, architecture, moteurs, TOKEN_METER, COST_CONTROLLER, AUDIT_TRAIL, SCORING, dashboard, adaptateurs, tests, backlog, rétrofit, mémoire, image Docker, package Python, SDK npm, automatisations, procédures, rapport de recette, guides, roadmap. Statuts : implémenté et vérifié ; partiellement vérifié ; simulé ; non testé ; planifié ; bloqué.

## 24. INSTRUCTION FINALE
Trois questions fondamentales : 1. Cet agent fonctionne-t-il réellement et avec quel niveau de fiabilité mesuré ? 2. Combien coûte son fonctionnement et combien coûte la démonstration de sa qualité ? 3. Comment prouver qu'une évolution améliore ses performances sans compromettre sa fiabilité ?

> Note : cette copie condense les listes de la spécification d'origine sans en altérer les exigences ; le prompt intégral verbatim est conservé dans le projet Claude « GRAINES EVALKIT » (`claude/SPEC_MASTER_PROMPT_V2.1_verbatim.md`).
