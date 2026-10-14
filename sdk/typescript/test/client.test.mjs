// Unit tests with a fake fetch — no server, no network.
import assert from "node:assert/strict";
import { test } from "node:test";
import { EvalkitApiError, EvalkitClient, usageFromAnthropic, usageFromOpenAI } from "../dist/index.js";

function fakeFetch(routes) {
  const calls = [];
  const fetchFn = async (url, init) => {
    calls.push({ url, init });
    const key = `${init.method} ${new URL(url).pathname}`;
    const handler = routes[key];
    if (!handler) return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    const [status, body] = handler(init);
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  };
  return { fetchFn, calls };
}

test("sends the api key header and parses JSON", async () => {
  const { fetchFn, calls } = fakeFetch({ "GET /v1/health": () => [200, { status: "ok", evalkit: "x", contracts: "1.0.0" }] });
  const c = new EvalkitClient({ baseUrl: "http://h/", apiKey: "k", fetch: fetchFn });
  const h = await c.health();
  assert.equal(h.status, "ok");
  assert.equal(calls[0].init.headers["x-evalkit-key"], "k");
  assert.equal(calls[0].url, "http://h/v1/health");
});

test("launch + wait polls until terminal", async () => {
  let polls = 0;
  const { fetchFn } = fakeFetch({
    "POST /v1/campaigns": (init) => {
      const body = JSON.parse(init.body);
      assert.equal(body.agent_id, "greeter");
      return [202, { campaign_id: "cmp_1", status: "PLANNED" }];
    },
    "GET /v1/campaigns/cmp_1": () => [200, { campaign_id: "cmp_1", status: ++polls < 3 ? "RUNNING" : "COMPLETED" }],
  });
  const c = new EvalkitClient({ baseUrl: "http://h", apiKey: "k", fetch: fetchFn });
  const launched = await c.launchCampaign({ project_id: "demo", agent_id: "greeter" });
  const done = await c.waitForCampaign(launched.campaign_id, { intervalMs: 1 });
  assert.equal(done.status, "COMPLETED");
  assert.equal(polls, 3);
});

test("errors carry status and detail", async () => {
  const { fetchFn } = fakeFetch({ "GET /v1/campaigns/x": () => [401, { detail: "invalid or missing X-EvalKit-Key" }] });
  const c = new EvalkitClient({ baseUrl: "http://h", apiKey: "bad", fetch: fetchFn });
  await assert.rejects(c.getCampaign("x"), (e) => e instanceof EvalkitApiError && e.status === 401 && /X-EvalKit-Key/.test(String(e.detail)));
});

test("usage builders declare provider subset conventions", () => {
  const o = usageFromOpenAI("gpt-x", { prompt_tokens: 400, completion_tokens: 120, prompt_tokens_details: { cached_tokens: 300 }, completion_tokens_details: { reasoning_tokens: 80 } });
  assert.deepEqual(o.subsets, { cached_input_tokens: "input_tokens", reasoning_tokens: "output_tokens" });
  assert.equal(o.total_tokens, 520);
  const a = usageFromAnthropic("claude-x", { input_tokens: 100, output_tokens: 40, cache_read_input_tokens: 300, cache_creation_input_tokens: 50 });
  assert.deepEqual(a.subsets, {});
  assert.equal(a.total_tokens, 490);
  assert.equal(a.source, "REPORTED");
});
