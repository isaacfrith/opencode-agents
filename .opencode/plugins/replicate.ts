// Type-only imports: the plugin has no runtime dependencies, so it loads
// even when .opencode/node_modules has not been installed.
import type { Plugin } from "@opencode/plugin"
import type { ToolContext } from "@opencode/plugin/promise/tool"

const REPLICATE_API_BASE = "https://api.replicate.com/v1"

function getApiToken(): string {
  const token = process.env.REPLICATE_API_TOKEN
  if (token) return token
  throw new Error(
    "Replicate API token not found. Set the REPLICATE_API_TOKEN environment variable.",
  )
}

function authHeaders(apiToken: string): Record<string, string> {
  return {
    Authorization: `Bearer ${apiToken}`,
    "Content-Type": "application/json",
  }
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(signal.reason)
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      clearTimeout(timer)
      reject(signal.reason)
    }
    signal.addEventListener("abort", onAbort, { once: true })
  })
}

// ── Type definitions ──────────────────────────────────────

interface SearchModelResult {
  model: {
    url: string
    owner: string
    name: string
    description: string
    run_count: number
    cover_image_url?: string
    latest_version?: { id: string }
  }
  metadata: {
    tags?: string[]
    generated_description?: string
  }
}

interface ModelDetail {
  is_official?: boolean
  created_at?: string
}

interface SearchResponse {
  models: SearchModelResult[]
  collections?: Array<{ name: string; slug: string; description: string }>
}

interface ModelResponse {
  owner: string
  name: string
  description: string
  latest_version?: {
    id: string
    openapi_schema?: {
      components?: {
        schemas?: {
          Input?: { properties?: Record<string, unknown> }
          Output?: unknown
        }
      }
    }
  }
}

interface PredictionResponse {
  id: string
  status: string
  output: unknown
  error: string | null
  logs: string | null
  metrics?: { predict_time?: number }
  urls?: { get?: string; web?: string }
}

// ── Tool implementations ──────────────────────────────────

async function search(query: string, signal: AbortSignal): Promise<string> {
  const apiToken = getApiToken()
  const url = `${REPLICATE_API_BASE}/search?query=${encodeURIComponent(query)}`
  const response = await fetch(url, { headers: authHeaders(apiToken), signal })

  if (!response.ok) {
    const error = await response.text()
    return `ERROR: Search failed (${response.status}): ${error}`
  }

  const data = (await response.json()) as SearchResponse
  if (!data.models?.length) {
    return "No models found."
  }

  // Enrich results with official status and creation date
  const details = await Promise.all(
    data.models.map(async (r): Promise<ModelDetail> => {
      const res = await fetch(
        `${REPLICATE_API_BASE}/models/${r.model.owner}/${r.model.name}`,
        { headers: authHeaders(apiToken), signal },
      )
      if (!res.ok) return {}
      const d = (await res.json()) as ModelDetail
      return { is_official: d.is_official, created_at: d.created_at }
    }),
  )

  const lines = data.models.map((r, i) => {
    const m = r.model
    const d = details[i]
    const created = d.created_at ? ` (created ${d.created_at.slice(0, 10)})` : ""
    const official = d.is_official ? " [official]" : ""
    const parts = [
      `**${m.owner}/${m.name}** -- ${m.run_count.toLocaleString()} runs${created}${official}`,
      m.description ? `  ${m.description}` : null,
      r.metadata.tags?.length ? `  Tags: ${r.metadata.tags.join(", ")}` : null,
      r.metadata.generated_description
        ? `  ${r.metadata.generated_description}`
        : null,
    ]
    return parts.filter(Boolean).join("\n")
  })

  let result = lines.join("\n\n")

  if (data.collections?.length) {
    result += "\n\n---\n**Related collections:**\n"
    result += data.collections
      .map(
        (c) =>
          `- [${c.name}](https://replicate.com/collections/${c.slug}): ${c.description}`,
      )
      .join("\n")
  }

  return result
}

async function schema(model: string, signal: AbortSignal): Promise<string> {
  const apiToken = getApiToken()
  const url = `${REPLICATE_API_BASE}/models/${model}`
  const response = await fetch(url, { headers: authHeaders(apiToken), signal })

  if (!response.ok) {
    const error = await response.text()
    return `ERROR: Failed to get model (${response.status}): ${error}`
  }

  const data = (await response.json()) as ModelResponse
  const parts = [`# ${data.owner}/${data.name}`, data.description]

  if (data.latest_version?.id) {
    parts.push(`\nLatest version: \`${data.latest_version.id}\``)
    parts.push(`Run as: \`${data.owner}/${data.name}:${data.latest_version.id}\``)
  }

  const schemas = data.latest_version?.openapi_schema?.components?.schemas
  if (schemas?.Input?.properties) {
    parts.push(
      "\n## Input schema\n```json\n" +
        JSON.stringify(schemas.Input.properties, null, 2) +
        "\n```",
    )
  }
  if (schemas?.Output) {
    parts.push(
      "\n## Output schema\n```json\n" +
        JSON.stringify(schemas.Output, null, 2) +
        "\n```",
    )
  }

  return parts.join("\n")
}

async function run(
  model: string,
  input: Record<string, unknown>,
  context: ToolContext,
): Promise<string> {
  const { signal } = context
  const apiToken = getApiToken()
  const hasVersion = model.includes(":")

  const url = hasVersion
    ? `${REPLICATE_API_BASE}/predictions`
    : `${REPLICATE_API_BASE}/models/${model}/predictions`
  const body = hasVersion
    ? { version: model.split(":")[1], input }
    : { input }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...authHeaders(apiToken),
      Prefer: "wait=60",
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    const error = await response.text()
    return `ERROR: Prediction failed (${response.status}): ${error}`
  }

  let prediction = (await response.json()) as PredictionResponse
  const predictionUrl = `https://replicate.com/p/${prediction.id}`

  if (prediction.status === "failed") {
    return `ERROR: Prediction ${prediction.id} failed: ${prediction.error}\n\n${predictionUrl}`
  }

  if (prediction.status === "succeeded") {
    const time = prediction.metrics?.predict_time
    const timeStr = time ? ` (${time.toFixed(2)}s)` : ""
    return (
      `Prediction ${prediction.id} succeeded${timeStr}.\n\n${predictionUrl}\n\n` +
      `Output:\n${JSON.stringify(prediction.output, null, 2)}`
    )
  }

  // Poll until complete
  let allLogs = prediction.logs || ""
  const getUrl =
    prediction.urls?.get ?? `${REPLICATE_API_BASE}/predictions/${prediction.id}`

  while (
    prediction.status !== "succeeded" &&
    prediction.status !== "failed" &&
    prediction.status !== "canceled"
  ) {
    await context.progress({ status: prediction.status, prediction: prediction.id })
    await sleep(2000, signal)

    const pollRes = await fetch(getUrl, { headers: authHeaders(apiToken), signal })
    if (!pollRes.ok) {
      const error = await pollRes.text()
      return `ERROR: Failed to poll prediction (${pollRes.status}): ${error}`
    }

    prediction = (await pollRes.json()) as PredictionResponse

    if (prediction.logs && prediction.logs.length > allLogs.length) {
      allLogs = prediction.logs
    }
  }

  if (prediction.status === "failed") {
    return (
      `ERROR: Prediction ${prediction.id} failed: ${prediction.error}\n\n${predictionUrl}` +
      (allLogs ? `\n\nLogs:\n${allLogs}` : "")
    )
  }

  if (prediction.status === "canceled") {
    return `Prediction ${prediction.id} was canceled.\n\n${predictionUrl}`
  }

  const time = prediction.metrics?.predict_time
  const timeStr = time ? ` (${time.toFixed(2)}s)` : ""
  return (
    `Prediction ${prediction.id} succeeded${timeStr}.\n\n${predictionUrl}\n\n` +
    `Output:\n${JSON.stringify(prediction.output, null, 2)}` +
    (allLogs ? `\n\nLogs:\n${allLogs}` : "")
  )
}

async function whoami(signal: AbortSignal): Promise<string> {
  const apiToken = getApiToken()
  const res = await fetch(`${REPLICATE_API_BASE}/account`, {
    headers: authHeaders(apiToken),
    signal,
  })
  if (!res.ok) {
    const error = await res.text()
    return `ERROR: Failed to get account info (${res.status}): ${error}`
  }
  const data = (await res.json()) as {
    type: string
    username: string
    name: string
  }
  return `Logged in as: ${data.username} (${data.name}, type: ${data.type})`
}

// ── Plugin ────────────────────────────────────────────────

// Tools live in the "replicate" namespace, so their effective names are
// replicate_search, replicate_schema, replicate_run and replicate_whoami.
const NAMESPACE = "replicate"

const plugin: Plugin.Plugin = {
  id: "replicate",
  async setup(ctx) {
    await ctx.tool.transform((editor) => {
      editor.namespace({
        name: NAMESPACE,
        description: "Search, inspect, and run ML models on Replicate",
      })

      editor.add({
        name: "search",
        description:
          "Search for models on Replicate. Returns model names, descriptions, run counts, " +
          "official status, and tags. Use this to find models for image generation, text " +
          "generation, audio, video, etc.",
        input: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description:
                "Search query (e.g. 'image generation', 'lip sync', 'text to speech')",
            },
          },
          required: ["query"],
          additionalProperties: false,
        },
        options: { namespace: NAMESPACE },
        async execute(input, context) {
          const { query } = input as { query: string }
          return { content: await search(query, context.signal) }
        },
      })

      editor.add({
        name: "schema",
        description:
          "Get the input/output schema for a Replicate model. Use this before running a " +
          "model to understand what inputs it accepts and what it returns.",
        input: {
          type: "object",
          properties: {
            model: {
              type: "string",
              description:
                "Model identifier in 'owner/name' format (e.g. 'black-forest-labs/flux-schnell')",
            },
          },
          required: ["model"],
          additionalProperties: false,
        },
        options: { namespace: NAMESPACE },
        async execute(input, context) {
          const { model } = input as { model: string }
          return { content: await schema(model, context.signal) }
        },
      })

      editor.add({
        name: "run",
        description:
          "Run a model on Replicate. Tries sync mode (up to 60s wait). If the model isn't " +
          "done yet, polls every 2 seconds until completion, collecting logs along the way. " +
          "For official models use 'owner/name'. For community models use " +
          "'owner/name:version_id'. Use replicate_schema first to understand the model's inputs.",
        input: {
          type: "object",
          properties: {
            model: {
              type: "string",
              description:
                "Model identifier. Official: 'owner/name' (e.g. 'black-forest-labs/flux-schnell'). " +
                "Community: 'owner/name:version_id'.",
            },
            input: {
              type: "object",
              description: "Model input parameters as a JSON object",
              additionalProperties: true,
            },
          },
          required: ["model", "input"],
          additionalProperties: false,
        },
        options: { namespace: NAMESPACE },
        async execute(input, context) {
          const args = input as { model: string; input: Record<string, unknown> }
          return { content: await run(args.model, args.input, context) }
        },
      })

      editor.add({
        name: "whoami",
        description: "Get the Replicate username for the currently authenticated user.",
        input: {
          type: "object",
          properties: {},
          additionalProperties: false,
        },
        options: { namespace: NAMESPACE },
        async execute(_input, context) {
          return { content: await whoami(context.signal) }
        },
      })
    })
  },
}

export default plugin
