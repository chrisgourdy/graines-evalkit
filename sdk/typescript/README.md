# @graines/evalkit

TypeScript client for the EVALKIT HTTP API. It launches campaigns, polls results, reads
scorecards and reports, and pushes usage/events from JavaScript agents. It reimplements no
statistics or scoring: the Python engine is the single source of truth, and the types in
`src/contracts.ts` are generated from its JSON Schemas (`npm run gen`).

```ts
import { EvalkitClient } from "@graines/evalkit";
const client = new EvalkitClient({ baseUrl: "http://127.0.0.1:8765", apiKey: process.env.EVALKIT_API_KEY! });
const campaign = await client.launchCampaign({ project_id: "demo", agent_id: "greeter", profile: "STANDARD" });
const done = await client.waitForCampaign(campaign.campaign_id);
const scorecard = await client.getScorecard(done.campaign_id);
```

Not published to npm: see docs/DISTRIBUTION.md and docs/RELEASE_POLICY.md.
