// Worker for GovWell Prospecting Agent — Phase B
// Handles incoming requests from the dashboard, calls Anthropic API with
// the Building agent, returns structured results.

import {
  BUILDING_AGENT_SYSTEM_PROMPT,
  SUBMIT_BUILDING_PROSPECTS_TOOL,
} from "./building-agent.js";

const ALLOWED_ORIGINS = [
  "https://territory.bd-at-govwell.com",
  "https://ryan-govwell.github.io",
];

const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";
const MODEL = "claude-sonnet-4-5-20250929";
const MAX_TOKENS = 8000;

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin");

    if (request.method === "OPTIONS") return handleCors(origin);
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }
    if (!ALLOWED_ORIGINS.includes(origin)) {
      return jsonResponse(
        { error: "Origin not allowed", origin },
        403,
        origin
      );
    }

    let body;
    try {
      body = await request.json();
    } catch (err) {
      return jsonResponse({ error: "Invalid JSON body" }, 400, origin);
    }

    const { accountName, state, function: fnName, existingContacts } = body;

    if (!accountName || !state || fnName !== "building_permitting_inspections") {
      return jsonResponse(
        {
          error: "Missing or invalid required fields",
          required: ["accountName", "state", 'function: "building_permitting_inspections"'],
        },
        400,
        origin
      );
    }

    if (!env.ANTHROPIC_API_KEY) {
      return jsonResponse(
        { error: "Server misconfigured: missing API key" },
        500,
        origin
      );
    }

    try {
      const agentResult = await callBuildingAgent({
        accountName,
        state,
        existingContacts: existingContacts || [],
        apiKey: env.ANTHROPIC_API_KEY,
      });

      return jsonResponse(agentResult, 200, origin);
    } catch (err) {
      console.error("Agent error:", err);
      return jsonResponse(
        { error: "Agent failed", detail: err.message },
        500,
        origin
      );
    }
  },
};

async function callBuildingAgent({ accountName, state, existingContacts, apiKey }) {
  const userMessage = buildUserMessage({ accountName, state, existingContacts });

const requestBody = {
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: [
      {
        type: "text",
        text: BUILDING_AGENT_SYSTEM_PROMPT,
        cache_control: { type: "ephemeral" },
      },
    ],
    tools: [
      { type: "web_search_20250305", name: "web_search", max_uses: 3 },
      {
        ...SUBMIT_BUILDING_PROSPECTS_TOOL,
        cache_control: { type: "ephemeral" },
      },
    ],
    messages: [{ role: "user", content: userMessage }],
  };

  const response = await fetch(ANTHROPIC_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Anthropic API ${response.status}: ${errorText}`);
  }

  const data = await response.json();

  // Find the submit_building_prospects tool call in the response.
  const toolUseBlock = data.content?.find(
    (b) => b.type === "tool_use" && b.name === "submit_building_prospects"
  );

  if (!toolUseBlock) {
    // Agent didn't call the tool. Return raw response for debugging.
    return {
      error: "Agent did not call submit_building_prospects",
      raw_response: data,
    };
  }

  return {
    result: toolUseBlock.input,
    usage: data.usage,
    stop_reason: data.stop_reason,
  };
}

function buildUserMessage({ accountName, state, existingContacts }) {
  const lines = [
    `Account: ${accountName}`,
    `State: ${state}`,
    "",
    `Existing Building/Permitting/Inspections contacts on file (name and title only — no email/phone on file):`,
  ];

  if (existingContacts.length === 0) {
    lines.push("(none)");
  } else {
    for (const c of existingContacts) {
      lines.push(`- ${c.name || "(no name)"} — ${c.title || "(no title)"}`);
    }
  }

  lines.push("");
  lines.push(
    "Please execute a thorough search of the official website for this account. Find paid staff in the Building/Permitting/Inspections function, dedupe and enrich against the existing contacts above, and submit your findings via the submit_building_prospects tool."
  );

  return lines.join("\n");
}

function jsonResponse(payload, status, origin) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: corsHeaders(origin),
  });
}

function corsHeaders(origin) {
  return {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": origin || "",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function handleCors(origin) {
  if (!ALLOWED_ORIGINS.includes(origin)) {
    return new Response("Origin not allowed", { status: 403 });
  }
  return new Response(null, { status: 204, headers: corsHeaders(origin) });
}