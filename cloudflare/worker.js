/**
 * Cloudflare Pages Edge Worker (_worker.js) for YouTube AI Factory.
 *
 * Serves static dashboard assets via env.ASSETS and implements the local-equivalent
 * policy validation, research-plan generator, and DST-aware Top-Tier Country
 * (US, UK, CA, AU) upload-timing API with zero external paid calls or stored secrets.
 */

const DIGEN_MCP_ENDPOINT = "https://api.digen.ai/v2/gateway/agent/openapi/mcp";
const VIDIQ_MCP_ENDPOINT = "https://mcp.vidiq.com/mcp";

const DEFAULTS = {
  research: {
    provider: "auto",
    fallback_to_gemini: true,
    depth: "full",
    target_countries: ["US", "UK", "CA", "AU"],
    minimum_source_links: 3,
    require_source_dates: true,
    allow_unverified_estimates: false,
    include_upload_time_research: true,
  },
  video: {
    provider: "digen",
    mcp_endpoint: DIGEN_MCP_ENDPOINT,
    require_credit_approval: true,
    automatic_paid_retries: false,
  },
  publishing: {
    require_approval: true,
    default_visibility: "private",
    optimize_top_tier_upload_time: true,
    creator_timezone: "Asia/Dhaka",
  },
};

const TIER1_ZONES = {
  US: ["US Eastern (ET)", "America/New_York"],
  US_PT: ["US Pacific (PT)", "America/Los_Angeles"],
  CA: ["Canada Eastern", "America/Toronto"],
  UK: ["United Kingdom", "Europe/London"],
  AU: ["Australia East", "Australia/Sydney"],
  NZ: ["New Zealand", "Pacific/Auckland"],
  IE: ["Ireland", "Europe/Dublin"],
};

const RESEARCH_SOURCES = [
  ["Buffer YouTube Timing Study (1.8M+ posts)", "https://buffer.com/resources/best-time-to-post-on-youtube/"],
  ["Sprout Social YouTube Posting Times", "https://sproutsocial.com/insights/best-times-to-post-on-youtube/"],
  ["vidIQ Best Time to Post on YouTube", "https://vidiq.com/blog/post/best-time-to-post-youtube-videos/"],
  ["YouTube Help — When Your Viewers Are on YouTube", "https://support.google.com/youtube/answer/10343433"],
];

const SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Content-Security-Policy":
    "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
};

function cloneDefaults() {
  return JSON.parse(JSON.stringify(DEFAULTS));
}

function validateTimezone(tz) {
  if (typeof tz !== "string" || !tz.trim()) {
    throw new Error("creator_timezone must be a non-empty IANA timezone");
  }
  const clean = tz.trim();
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: clean }).format(new Date());
  } catch {
    throw new Error(`Unknown IANA timezone: ${clean}`);
  }
  return clean;
}

function validateSettings(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("Settings must be a JSON object");
  }
  const result = cloneDefaults();
  for (const [section, values] of Object.entries(input)) {
    if (!(section in result) || !values || typeof values !== "object" || Array.isArray(values)) {
      throw new Error(`Unknown or invalid settings section: ${section}`);
    }
    for (const key of Object.keys(values)) {
      if (!(key in result[section])) {
        throw new Error(`Unrecognized setting in ${section}: ${key}`);
      }
      result[section][key] = values[key];
    }
  }
  const r = result.research;
  if (!["auto", "vidiq", "gemini"].includes(r.provider)) {
    throw new Error("research.provider must be auto, vidiq, or gemini");
  }
  if (!["quick", "full"].includes(r.depth)) {
    throw new Error("research.depth must be quick or full");
  }
  if (typeof r.fallback_to_gemini !== "boolean") {
    throw new Error("research.fallback_to_gemini must be boolean");
  }
  if (
    !Array.isArray(r.target_countries) ||
    r.target_countries.length === 0 ||
    !r.target_countries.every((c) => typeof c === "string" && c.trim())
  ) {
    throw new Error("target_countries must be a non-empty list of strings");
  }
  if (result.video.provider !== "digen" || result.video.require_credit_approval !== true || result.video.automatic_paid_retries !== false) {
    throw new Error("Digen video safety invariants cannot be relaxed");
  }
  if (result.publishing.require_approval !== true || result.publishing.default_visibility !== "private") {
    throw new Error("Publishing must remain private with human approval");
  }
  result.publishing.creator_timezone = validateTimezone(result.publishing.creator_timezone);
  return result;
}

function loadCookieSettings(request) {
  const cookieHeader = request.headers.get("Cookie") || "";
  for (const part of cookieHeader.split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k === "yaf_settings" && rest.length) {
      try {
        return validateSettings(JSON.parse(decodeURIComponent(rest.join("="))));
      } catch {
        return cloneDefaults();
      }
    }
  }
  return cloneDefaults();
}

function getTzParts(dateObj, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZoneName: "short",
  }).formatToParts(dateObj);
  const map = {};
  for (const p of parts) map[p.type] = p.value;
  return map;
}

function anchorWallTimeToUtc(year, month, day, hour, minute, anchorTz) {
  const guessUtc = Date.UTC(year, month - 1, day, hour, minute, 0);
  const p = getTzParts(new Date(guessUtc), anchorTz);
  const asUtc = Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day), Number(p.hour), Number(p.minute), 0);
  const offsetMs = asUtc - guessUtc;
  return new Date(guessUtc - offsetMs);
}

function convertWindow(refDateStr, startHm, endHm, anchorTz, targetTz) {
  const [y, m, d] = refDateStr.split("-").map(Number);
  const startUtc = anchorWallTimeToUtc(y, m, d, startHm[0], startHm[1], anchorTz);
  const endUtc = anchorWallTimeToUtc(y, m, d, endHm[0], endHm[1], anchorTz);
  const sp = getTzParts(startUtc, targetTz);
  const ep = getTzParts(endUtc, targetTz);
  const refDayUtc = Date.UTC(y, m - 1, d);
  const startDayUtc = Date.UTC(Number(sp.year), Number(sp.month) - 1, Number(sp.day));
  const endDayUtc = Date.UTC(Number(ep.year), Number(ep.month) - 1, Number(ep.day));
  const dayShift = Math.round((startDayUtc - refDayUtc) / 86400000);
  const endShift = Math.round((endDayUtc - startDayUtc) / 86400000);
  const shiftNote = dayShift > 0 ? " (+1d)" : dayShift < 0 ? " (-1d)" : "";
  const crossMid = endShift > 0 && dayShift === 0 ? " (+1d)" : "";
  return `${sp.hour}:${sp.minute}–${ep.hour}:${ep.minute}${crossMid} ${sp.timeZoneName || targetTz}${shiftNote}`;
}

function computeUploadWindows(aspect = "9:16", targetCountries = ["US", "UK", "CA", "AU"], creatorTz = "Asia/Dhaka") {
  const refDate = new Date().toISOString().slice(0, 10);
  const anchor = "America/New_York";
  const rawSlots =
    aspect === "9:16"
      ? [
          {
            id: "shorts_transatlantic_primary",
            name: "Primary US + UK + CA Overlap Slot",
            best_days: ["Wednesday", "Thursday", "Friday", "Tuesday"],
            private_upload_et: [[10, 0], [12, 0]],
            public_publish_et: [[12, 0], [14, 0]],
            rationale:
              "Hits UK 17:00–19:00 prime post-work/school scroll simultaneously with US/Canada Eastern 12:00–14:00 lunch/early-afternoon mobile break.",
          },
          {
            id: "shorts_na_pacific_au_secondary",
            name: "Secondary US Afternoon/Evening + AU Morning Slot",
            best_days: ["Friday", "Thursday", "Saturday"],
            private_upload_et: [[14, 0], [16, 0]],
            public_publish_et: [[16, 0], [18, 0]],
            rationale:
              "Aligns with Buffer's top Friday 16:00 local Shorts slot, US Pacific afternoon, and Australia East morning commute.",
          },
        ]
      : [
          {
            id: "longform_weekday_overlap",
            name: "Primary Weekday US + UK + CA Pre-Peak Slot",
            best_days: ["Wednesday", "Thursday", "Friday"],
            private_upload_et: [[10, 0], [12, 0]],
            public_publish_et: [[13, 0], [15, 0]],
            rationale:
              "Publishes 2–3 hours ahead of North American 17:00–21:00 CTV/lean-back peak while landing directly in UK 18:00–20:00 evening viewing.",
          },
          {
            id: "longform_weekend_morning",
            name: "Weekend Leisure Peak Slot",
            best_days: ["Sunday", "Saturday"],
            private_upload_et: [[7, 0], [8, 30]],
            public_publish_et: [[9, 0], [11, 0]],
            rationale:
              "Captures Sunday/Saturday 09:00–11:00 ET relaxed morning viewing (Buffer's #1 overall long-form slot is Sunday 10:00) plus UK 14:00–16:00 afternoon.",
          },
        ];

  const normalized = targetCountries.map((c) => c.trim().toUpperCase()).filter(Boolean);
  const activeZones = [["UTC", "UTC"]];
  const seen = new Set(["UTC"]);
  for (const code of normalized) {
    if (code === "US") {
      for (const k of ["US", "US_PT"]) {
        const [label, tz] = TIER1_ZONES[k];
        if (!seen.has(tz)) {
          activeZones.push([label, tz]);
          seen.add(tz);
        }
      }
    } else if (TIER1_ZONES[code]) {
      const [label, tz] = TIER1_ZONES[code];
      if (!seen.has(tz)) {
        activeZones.push([label, tz]);
        seen.add(tz);
      }
    }
  }

  const slots = rawSlots.map((slot) => {
    const markets = {};
    for (const [label, tz] of activeZones) {
      markets[label] = {
        timezone: tz,
        private_upload: convertWindow(refDate, slot.private_upload_et[0], slot.private_upload_et[1], anchor, tz),
        public_publish: convertWindow(refDate, slot.public_publish_et[0], slot.public_publish_et[1], anchor, tz),
      };
    }
    return {
      id: slot.id,
      name: slot.name,
      best_days: slot.best_days,
      rationale: slot.rationale,
      creator_local: {
        timezone: creatorTz,
        private_upload: convertWindow(refDate, slot.private_upload_et[0], slot.private_upload_et[1], anchor, creatorTz),
        public_publish: convertWindow(refDate, slot.public_publish_et[0], slot.public_publish_et[1], anchor, creatorTz),
      },
      markets,
    };
  });

  return {
    reference_date: refDate,
    aspect,
    format: aspect === "9:16" ? "YouTube Shorts (9:16)" : "Long-Form Video (16:9)",
    target_countries: normalized,
    creator_timezone: creatorTz,
    slots,
    sources: RESEARCH_SOURCES.map(([title, url]) => ({ title, url })),
  };
}

function formatUploadPlanText(plan) {
  const lines = [
    `TOP-TIER COUNTRY UPLOAD & SCHEDULE PLAN — ${plan.format}`,
    `Reference date (DST-aware): ${plan.reference_date} | Markets: ${plan.target_countries.join(", ")} | Creator TZ: ${plan.creator_timezone}`,
    "",
  ];
  plan.slots.forEach((slot, i) => {
    lines.push(`${i + 1}. ${slot.name}`);
    lines.push(`   Best days: ${slot.best_days.join(", ")}`);
    lines.push(
      `   Creator local (${slot.creator_local.timezone}): Upload PRIVATE ${slot.creator_local.private_upload} -> Schedule PUBLIC ${slot.creator_local.public_publish}`
    );
    for (const [label, conv] of Object.entries(slot.markets)) {
      lines.push(`   - ${label} (${conv.timezone}): Private ${conv.private_upload} | Public ${conv.public_publish}`);
    }
    lines.push(`   Why: ${slot.rationale}`);
    lines.push("");
  });
  lines.push("EVIDENCE SOURCES:");
  for (const s of plan.sources) lines.push(`- ${s.title}: ${s.url}`);
  return lines.join("\n");
}

function buildResearchInstructions(settings, topic) {
  const r = settings.research;
  const p = settings.publishing;
  const v = settings.video;
  const routeMap = {
    auto: `Check vidIQ MCP (${VIDIQ_MCP_ENDPOINT}) access and credits first; use vidIQ when authenticated and sufficient. If unavailable, ${
      r.fallback_to_gemini ? "use Gemini in Antigravity" : "stop and report the blocker"
    }.`,
    vidiq: `Use vidIQ MCP (${VIDIQ_MCP_ENDPOINT}) research tools exclusively as primary. If unavailable, ${
      r.fallback_to_gemini ? "switch to Gemini via Antigravity" : "stop; do not silently use Gemini"
    }.`,
    gemini:
      "Use Gemini through the active Antigravity agent, its web research tools, and local YouTube Skills; NEVER invoke vidIQ tools.",
  };
  const uploadPlan = formatUploadPlanText(computeUploadWindows("9:16", r.target_countries, p.creator_timezone));
  return `# RESEARCH JOB — YouTube AI Factory

User request: ${topic}

RESEARCH & PRODUCTION SETTINGS
- Selected research mode: ${r.provider} (fallback_to_gemini=${r.fallback_to_gemini})
- Research depth: ${r.depth}
- Top-tier target countries: ${r.target_countries.join(", ")}
- Creator local timezone: ${p.creator_timezone}
- Digen MCP endpoint: ${v.mcp_endpoint}
- vidIQ MCP endpoint: ${VIDIQ_MCP_ENDPOINT}

MANDATORY PROVIDER RULE
${routeMap[r.provider]}

WORKFLOW
1. Open .agents/skills/research-router/SKILL.md, .agents/skills/niche-scout/SKILL.md and .agents/skills/hook-script/SKILL.md.
2. Research original niche and video opportunities for ${r.target_countries.join(", ")} with verifiable links, dated observations, candidate titles and 3 honest hooks per shortlisted idea.
3. Verify Top-Tier Country Upload Best-Time windows (1–2h Shorts / 2–3h Long-Form PRIVATE upload buffer) and override with YouTube Studio's "When your viewers are on YouTube" heatmap after ~28 days of channel data.
4. Attribute every numeric volume/competition metric to vidIQ or a verified source; never fabricate metrics in Gemini mode.
5. Prepare a Digen-ready scene package (Digen only: ${v.mcp_endpoint}; never spend credits or publish publicly without explicit owner approval).

${uploadPlan}
`;
}

function jsonResponse(status, obj, extraHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...SECURITY_HEADERS,
      ...extraHeaders,
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/api/settings") {
      return jsonResponse(200, loadCookieSettings(request));
    }

    if (request.method === "GET" && url.pathname === "/api/research-plan") {
      const topic = (url.searchParams.get("topic") || "Research 5 original YouTube niches").slice(0, 400);
      const settings = loadCookieSettings(request);
      return new Response(buildResearchInstructions(settings, topic), {
        status: 200,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          ...SECURITY_HEADERS,
        },
      });
    }

    if (request.method === "GET" && url.pathname === "/api/upload-plan") {
      const aspect = url.searchParams.get("aspect") || "9:16";
      if (!["9:16", "16:9"].includes(aspect)) {
        return jsonResponse(400, { error: "aspect must be 9:16 or 16:9" });
      }
      const settings = loadCookieSettings(request);
      return jsonResponse(
        200,
        computeUploadWindows(aspect, settings.research.target_countries, settings.publishing.creator_timezone)
      );
    }

    if (request.method === "POST" && url.pathname === "/api/research-settings") {
      const origin = request.headers.get("Origin");
      if (origin && origin !== url.origin) {
        return jsonResponse(403, { error: "Origin not allowed" });
      }
      const ct = (request.headers.get("Content-Type") || "").split(";")[0].trim();
      if (ct !== "application/json") {
        return jsonResponse(415, { error: "Send application/json" });
      }
      try {
        const raw = await request.text();
        if (raw.length < 2 || raw.length > 8192) {
          throw new Error("Request body length invalid");
        }
        const patch = JSON.parse(raw);
        const allowed = new Set(["provider", "depth", "fallback_to_gemini", "target_countries", "creator_timezone"]);
        if (!patch || typeof patch !== "object" || Array.isArray(patch)) {
          throw new Error("Payload must be a JSON object");
        }
        for (const k of Object.keys(patch)) {
          if (!allowed.has(k)) {
            throw new Error("Only research provider, depth, fallback, target_countries, and creator_timezone can be updated");
          }
        }
        const current = loadCookieSettings(request);
        if ("creator_timezone" in patch) {
          current.publishing.creator_timezone = patch.creator_timezone;
          delete patch.creator_timezone;
        }
        Object.assign(current.research, patch);
        const saved = validateSettings(current);
        const secureAttr = url.protocol === "https:" ? "; Secure" : "";
        const cookieVal = encodeURIComponent(JSON.stringify(saved));
        return jsonResponse(200, saved, {
          "Set-Cookie": `yaf_settings=${cookieVal}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax${secureAttr}`,
        });
      } catch (err) {
        return jsonResponse(400, { error: err instanceof Error ? err.message : "Invalid settings" });
      }
    }

    if (url.pathname.startsWith("/api/")) {
      return jsonResponse(404, { error: "Not found" });
    }

    const assetResp = await env.ASSETS.fetch(request);
    const headers = new Headers(assetResp.headers);
    for (const [k, v] of Object.entries(SECURITY_HEADERS)) {
      headers.set(k, v);
    }
    return new Response(assetResp.body, {
      status: assetResp.status,
      statusText: assetResp.statusText,
      headers,
    });
  },
};
