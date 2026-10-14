// EVALKIT API client — thin, dependency-free (global fetch, Node >= 18 / browsers).
import type { AuditEvent, Campaign, EvaluationResult, Run, Scorecard, TokenUsage } from "./contracts/index.js";

export type CampaignProfile = "QUICK" | "STANDARD" | "DEEP" | "EXTENDED";

export interface ClientOptions {
  baseUrl: string;
  apiKey: string;
  /** Custom fetch (tests, polyfills). Defaults to globalThis.fetch. */
  fetch?: typeof fetch;
}

export interface CampaignRequest {
  project_id: string;
  agent_id: string;
  profile?: CampaignProfile;
  seed?: number | null;
  repetitions?: number | null;
  dry_run?: boolean;
  baseline_campaign_id?: string | null;
  workers?: number;
  stop_on_eliminatory?: boolean;
}

export interface UsagePush {
  project_id: string;
  usage: TokenUsage;
  agent_id?: string | null;
  agent_version?: string | null;
  campaign_id?: string | null;
  scenario_id?: string | null;
  run_id?: string | null;
  evaluator_id?: string | null;
  call_id?: string | null;
}

export interface EventPush {
  event_type: string;
  component?: string;
  actor?: string;
  severity?: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  project_id?: string | null;
  agent_id?: string | null;
  campaign_id?: string | null;
  run_id?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
  payload?: Record<string, unknown>;
}

export class EvalkitApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
    message?: string,
  ) {
    super(message ?? `EVALKIT API error ${status}`);
    this.name = "EvalkitApiError";
  }
}

const TERMINAL = new Set(["COMPLETED", "STOPPED_BUDGET", "STOPPED_ELIMINATORY", "FAILED", "SUSPENDED", "DRY_RUN"]);

export class EvalkitClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly fetchFn: typeof fetch;

  constructor(opts: ClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
    this.fetchFn = opts.fetch ?? globalThis.fetch;
    if (!this.fetchFn) throw new Error("no fetch implementation available");
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await this.fetchFn(`${this.baseUrl}${path}`, {
      method,
      headers: { "content-type": "application/json", "x-evalkit-key": this.apiKey },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let data: unknown = text;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      /* non-JSON body kept as text */
    }
    if (!res.ok) {
      const detail = typeof data === "object" && data !== null && "detail" in data ? (data as { detail: unknown }).detail : data;
      throw new EvalkitApiError(res.status, detail, `EVALKIT API ${method} ${path} -> ${res.status}: ${JSON.stringify(detail)}`);
    }
    return data as T;
  }

  health(): Promise<{ status: string; evalkit: string; contracts: string }> {
    return this.request("GET", "/v1/health");
  }

  listCampaigns(projectId: string, agentId?: string): Promise<Campaign[]> {
    const q = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
    return this.request("GET", `/v1/projects/${encodeURIComponent(projectId)}/campaigns${q}`);
  }

  launchCampaign(req: CampaignRequest): Promise<Campaign> {
    return this.request("POST", "/v1/campaigns", req);
  }

  getCampaign(campaignId: string): Promise<Campaign> {
    return this.request("GET", `/v1/campaigns/${encodeURIComponent(campaignId)}`);
  }

  /** Poll until the campaign reaches a terminal status. */
  async waitForCampaign(campaignId: string, opts: { intervalMs?: number; timeoutMs?: number } = {}): Promise<Campaign> {
    const interval = opts.intervalMs ?? 500;
    const deadline = Date.now() + (opts.timeoutMs ?? 300_000);
    for (;;) {
      const c = await this.getCampaign(campaignId);
      if (TERMINAL.has(c.status ?? "")) return c;
      if (Date.now() > deadline) throw new Error(`campaign ${campaignId} still ${c.status} after timeout`);
      await new Promise((r) => setTimeout(r, interval));
    }
  }

  getRuns(campaignId: string): Promise<Run[]> {
    return this.request("GET", `/v1/campaigns/${encodeURIComponent(campaignId)}/runs`);
  }

  getResults(campaignId: string): Promise<EvaluationResult[]> {
    return this.request("GET", `/v1/campaigns/${encodeURIComponent(campaignId)}/results`);
  }

  getScorecard(campaignId: string): Promise<Scorecard> {
    return this.request("GET", `/v1/campaigns/${encodeURIComponent(campaignId)}/scorecard`);
  }

  getReport(campaignId: string): Promise<Record<string, unknown>> {
    return this.request("GET", `/v1/campaigns/${encodeURIComponent(campaignId)}/report`);
  }

  getEvents(campaignId: string): Promise<AuditEvent[]> {
    return this.request("GET", `/v1/campaigns/${encodeURIComponent(campaignId)}/events`);
  }

  pushUsage(req: UsagePush): Promise<{ usage_id: string; cost_status: string }> {
    return this.request("POST", "/v1/usage", req);
  }

  pushEvent(req: EventPush): Promise<{ event_id: string; sequence: number }> {
    return this.request("POST", "/v1/events", req);
  }
}

/** Build a REPORTED TokenUsage for an OpenAI-style payload (cached/reasoning declared as subsets). */
export function usageFromOpenAI(model: string, u: {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens?: number;
  prompt_tokens_details?: { cached_tokens?: number };
  completion_tokens_details?: { reasoning_tokens?: number };
}): TokenUsage {
  return {
    provider: "openai",
    model,
    source: "REPORTED",
    input_tokens: u.prompt_tokens,
    output_tokens: u.completion_tokens,
    cached_input_tokens: u.prompt_tokens_details?.cached_tokens ?? null,
    reasoning_tokens: u.completion_tokens_details?.reasoning_tokens ?? null,
    total_tokens: u.total_tokens ?? u.prompt_tokens + u.completion_tokens,
    subsets: { cached_input_tokens: "input_tokens", reasoning_tokens: "output_tokens" },
  } as TokenUsage;
}

/** Build a REPORTED TokenUsage for an Anthropic Messages usage payload (cache figures separate). */
export function usageFromAnthropic(model: string, u: {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens?: number;
  cache_creation_input_tokens?: number;
}): TokenUsage {
  const cached = u.cache_read_input_tokens ?? 0;
  const created = u.cache_creation_input_tokens ?? 0;
  return {
    provider: "anthropic",
    model,
    source: "REPORTED",
    input_tokens: u.input_tokens,
    output_tokens: u.output_tokens,
    cached_input_tokens: u.cache_read_input_tokens ?? null,
    cache_creation_tokens: u.cache_creation_input_tokens ?? null,
    total_tokens: u.input_tokens + u.output_tokens + cached + created,
    subsets: {},
  } as TokenUsage;
}
