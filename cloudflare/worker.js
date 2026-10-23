/**
 * Cloudflare Worker + Static Assets Control Center for YouTube AI Factory.
 *
 * Hybrid Architecture:
 * - Frontend Control Center: Channels • Research Provider • Ideas • Videos • Approvals • Analytics
 * - Cloud Engine: Workers API + Cron readiness, D1 SQLite (env.DB), R2 Media Storage (env.MEDIA_BUCKET),
 *   and Production Job Queue.
 * - Local Engine (Phase 1 MVP): Google Antigravity + vidIQ/Gemini MCP + Digen CLI/MCP + FFmpeg rendering.
 *   Heavy FFmpeg rendering is kept strictly on the Local Engine (never on Workers CPU).
 */

const DIGEN_MCP_ENDPOINT = "https://api.digen.ai/v2/gateway/agent/openapi/mcp";
const VIDIQ_MCP_ENDPOINT = "https://mcp.vidiq.com/mcp";
const R2_STATE_KEY = "_state/control-center-v2.json";

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

const VIDIQ_LEDGER = {
  planName: "Max",
  totalCredits: 6142,
  maxRenewableCredits: 6000,
  addOnCredits: 200,
  metricsAsOf: "2026-10-22T09:42:31Z",
  digenWorkflow: "skill_agent (v21 active)",
  digenMcpEndpoint: DIGEN_MCP_ENDPOINT,
  vidiqMcpEndpoint: VIDIQ_MCP_ENDPOINT,
};

const VIDIQ_KEYWORDS = [
  {
    keyword: "miniature diorama",
    overall: 67.5,
    competition: 26.8,
    competitionLabel: "Low",
    monthlySearches: "18,555",
    usVolume: "unknown (null)",
    growth30d: "+118.7%",
    topOpportunity: "diy diorama / satisfying video (88.4K US)",
  },
  {
    keyword: "animated short film",
    overall: 66.9,
    competition: 56.0,
    competitionLabel: "Medium",
    monthlySearches: "323,517",
    usVolume: "32,105",
    growth30d: "+126.6%",
    topOpportunity: "short film (69.4 overall, 141.9K US)",
  },
  {
    keyword: "how things work",
    overall: 65.3,
    competition: 54.0,
    competitionLabel: "Medium",
    monthlySearches: "173,105",
    usVolume: "18,933",
    growth30d: "+25.5%",
    topOpportunity: "everything professor (70.4 overall)",
  },
  {
    keyword: "deep sea creatures",
    overall: 64.8,
    competition: 59.0,
    competitionLabel: "Medium",
    monthlySearches: "254,959",
    usVolume: "17,847",
    growth30d: "-21.6%",
    topOpportunity: "deep sea mysteries (69.4 overall, 37.7 comp)",
  },
  {
    keyword: "forgotten history",
    overall: 62.6,
    competition: 63.0,
    competitionLabel: "Med-High",
    monthlySearches: "215,889",
    usVolume: "15,606",
    growth30d: "-14.4%",
    topOpportunity: "world war 2 (67.6 overall, 58.5 comp)",
  },
];

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
    "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; media-src 'self' blob:; img-src 'self' data: blob:; base-uri 'none'; frame-ancestors 'none'",
};

const SAFE_MEDIA_RE = /^\/api\/media\/([a-z0-9-]{1,64})\/([a-zA-Z0-9._-]{1,80})$/;

let MEMORY_FALLBACK_STATE = null;

function nowIso() {
  return new Date().toISOString();
}

function slugify(val) {
  const clean = String(val || "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
  return clean || `ep-${Math.random().toString(36).slice(2, 8)}`;
}

function cloneJson(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function buildSeedState() {
  const ts = "2026-10-23T08:00:00.000Z";
  return {
    settings: cloneJson(DEFAULTS),
    channels: [
      {
        id: "ch-hawthorn",
        name: "Hawthorn Hollow Miniatures",
        handle: "@hawthornhollow",
        niche: "Cozy Miniature Diorama Folklore",
        default_aspect: "9:16",
        target_countries: ["US", "UK", "CA", "AU"],
        creator_timezone: "Asia/Dhaka",
        studio_heatmap_override: "",
        status: "active",
        updated_at: ts,
      },
      {
        id: "ch-mechanics",
        name: "Everyday Hidden Mechanics 3D",
        handle: "@hiddenmechanics3d",
        niche: "Everyday Hidden Mechanics",
        default_aspect: "9:16",
        target_countries: ["US", "UK", "CA", "AU"],
        creator_timezone: "Asia/Dhaka",
        studio_heatmap_override: "",
        status: "pilot-ready",
        updated_at: ts,
      },
    ],
    ideas: [
      {
        id: "idea-miniature-folklore",
        channel_id: "ch-hawthorn",
        title: "The Lantern Beneath Hawthorn Hollow",
        niche: "Cozy Miniature Diorama Folklore",
        score: 91,
        rubric: "Curiosity 18/20 · Distinction 19/20 · Digen 23/25 · Evergreen 17/20 · Serial 14/15",
        aspect: "9:16",
        vidiq_summary: "67.5/100 overall · 26.8 Low competition · +118.7% 30d search growth",
        promise:
          "Tilt-shift moss-and-brass miniature dioramas bringing 32-second UK & North American woodland micro-myths to life with recurring non-human sprite Wick.",
        upload_slot: "Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)",
        hooks: [
          "Every autumn in the British hills, hikers spot tiny brass lanterns glowing beneath hawthorn roots.",
          "When frost hits the hollow, one acorn-sized keeper has eight seconds before the last ember dies.",
          "Look closely inside this mossy oak root—someone left the porch light on.",
        ],
        sources: [
          { label: "PBS Storied / Monstrum", url: "https://www.youtube.com/@pbsstoried" },
          { label: "YouTube Miniature Diorama", url: "https://www.youtube.com/results?search_query=miniature+folklore+diorama" },
        ],
        status: "in-production",
        updated_at: ts,
      },
      {
        id: "idea-airplane-window",
        channel_id: "ch-mechanics",
        title: "Why Airplane Windows Have That Tiny Hole",
        niche: "Everyday Hidden Mechanics",
        score: 89,
        rubric: "Curiosity 19/20 · Distinction 17/20 · Digen 21/25 · Evergreen 19/20 · Serial 13/15",
        aspect: "9:16",
        vidiq_summary: "65.3/100 overall · 173,105/mo searches (+25.5% 30d) · 18,933 US volume",
        promise:
          "Stylized 3D cutaway micro-documentary showing how a 1mm bleed hole balances cabin air pressure across three acrylic panes at 35,000 feet.",
        upload_slot: "Wed/Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)",
        hooks: [
          "There is an intentional hole drilled right through your airplane window—and it keeps the cabin pane from shattering.",
          "At 35,000 feet, three thin layers hold back freezing air thanks to a one-millimeter bleed hole.",
          "Slice an airliner window in half and you'll spot a tiny tunnel doing a life-saving job.",
        ],
        sources: [
          { label: "How Things Work", url: "https://www.youtube.com/@YoutubeHowThingsWork" },
          { label: "Practical Engineering", url: "https://www.youtube.com/@PracticalEngineeringChannel" },
        ],
        status: "shortlisted",
        updated_at: ts,
      },
      {
        id: "idea-tiny-rover",
        channel_id: "ch-hawthorn",
        title: "Unit Bramble and the Last Lunar Dandelion",
        niche: "Tiny Rover Chronicles (Cozy Sci-Fi)",
        score: 86,
        rubric: "Curiosity 17/20 · Distinction 18/20 · Digen 23/25 · Evergreen 15/20 · Serial 13/15",
        aspect: "9:16",
        vidiq_summary: "66.9/100 overall · 323,517/mo (+126.6% 30d) · 32,105 US volume",
        promise:
          "Isometric macro dispatch following palm-sized repair rover 'Unit Bramble' tending forgotten terrarium domes across quiet moons.",
        upload_slot: "Fri/Sat 16:00–18:00 ET (02:00–04:00 BDT +1d)",
        hooks: [
          "Sixty years after humans left Outpost Nine, the smallest rover found something impossible growing in the dust.",
          "Sunset on this moon lasts two freezing weeks—and Unit Bramble just found one flower outside the dome.",
          "His battery hit four percent right when his botanical scanner turned green for the first time in a century.",
        ],
        sources: [{ label: "DUST Sci-Fi Shorts", url: "https://www.youtube.com/@watchdust" }],
        status: "shortlisted",
        updated_at: ts,
      },
      {
        id: "idea-abyssal-squid",
        channel_id: "ch-mechanics",
        title: "How Deep-Sea Squid Use Light to Disappear",
        niche: "Abyssal & Microscopic Mysteries",
        score: 82,
        rubric: "Curiosity 18/20 · Distinction 16/20 · Digen 19/25 · Evergreen 17/20 · Serial 12/15",
        aspect: "9:16",
        vidiq_summary: "'deep sea mysteries' sub-niche: 69.4/100 overall · 37.7 Low-Med competition",
        promise:
          "Clearly labeled 3D scientific visualization unpacking real deep-sea counter-illumination and bioluminescent defense mechanisms.",
        upload_slot: "Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)",
        hooks: [
          "Half a mile beneath the ocean surface, this creature turns on belly headlights to become completely invisible.",
          "In pitch-black water, flashing bright blue is actually how tiny shrimp escape giant predators.",
          "What looks like glowing stardust in ocean waves is a microscopic burglar alarm.",
        ],
        sources: [
          { label: "MBARI", url: "https://www.youtube.com/@MBARIvideo" },
          { label: "EV Nautilus", url: "https://www.youtube.com/@EVNautilus" },
        ],
        status: "shortlisted",
        updated_at: ts,
      },
      {
        id: "idea-clockwork-hat",
        channel_id: "ch-mechanics",
        title: "The Self-Tipping Clockwork Hat of 1896",
        niche: "Forgotten Industrial Oddities",
        score: 79,
        rubric: "Curiosity 19/20 · Distinction 15/20 · Digen 17/25 · Evergreen 17/20 · Serial 11/15",
        aspect: "9:16",
        vidiq_summary: "62.6/100 overall · 63.0 competition · requires ultra-specific patent angles",
        promise:
          "Dry-witted animated micro-history about US Patent No. 556,248—an 1896 bowler hat that tipped itself politely via clockwork gears.",
        upload_slot: "Tue/Wed/Thu 12:00–14:00 ET (22:00–00:00 BDT)",
        hooks: [
          "In 1896, inventors patented a hat that tipped itself politely—using clockwork gears strapped to your forehead.",
          "Before electronic alarms, British factory towns paid a worker with a twelve-foot pea-shooter to tap upstairs windows.",
          "Victorian parlor catalogs briefly sold cast-iron mechanical rocking chairs that fanned your face while you read.",
        ],
        sources: [
          { label: "Simple History", url: "https://www.youtube.com/@Simplehistory" },
          { label: "Weird History", url: "https://www.youtube.com/@WeirdHistory" },
        ],
        status: "backlog",
        updated_at: ts,
      },
    ],
    videos: [
      {
        slug: "pilot-01",
        channel_id: "ch-hawthorn",
        title: "The Lantern Beneath Hawthorn Hollow",
        niche: "Cozy Miniature Diorama Folklore",
        target_audience: "English-speaking US, UK, Canadian, and Australian viewers",
        aspect: "9:16",
        status: "prompts-packed",
        made_for_kids: false,
        contains_synthetic_media: true,
        hooks: [
          "Every autumn in the British hills, hikers spot tiny brass lanterns glowing beneath hawthorn roots.",
          "When frost hits the hollow, one acorn-sized keeper has eight seconds before the last ember dies.",
          "Look closely inside this mossy oak root—someone left the porch light on.",
        ],
        style_bible:
          "Tactile tilt-shift macro miniature diorama blended with stylized 3D stop-motion animation. Main character: Wick, an acorn-sized woodland lantern-keeper made of woven russet oak leaves and weathered brass, wearing a mossy bell-cap hat with two tiny warm amber pinhole eyes and carrying a miniature hexagonal brass lantern. Environment: gnarled ancient hawthorn tree roots, damp emerald moss, silver autumn frost crystals, warm golden lantern glow against deep twilight blue shadows. Macro shallow depth-of-field, coherent proportions in every shot, zero on-screen text, zero watermarks.",
        script:
          "Beneath the oldest hawthorn root, a tiny brass lantern still burns every October night. Its keeper is Wick—no taller than an acorn—guarding the last warm ember before winter frost seals the hollow. When a sudden freezing gust snuffs the wick to a faint spark, he shelters the glass with his own leaf cloak and feeds it a single dried sun-berry. Golden light blooms across the mossy roots, guiding lost woodland beetles safely underground until spring.",
        scenes: [
          {
            name: "The Glowing Root Hollow",
            duration_seconds: 8,
            narration: "Beneath the oldest hawthorn root, a tiny brass lantern still burns every October night.",
            prompt:
              "Vertical 9:16 macro tilt-shift miniature diorama animation. Camera pushes gently toward a mossy hollow beneath gnarled hawthorn roots in twilight mist. Inside stands Wick, an acorn-sized lantern-keeper crafted from russet oak leaves and weathered brass with a mossy bell-cap hat and two warm amber pinhole eyes, holding a glowing hexagonal brass lantern. Crisp macro depth of field, drifting autumn spores, soft rustling leaves ambient audio, no text.",
            clipStatus: "missing",
            clipUrl: "",
          },
          {
            name: "Frost Hits the Hollow",
            duration_seconds: 8,
            narration: "Its keeper is Wick—no taller than an acorn—guarding the last warm ember before winter frost seals the hollow.",
            prompt:
              "Vertical 9:16 macro miniature animation, exact same character Wick and hawthorn root hollow. Delicate silver frost crystals creep rapidly across the emerald moss toward the doorway. Close-up as a cold blue gust sweeps in and the flame inside Wick's hexagonal brass lantern flickers down to a tiny dying red spark. Expressive head tilt, atmospheric wind chime of ice, stable miniature proportions, no text.",
            clipStatus: "missing",
            clipUrl: "",
          },
          {
            name: "The Sun-Berry Spark",
            duration_seconds: 8,
            narration: "When a sudden gust nearly snuffs the flame, he shields the glass with his cloak and drops in a dried sun-berry.",
            prompt:
              "Vertical 9:16 extreme macro close-up, exact same acorn-sized Wick kneeling on frosted moss. Wick wraps his russet oak-leaf cloak around the hexagonal brass lantern to block the frost, opens the tiny brass latch, and places a luminous golden dried berry onto the faint spark. Warm golden volumetric light erupts softly inside the glass, reflecting in Wick's amber eyes. Tactile stop-motion charm, no text.",
            clipStatus: "missing",
            clipUrl: "",
          },
          {
            name: "Sanctuary Until Spring",
            duration_seconds: 8,
            narration: "Golden light blooms across the mossy roots, guiding tiny woodland travelers safely home until spring.",
            prompt:
              "Vertical 9:16 gentle pull-back crane shot of the miniature hawthorn hollow. Warm golden lantern light melts the frost around the mossy entrance as two tiny iridescent woodland beetles follow the warm glow into the cozy root archway beside Wick. Frosty blue autumn night outside contrasting with warm amber sanctuary inside. Peaceful acoustic atmosphere, zero text.",
            clipStatus: "missing",
            clipUrl: "",
          },
        ],
        seo: {
          title: "The Tiny Lantern Keeper Under the Oldest Tree ✨ | Miniature Folklore Short",
          description:
            "Deep beneath an autumn hawthorn root, an acorn-sized keeper named Wick guards the last warm lantern before winter frost arrives.\n\nAn original fictional miniature folklore micro-story crafted with stylized 3D synthetic animation.\n\n#MiniatureWorld #FolkloreStory #AnimatedShort #CozyVibes #ShortFilm",
          tags: ["miniature diorama story", "cozy folklore short", "animated micro story", "autumn folklore", "original 3d short"],
          thumbnail_brief:
            "Macro vertical close-up of acorn-sized Wick in his mossy bell-cap cradling a bright golden hexagonal brass lantern inside a dark frosty tree root hollow; strong warm-amber vs icy-blue contrast; clean composition with zero misleading text.",
        },
        r2_final_key: "",
        r2_thumb_key: "",
        updated_at: ts,
      },
      {
        slug: "pilot-demo",
        channel_id: "ch-hawthorn",
        title: "The Little Robot Who Found a Star",
        niche: "Animated micro-adventure stories",
        target_audience: "English-speaking US, UK and Canadian viewers",
        aspect: "9:16",
        status: "draft",
        made_for_kids: false,
        contains_synthetic_media: true,
        hooks: [
          "Everything in the city had gone dark—except one crack in the pavement.",
          "Pip had one last spark left in his copper chest when he heard a star crying.",
          "Nobody in the dark city looked down until a palm-sized robot stopped at the curb.",
        ],
        style_bible:
          "Original cinematic stylized 3D animation. Main character: Pip, palm-sized friendly brushed-copper robot, one large glowing teal eye, rectangular backpack and short rounded legs. Consistent outfit, voice, eye and proportions in every scene. Warm amber/teal night lighting. No logos, no visible text.",
        script:
          "Everything in the city had gone dark. But Pip heard a tiny sound beneath the pavement. A little star was trapped in a crack! He tried to pull it out, but the city was too cold. Then he gave it the last spark from his own heart. The sky lit up. And for the first time, the whole city saw the stars.",
        scenes: [
          {
            name: "The city goes dark",
            duration_seconds: 8,
            narration: "Everything in the city had gone dark.",
            prompt:
              "Vertical cinematic 3D original animation. A tiny brushed-copper robot named Pip with one glowing teal eye and a small rectangular backpack walks through a silent city at night. Streetlights flicker off one by one. Tracking shot, suspenseful yet family-friendly, coherent anatomy, no text.",
            clipStatus: "missing",
            clipUrl: "",
          },
          {
            name: "A star beneath the pavement",
            duration_seconds: 8,
            narration: "But Pip heard a tiny sound beneath the pavement. A little star was trapped in a crack!",
            prompt:
              "Same exact Pip robot and city. Close-up of Pip kneeling at a stone pavement crack, where a tiny warm golden star glows. Pip's teal eye widens with surprise. Soft volumetric beams and expressive animation, stable proportions.",
            clipStatus: "missing",
            clipUrl: "",
          },
          {
            name: "A spark of kindness",
            duration_seconds: 8,
            narration: "He gave it the last spark from his own heart.",
            prompt:
              "Same Pip robot gently offering a tiny glowing spark from its chest to the star. Star rises into a warm night sky and countless stars gently appear over the quiet city. Uplifting cinematic crane shot, magical but original design.",
            clipStatus: "missing",
            clipUrl: "",
          },
        ],
        seo: {
          title: "The Robot Who Gave Away His Last Spark ✨ | Animated Short",
          description:
            "A tiny robot finds something extraordinary beneath a dark city. An original animated micro-story about kindness and courage. #AnimatedShort #ShortStory #AIAnimation",
          tags: ["animated short", "original animation", "robot story", "micro story", "short film"],
          thumbnail_brief:
            "Large close-up of Pip's expressive teal eye looking at a luminous tiny golden star in its hands; dark city behind; strong contrast; original artwork; no fake claims.",
        },
        r2_final_key: "",
        r2_thumb_key: "",
        updated_at: ts,
      },
    ],
    approvals: {
      "pilot-01": {
        video_slug: "pilot-01",
        digen_scene1_approved: false,
        digen_remaining_approved: false,
        qa_approved: false,
        qa_checks: [false, false, false, false, false],
        private_upload_approved: false,
        scheduled_publish_window: "Wed/Thu/Fri 22:00–00:00 Asia/Dhaka (12:00–14:00 US ET / 17:00–19:00 UK)",
        notes: "Scene-01 credit gate pending owner approval.",
        updated_at: ts,
      },
      "pilot-demo": {
        video_slug: "pilot-demo",
        digen_scene1_approved: false,
        digen_remaining_approved: false,
        qa_approved: false,
        qa_checks: [false, false, false, false, false],
        private_upload_approved: false,
        scheduled_publish_window: "Wed/Thu/Fri 22:00–00:00 Asia/Dhaka",
        notes: "Sample reference episode.",
        updated_at: ts,
      },
    },
    jobs: [
      {
        id: "job-seed-pack-01",
        channel_id: "ch-hawthorn",
        video_slug: "pilot-01",
        job_type: "pack_prompts",
        target_runner: "local_engine",
        status: "completed",
        payload: { scenes: 4, aspect: "9:16" },
        result_summary: "Packed 4 Digen prompts + US/UK/CA/AU upload schedule locally.",
        created_at: ts,
        updated_at: ts,
      },
      {
        id: "job-seed-digen-01",
        channel_id: "ch-hawthorn",
        video_slug: "pilot-01",
        job_type: "digen_scene_01",
        target_runner: "local_engine",
        status: "awaiting_approval",
        payload: { scene: 1, credits_gate: "required" },
        result_summary: "Waiting for human Scene-01 credit approval.",
        created_at: ts,
        updated_at: ts,
      },
    ],
    analytics: [],
  };
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
  const result = cloneJson(DEFAULTS);
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
  if (
    result.video.provider !== "digen" ||
    result.video.require_credit_approval !== true ||
    result.video.automatic_paid_retries !== false
  ) {
    throw new Error("Digen video safety invariants cannot be relaxed");
  }
  if (result.publishing.require_approval !== true || result.publishing.default_visibility !== "private") {
    throw new Error("Publishing must remain private with human approval");
  }
  result.publishing.creator_timezone = validateTimezone(result.publishing.creator_timezone);
  return result;
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

function computeUploadWindows(
  aspect = "9:16",
  targetCountries = ["US", "UK", "CA", "AU"],
  creatorTz = "Asia/Dhaka",
  explicitDate = null
) {
  const cleanCreatorTz = validateTimezone(creatorTz);
  const refDate =
    explicitDate && /^\d{4}-\d{2}-\d{2}$/.test(explicitDate) ? explicitDate : new Date().toISOString().slice(0, 10);
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
        timezone: cleanCreatorTz,
        private_upload: convertWindow(refDate, slot.private_upload_et[0], slot.private_upload_et[1], anchor, cleanCreatorTz),
        public_publish: convertWindow(refDate, slot.public_publish_et[0], slot.public_publish_et[1], anchor, cleanCreatorTz),
      },
      markets,
    };
  });

  return {
    reference_date: refDate,
    aspect,
    format: aspect === "9:16" ? "YouTube Shorts (9:16)" : "Long-Form Video (16:9)",
    target_countries: normalized,
    creator_timezone: cleanCreatorTz,
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
  return `# RESEARCH JOB — YouTube AI Factory (Local-First Hybrid Architecture)

User request: ${topic}

RESEARCH & PRODUCTION SETTINGS
- Selected research mode: ${r.provider} (fallback_to_gemini=${r.fallback_to_gemini})
- Research depth: ${r.depth}
- Top-tier target countries: ${r.target_countries.join(", ")}
- Creator local timezone: ${p.creator_timezone}
- Digen MCP endpoint: ${v.mcp_endpoint}
- vidIQ MCP endpoint: ${VIDIQ_MCP_ENDPOINT}
- Execution Split: Local Antigravity + MCP + FFmpeg (0 cloud API overages) <-> Cloudflare Control Center

MANDATORY PROVIDER RULE
${routeMap[r.provider]}

WORKFLOW
1. Open .agents/skills/research-router/SKILL.md, .agents/skills/niche-scout/SKILL.md and .agents/skills/hook-script/SKILL.md.
2. Research original niche and video opportunities for ${r.target_countries.join(", ")} with verifiable links, dated observations, candidate titles and 3 honest hooks per shortlisted idea.
3. Verify Top-Tier Country Upload Best-Time windows (1–2h Shorts / 2–3h Long-Form PRIVATE upload buffer) and override with YouTube Studio's "When your viewers are on YouTube" heatmap after ~28 days of channel data.
4. Attribute every numeric volume/competition metric to vidIQ or a verified source; never fabricate metrics in Gemini mode.
5. Prepare a Digen-ready scene package (Digen only: ${v.mcp_endpoint}; never spend credits or publish publicly without explicit owner approval), render locally via FFmpeg, and sync state to Cloudflare Control Center (python3 factory.py sync).

${uploadPlan}
`;
}

/**
 * Storage Adapter:
 * 1) Uses Cloudflare D1 (env.DB) if bound (full SQL tables from cloudflare/schema.sql).
 * 2) Otherwise uses Cloudflare R2 (env.MEDIA_BUCKET) durable JSON document (_state/control-center-v2.json).
 * 3) Falls back to isolate memory for local unit tests without bindings.
 */
async function ensureD1Schema(db) {
  await db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_settings (id TEXT PRIMARY KEY DEFAULT 'global', settings_json TEXT NOT NULL, updated_at TEXT NOT NULL)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_channels (id TEXT PRIMARY KEY, name TEXT NOT NULL, handle TEXT NOT NULL, niche TEXT NOT NULL, default_aspect TEXT NOT NULL, target_countries_json TEXT NOT NULL, creator_timezone TEXT NOT NULL, studio_heatmap_override TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_ideas (id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, title TEXT NOT NULL, niche TEXT NOT NULL, score INTEGER NOT NULL, rubric TEXT NOT NULL, aspect TEXT NOT NULL, vidiq_summary TEXT NOT NULL, promise TEXT NOT NULL, upload_slot TEXT NOT NULL, hooks_json TEXT NOT NULL, sources_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_videos (slug TEXT PRIMARY KEY, channel_id TEXT NOT NULL, title TEXT NOT NULL, niche TEXT NOT NULL, aspect TEXT NOT NULL, status TEXT NOT NULL, episode_json TEXT NOT NULL, r2_final_key TEXT NOT NULL, r2_thumb_key TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_approvals (video_slug TEXT PRIMARY KEY, digen_scene1_approved INTEGER NOT NULL, digen_remaining_approved INTEGER NOT NULL, qa_approved INTEGER NOT NULL, qa_checks_json TEXT NOT NULL, private_upload_approved INTEGER NOT NULL, scheduled_publish_window TEXT NOT NULL, notes TEXT NOT NULL, updated_at TEXT NOT NULL)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_jobs (id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, video_slug TEXT NOT NULL, job_type TEXT NOT NULL, target_runner TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, result_summary TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS yaf_analytics (id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, video_slug TEXT NOT NULL, published_at TEXT NOT NULL, views_48h INTEGER NOT NULL, viewed_vs_swiped_pct REAL NOT NULL, avg_completion_pct REAL NOT NULL, ctr_pct REAL NOT NULL, top_country TEXT NOT NULL, publish_slot_used TEXT NOT NULL, studio_heatmap_peak TEXT NOT NULL, retention_notes TEXT NOT NULL, updated_at TEXT NOT NULL)`),
  ]);
}

async function loadState(env) {
  if (env.DB) {
    await ensureD1Schema(env.DB);
    const sRow = await env.DB.prepare("SELECT settings_json FROM yaf_settings WHERE id = 'global'").first();
    if (!sRow) {
      const seed = buildSeedState();
      await saveState(env, seed);
      return { state: seed, mode: "cloudflare_d1 + r2_assets" };
    }
    const [chRows, ideaRows, vidRows, appRows, jobRows, anaRows] = await Promise.all([
      env.DB.prepare("SELECT * FROM yaf_channels ORDER BY created_at ASC").all(),
      env.DB.prepare("SELECT * FROM yaf_ideas ORDER BY score DESC, updated_at DESC").all(),
      env.DB.prepare("SELECT * FROM yaf_videos ORDER BY updated_at DESC").all(),
      env.DB.prepare("SELECT * FROM yaf_approvals").all(),
      env.DB.prepare("SELECT * FROM yaf_jobs ORDER BY updated_at DESC LIMIT 50").all(),
      env.DB.prepare("SELECT * FROM yaf_analytics ORDER BY updated_at DESC").all(),
    ]);
    const approvals = {};
    for (const r of appRows.results || []) {
      approvals[r.video_slug] = {
        video_slug: r.video_slug,
        digen_scene1_approved: Boolean(r.digen_scene1_approved),
        digen_remaining_approved: Boolean(r.digen_remaining_approved),
        qa_approved: Boolean(r.qa_approved),
        qa_checks: JSON.parse(r.qa_checks_json || "[]"),
        private_upload_approved: Boolean(r.private_upload_approved),
        scheduled_publish_window: r.scheduled_publish_window,
        notes: r.notes,
        updated_at: r.updated_at,
      };
    }
    return {
      mode: env.MEDIA_BUCKET ? "cloudflare_d1 + r2_assets" : "cloudflare_d1",
      state: {
        settings: validateSettings(JSON.parse(sRow.settings_json)),
        channels: (chRows.results || []).map((r) => ({
          id: r.id,
          name: r.name,
          handle: r.handle,
          niche: r.niche,
          default_aspect: r.default_aspect,
          target_countries: JSON.parse(r.target_countries_json),
          creator_timezone: r.creator_timezone,
          studio_heatmap_override: r.studio_heatmap_override,
          status: r.status,
          updated_at: r.updated_at,
        })),
        ideas: (ideaRows.results || []).map((r) => ({
          id: r.id,
          channel_id: r.channel_id,
          title: r.title,
          niche: r.niche,
          score: r.score,
          rubric: r.rubric,
          aspect: r.aspect,
          vidiq_summary: r.vidiq_summary,
          promise: r.promise,
          upload_slot: r.upload_slot,
          hooks: JSON.parse(r.hooks_json),
          sources: JSON.parse(r.sources_json),
          status: r.status,
          updated_at: r.updated_at,
        })),
        videos: (vidRows.results || []).map((r) => ({
          ...JSON.parse(r.episode_json),
          slug: r.slug,
          channel_id: r.channel_id,
          status: r.status,
          r2_final_key: r.r2_final_key,
          r2_thumb_key: r.r2_thumb_key,
          updated_at: r.updated_at,
        })),
        approvals,
        jobs: (jobRows.results || []).map((r) => ({
          id: r.id,
          channel_id: r.channel_id,
          video_slug: r.video_slug,
          job_type: r.job_type,
          target_runner: r.target_runner,
          status: r.status,
          payload: JSON.parse(r.payload_json),
          result_summary: r.result_summary,
          created_at: r.created_at,
          updated_at: r.updated_at,
        })),
        analytics: (anaRows.results || []).map((r) => ({
          id: r.id,
          channel_id: r.channel_id,
          video_slug: r.video_slug,
          published_at: r.published_at,
          views_48h: r.views_48h,
          viewed_vs_swiped_pct: r.viewed_vs_swiped_pct,
          avg_completion_pct: r.avg_completion_pct,
          ctr_pct: r.ctr_pct,
          top_country: r.top_country,
          publish_slot_used: r.publish_slot_used,
          studio_heatmap_peak: r.studio_heatmap_peak,
          retention_notes: r.retention_notes,
          updated_at: r.updated_at,
        })),
      },
    };
  }

  if (env.MEDIA_BUCKET) {
    const obj = await env.MEDIA_BUCKET.get(R2_STATE_KEY);
    if (obj) {
      try {
        const parsed = await obj.json();
        parsed.settings = validateSettings(parsed.settings || DEFAULTS);
        return { state: parsed, mode: "cloudflare_r2_durable (youtube-ai-factory-assets)" };
      } catch {
        // Fall through to seed initialization
      }
    }
    const seed = buildSeedState();
    await env.MEDIA_BUCKET.put(R2_STATE_KEY, JSON.stringify(seed), {
      httpMetadata: { contentType: "application/json" },
    });
    return { state: seed, mode: "cloudflare_r2_durable (youtube-ai-factory-assets)" };
  }

  if (!MEMORY_FALLBACK_STATE) {
    MEMORY_FALLBACK_STATE = buildSeedState();
  }
  return { state: MEMORY_FALLBACK_STATE, mode: "worker_memory_fallback" };
}

async function saveState(env, state) {
  const ts = nowIso();
  if (env.DB) {
    await ensureD1Schema(env.DB);
    const stmts = [
      env.DB.prepare("INSERT OR REPLACE INTO yaf_settings (id, settings_json, updated_at) VALUES ('global', ?, ?)").bind(
        JSON.stringify(state.settings),
        ts
      ),
    ];
    for (const ch of state.channels || []) {
      stmts.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO yaf_channels (id, name, handle, niche, default_aspect, target_countries_json, creator_timezone, studio_heatmap_override, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          ch.id,
          ch.name,
          ch.handle,
          ch.niche,
          ch.default_aspect || "9:16",
          JSON.stringify(ch.target_countries || ["US", "UK", "CA", "AU"]),
          ch.creator_timezone || "Asia/Dhaka",
          ch.studio_heatmap_override || "",
          ch.status || "active",
          ch.created_at || ts,
          ch.updated_at || ts
        )
      );
    }
    for (const idea of state.ideas || []) {
      stmts.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO yaf_ideas (id, channel_id, title, niche, score, rubric, aspect, vidiq_summary, promise, upload_slot, hooks_json, sources_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          idea.id,
          idea.channel_id || "ch-hawthorn",
          idea.title,
          idea.niche,
          Number(idea.score || 80),
          idea.rubric || "",
          idea.aspect || "9:16",
          idea.vidiq_summary || "",
          idea.promise || "",
          idea.upload_slot || "",
          JSON.stringify(idea.hooks || []),
          JSON.stringify(idea.sources || []),
          idea.status || "shortlisted",
          idea.created_at || ts,
          idea.updated_at || ts
        )
      );
    }
    for (const vid of state.videos || []) {
      stmts.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO yaf_videos (slug, channel_id, title, niche, aspect, status, episode_json, r2_final_key, r2_thumb_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          vid.slug,
          vid.channel_id || "ch-hawthorn",
          vid.title,
          vid.niche,
          vid.aspect || "9:16",
          vid.status || "draft",
          JSON.stringify(vid),
          vid.r2_final_key || "",
          vid.r2_thumb_key || "",
          vid.created_at || ts,
          vid.updated_at || ts
        )
      );
    }
    for (const app of Object.values(state.approvals || {})) {
      stmts.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO yaf_approvals (video_slug, digen_scene1_approved, digen_remaining_approved, qa_approved, qa_checks_json, private_upload_approved, scheduled_publish_window, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          app.video_slug,
          app.digen_scene1_approved ? 1 : 0,
          app.digen_remaining_approved ? 1 : 0,
          app.qa_approved ? 1 : 0,
          JSON.stringify(app.qa_checks || [false, false, false, false, false]),
          app.private_upload_approved ? 1 : 0,
          app.scheduled_publish_window || "",
          app.notes || "",
          app.updated_at || ts
        )
      );
    }
    for (const job of state.jobs || []) {
      stmts.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO yaf_jobs (id, channel_id, video_slug, job_type, target_runner, status, payload_json, result_summary, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          job.id,
          job.channel_id || "ch-hawthorn",
          job.video_slug || "",
          job.job_type,
          job.target_runner || "local_engine",
          job.status || "queued",
          JSON.stringify(job.payload || {}),
          job.result_summary || "",
          job.created_at || ts,
          job.updated_at || ts
        )
      );
    }
    for (const ana of state.analytics || []) {
      stmts.push(
        env.DB.prepare(
          `INSERT OR REPLACE INTO yaf_analytics (id, channel_id, video_slug, published_at, views_48h, viewed_vs_swiped_pct, avg_completion_pct, ctr_pct, top_country, publish_slot_used, studio_heatmap_peak, retention_notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        ).bind(
          ana.id,
          ana.channel_id || "ch-hawthorn",
          ana.video_slug,
          ana.published_at || "",
          Number(ana.views_48h || 0),
          Number(ana.viewed_vs_swiped_pct || 0),
          Number(ana.avg_completion_pct || 0),
          Number(ana.ctr_pct || 0),
          ana.top_country || "US",
          ana.publish_slot_used || "",
          ana.studio_heatmap_peak || "",
          ana.retention_notes || "",
          ana.updated_at || ts
        )
      );
    }
    await env.DB.batch(stmts);
    return;
  }

  if (env.MEDIA_BUCKET) {
    await env.MEDIA_BUCKET.put(R2_STATE_KEY, JSON.stringify(state), {
      httpMetadata: { contentType: "application/json" },
    });
    return;
  }

  MEMORY_FALLBACK_STATE = state;
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

async function parseJsonBody(request, maxBytes = 262144) {
  const ct = (request.headers.get("Content-Type") || "").split(";")[0].trim();
  if (ct !== "application/json") {
    const err = new Error("Send application/json");
    err.status = 415;
    throw err;
  }
  const raw = await request.text();
  if (raw.length < 2 || raw.length > maxBytes) {
    throw new Error("Request body length invalid");
  }
  const data = JSON.parse(raw);
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("JSON body must be an object");
  }
  return data;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;

    if (request.method === "GET") {
      if (pathname === "/api/bootstrap") {
        const { state, mode } = await loadState(env);
        const uploadPlan = computeUploadWindows(
          "9:16",
          state.settings.research.target_countries,
          state.settings.publishing.creator_timezone
        );
        return jsonResponse(200, {
          runtime: "cloudflare_control_center",
          storageMode: mode,
          architecture: {
            phase1_local_mvp: "active_sync_supported",
            phase2_cloudflare_control_center: "live",
            phase3_cloud_queue_automation: "ready",
            r2_bucket_bound: Boolean(env.MEDIA_BUCKET),
            d1_bound: Boolean(env.DB),
            ffmpeg_location: "local_only",
          },
          ...state,
          vidiqLedger: VIDIQ_LEDGER,
          vidiqKeywords: VIDIQ_KEYWORDS,
          uploadPlan,
        });
      }

      if (pathname === "/api/settings") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.settings);
      }

      if (pathname === "/api/research-plan") {
        const topic = (url.searchParams.get("topic") || "Research 5 original YouTube niches").slice(0, 400);
        const { state } = await loadState(env);
        return new Response(buildResearchInstructions(state.settings, topic), {
          status: 200,
          headers: { "Content-Type": "text/plain; charset=utf-8", ...SECURITY_HEADERS },
        });
      }

      if (pathname === "/api/upload-plan") {
        const aspect = url.searchParams.get("aspect") || "9:16";
        if (!["9:16", "16:9"].includes(aspect)) {
          return jsonResponse(400, { error: "aspect must be 9:16 or 16:9" });
        }
        const { state } = await loadState(env);
        const countriesParam = url.searchParams.get("countries");
        const countries = countriesParam
          ? countriesParam
              .split(",")
              .map((c) => c.trim().toUpperCase())
              .filter(Boolean)
          : state.settings.research.target_countries;
        const tz = url.searchParams.get("tz") || state.settings.publishing.creator_timezone;
        const refDate = url.searchParams.get("date");
        try {
          return jsonResponse(200, computeUploadWindows(aspect, countries, tz, refDate));
        } catch (err) {
          return jsonResponse(400, { error: err instanceof Error ? err.message : "Invalid timezone" });
        }
      }

      if (pathname === "/api/channels") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.channels);
      }
      if (pathname === "/api/ideas") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.ideas);
      }
      if (pathname === "/api/videos") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.videos);
      }
      if (pathname === "/api/approvals") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.approvals);
      }
      if (pathname === "/api/jobs") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.jobs);
      }
      if (pathname === "/api/analytics") {
        const { state } = await loadState(env);
        return jsonResponse(200, state.analytics);
      }
      if (pathname === "/api/sync") {
        const { state } = await loadState(env);
        return jsonResponse(200, state);
      }

      const mediaMatch = pathname.match(SAFE_MEDIA_RE);
      if (mediaMatch) {
        if (!env.MEDIA_BUCKET) {
          return jsonResponse(404, { error: "R2 MEDIA_BUCKET is not bound" });
        }
        const [, slug, fname] = mediaMatch;
        const obj = await env.MEDIA_BUCKET.get(`videos/${slug}/${fname}`);
        if (!obj) {
          return jsonResponse(404, { error: "Media file not found in R2" });
        }
        const headers = new Headers(SECURITY_HEADERS);
        obj.writeHttpMetadata(headers);
        if (!headers.get("Content-Type")) {
          headers.set("Content-Type", fname.endsWith(".mp4") ? "video/mp4" : "image/jpeg");
        }
        return new Response(obj.body, { status: 200, headers });
      }
    }

    if (request.method === "PUT") {
      const origin = request.headers.get("Origin");
      if (origin && origin !== url.origin) {
        return jsonResponse(403, { error: "Origin not allowed" });
      }
      const mediaMatch = pathname.match(SAFE_MEDIA_RE);
      if (mediaMatch) {
        if (!env.MEDIA_BUCKET) {
          return jsonResponse(503, { error: "R2 bucket binding unavailable" });
        }
        const [, slug, fname] = mediaMatch;
        if (!/\.(mp4|jpg|jpeg|png)$/i.test(fname)) {
          return jsonResponse(400, { error: "Only .mp4, .jpg, or .png media files are accepted" });
        }
        const contentType = fname.endsWith(".mp4") ? "video/mp4" : fname.endsWith(".png") ? "image/png" : "image/jpeg";
        const bodyBuf = await request.arrayBuffer();
        if (bodyBuf.byteLength === 0 || bodyBuf.byteLength > 80 * 1024 * 1024) {
          return jsonResponse(400, { error: "Media upload must be between 1B and 80MB" });
        }
        const r2Key = `videos/${slug}/${fname}`;
        await env.MEDIA_BUCKET.put(r2Key, bodyBuf, { httpMetadata: { contentType } });
        const { state } = await loadState(env);
        const vid = state.videos.find((v) => v.slug === slug);
        if (vid) {
          const sceneMatch = fname.match(/^scene-(\d+)\.mp4$/);
          if (sceneMatch) {
            const idx = Number(sceneMatch[1]) - 1;
            if (vid.scenes[idx]) {
              vid.scenes[idx].clipStatus = "ready";
              vid.scenes[idx].clipUrl = `/api/media/${slug}/${fname}`;
            }
          } else if (fname.startsWith("final")) {
            vid.r2_final_key = r2Key;
          } else if (fname.startsWith("preview")) {
            vid.r2_thumb_key = r2Key;
          }
          vid.updated_at = nowIso();
          await saveState(env, state);
        }
        return jsonResponse(200, { ok: true, key: r2Key, url: `/api/media/${slug}/${fname}`, bytes: bodyBuf.byteLength });
      }
    }

    if (request.method === "POST" && pathname.startsWith("/api/")) {
      const origin = request.headers.get("Origin");
      if (origin && origin !== url.origin) {
        return jsonResponse(403, { error: "Origin not allowed" });
      }
      try {
        const body = await parseJsonBody(request);
        const { state } = await loadState(env);
        const ts = nowIso();

        if (pathname === "/api/research-settings") {
          const allowed = new Set(["provider", "depth", "fallback_to_gemini", "target_countries", "creator_timezone"]);
          for (const k of Object.keys(body)) {
            if (!allowed.has(k)) {
              throw new Error("Only provider, depth, fallback_to_gemini, target_countries, and creator_timezone can be updated");
            }
          }
          const next = cloneJson(state.settings);
          if ("creator_timezone" in body) {
            next.publishing.creator_timezone = body.creator_timezone;
            delete body.creator_timezone;
          }
          Object.assign(next.research, body);
          state.settings = validateSettings(next);
          await saveState(env, state);
          return jsonResponse(200, state.settings);
        }

        if (pathname === "/api/channels") {
          const name = String(body.name || "").trim();
          if (!name) throw new Error("Channel name is required");
          const id = slugify(body.id || `ch-${name}`);
          let handle = String(body.handle || `@${id.replace(/-/g, "")}`).trim();
          if (!handle.startsWith("@")) handle = `@${handle}`;
          const aspect = String(body.default_aspect || "9:16");
          if (!["9:16", "16:9"].includes(aspect)) throw new Error("default_aspect must be 9:16 or 16:9");
          const countries = Array.isArray(body.target_countries)
            ? body.target_countries.map((c) => String(c).trim().toUpperCase()).filter(Boolean)
            : String(body.target_countries || "US,UK,CA,AU")
                .split(",")
                .map((c) => c.trim().toUpperCase())
                .filter(Boolean);
          const creatorTz = validateTimezone(String(body.creator_timezone || "Asia/Dhaka"));
          const rec = {
            id,
            name,
            handle,
            niche: String(body.niche || "Original Micro-Stories").trim(),
            default_aspect: aspect,
            target_countries: countries.length ? countries : ["US", "UK", "CA", "AU"],
            creator_timezone: creatorTz,
            studio_heatmap_override: String(body.studio_heatmap_override || "").slice(0, 300),
            status: String(body.status || "active"),
            updated_at: ts,
          };
          const idx = state.channels.findIndex((c) => c.id === id);
          if (idx >= 0) state.channels[idx] = rec;
          else state.channels.push(rec);
          await saveState(env, state);
          return jsonResponse(200, rec);
        }

        if (pathname === "/api/ideas") {
          const title = String(body.title || "").trim();
          if (!title) throw new Error("Idea title is required");
          const id = slugify(body.id || `idea-${title}`);
          const aspect = String(body.aspect || "9:16");
          if (!["9:16", "16:9"].includes(aspect)) throw new Error("aspect must be 9:16 or 16:9");
          const hooks = Array.isArray(body.hooks)
            ? body.hooks.map((h) => String(h).trim()).filter(Boolean)
            : String(body.hooks || "")
                .split("\n")
                .map((h) => h.trim())
                .filter(Boolean);
          const score = Math.max(1, Math.min(100, Number(body.score || 82)));
          const rec = {
            id,
            channel_id: String(body.channel_id || "ch-hawthorn"),
            title,
            niche: String(body.niche || "Original Format").trim(),
            score,
            rubric: String(body.rubric || `Composite Score ${score}/100`),
            aspect,
            vidiq_summary: String(body.vidiq_summary || "Qualitative / Gemini research entry (unverified search volume)"),
            promise: String(body.promise || ""),
            upload_slot: String(body.upload_slot || "Wed/Thu/Fri 12:00–14:00 ET (22:00–00:00 BDT)"),
            hooks,
            sources: Array.isArray(body.sources) ? body.sources : [],
            status: String(body.status || "shortlisted"),
            updated_at: ts,
          };
          const idx = state.ideas.findIndex((i) => i.id === id);
          if (idx >= 0) state.ideas[idx] = rec;
          else state.ideas.unshift(rec);
          await saveState(env, state);
          return jsonResponse(200, rec);
        }

        if (pathname === "/api/ideas/promote") {
          const idea = state.ideas.find((i) => i.id === body.idea_id);
          if (!idea) throw new Error(`Unknown idea_id: ${body.idea_id}`);
          const slug = slugify(body.slug || idea.title);
          const hook1 = idea.hooks?.[0] || idea.title;
          const promoted = {
            slug,
            channel_id: idea.channel_id,
            title: idea.title,
            niche: idea.niche,
            target_audience: "English-speaking US, UK, Canadian, and Australian viewers",
            aspect: idea.aspect || "9:16",
            status: "prompts-packed",
            made_for_kids: false,
            contains_synthetic_media: true,
            hooks: (idea.hooks || [idea.title]).slice(0, 3),
            style_bible: `Stylized 3D visual continuity for ${idea.niche}. Crisp macro lighting, stable proportions across every shot, zero text or watermarks.`,
            script: `${hook1} ${idea.promise} Watch how one tiny mechanism changes everything in seconds.`,
            scenes: [
              {
                name: "Hook Contrast Shot (0–8s)",
                duration_seconds: 8,
                narration: hook1,
                prompt: `Vertical ${idea.aspect} stylized 3D macro opening shot for '${idea.title}'. Immediate visual contrast in frame 1, shallow depth of field, smooth push-in, zero text.`,
                clipStatus: "missing",
                clipUrl: "",
              },
              {
                name: "Core Mechanism / Escalation (8–16s)",
                duration_seconds: 8,
                narration: idea.promise,
                prompt: `Vertical ${idea.aspect} cutaway close-up continuing exact visual continuity for '${idea.title}'. Clear physical motion showing the central detail in action, no text.`,
                clipStatus: "missing",
                clipUrl: "",
              },
              {
                name: "Resolution & Payoff (16–24s)",
                duration_seconds: 8,
                narration: "That single hidden detail makes the entire system work safely.",
                prompt: `Vertical ${idea.aspect} satisfying pull-back reveal shot resolving '${idea.title}' with warm lighting contrast and coherent proportions, zero text.`,
                clipStatus: "missing",
                clipUrl: "",
              },
            ],
            seo: {
              title: `${idea.title} ✨`,
              description: `${idea.promise}\n\n#Shorts #OriginalAnimation`,
              tags: [idea.niche.toLowerCase(), "animated short", "how things work", "micro story"],
              thumbnail_brief: `Extreme high-contrast close-up of the central visual subject in '${idea.title}', mobile-legible, zero clickbait.`,
            },
            r2_final_key: "",
            r2_thumb_key: "",
            updated_at: ts,
          };
          idea.status = "in-production";
          const vIdx = state.videos.findIndex((v) => v.slug === slug);
          if (vIdx >= 0) state.videos[vIdx] = promoted;
          else state.videos.unshift(promoted);
          if (!state.approvals[slug]) {
            state.approvals[slug] = {
              video_slug: slug,
              digen_scene1_approved: false,
              digen_remaining_approved: false,
              qa_approved: false,
              qa_checks: [false, false, false, false, false],
              private_upload_approved: false,
              scheduled_publish_window: idea.upload_slot || "Wed/Thu/Fri 22:00–00:00 Asia/Dhaka",
              notes: "Promoted from Ideas backlog. Awaiting Scene-01 credit gate.",
              updated_at: ts,
            };
          }
          await saveState(env, state);
          return jsonResponse(200, promoted);
        }

        if (pathname === "/api/videos") {
          const slug = slugify(body.slug || body.title);
          const title = String(body.title || slug).trim();
          const aspect = String(body.aspect || "9:16");
          if (!["9:16", "16:9"].includes(aspect)) throw new Error("aspect must be 9:16 or 16:9");
          if (!Array.isArray(body.scenes) || body.scenes.length === 0) {
            throw new Error("Video episode must include at least 1 scene");
          }
          const scenes = body.scenes.map((s, i) => {
            const prompt = String(s.prompt || "").trim();
            if (!prompt) throw new Error(`Scene ${i + 1} prompt cannot be empty`);
            return {
              name: String(s.name || `Scene ${i + 1}`).trim(),
              duration_seconds: Math.max(1, Math.min(120, Number(s.duration_seconds || 8))),
              narration: String(s.narration || "").trim(),
              prompt,
              clipStatus: String(s.clipStatus || "missing"),
              clipUrl: String(s.clipUrl || ""),
            };
          });
          const seoIn = body.seo || {};
          const tags = Array.isArray(seoIn.tags)
            ? seoIn.tags
            : String(seoIn.tags || "")
                .split(",")
                .map((t) => t.trim())
                .filter(Boolean);
          const rec = {
            slug,
            channel_id: String(body.channel_id || "ch-hawthorn"),
            title,
            niche: String(body.niche || "Original Micro-Stories"),
            target_audience: String(body.target_audience || "English-speaking US, UK, Canadian, and Australian viewers"),
            aspect,
            status: String(body.status || "prompts-packed"),
            made_for_kids: Boolean(body.made_for_kids),
            contains_synthetic_media: body.contains_synthetic_media !== false,
            hooks: Array.isArray(body.hooks) ? body.hooks.slice(0, 3) : [title, "", ""],
            style_bible: String(body.style_bible || "Maintain strict character and lighting continuity across all shots."),
            script: String(body.script || ""),
            scenes,
            seo: {
              title: String(seoIn.title || title),
              description: String(seoIn.description || ""),
              tags,
              thumbnail_brief: String(seoIn.thumbnail_brief || ""),
            },
            r2_final_key: String(body.r2_final_key || ""),
            r2_thumb_key: String(body.r2_thumb_key || ""),
            updated_at: ts,
          };
          const idx = state.videos.findIndex((v) => v.slug === slug);
          if (idx >= 0) state.videos[idx] = rec;
          else state.videos.unshift(rec);
          if (!state.approvals[slug]) {
            state.approvals[slug] = {
              video_slug: slug,
              digen_scene1_approved: false,
              digen_remaining_approved: false,
              qa_approved: false,
              qa_checks: [false, false, false, false, false],
              private_upload_approved: false,
              scheduled_publish_window: "Wed/Thu/Fri 22:00–00:00 Asia/Dhaka",
              notes: "Awaiting Scene-01 credit gate.",
              updated_at: ts,
            };
          }
          await saveState(env, state);
          return jsonResponse(200, rec);
        }

        if (pathname === "/api/approvals") {
          const slug = slugify(body.video_slug);
          const cur = state.approvals[slug] || {
            video_slug: slug,
            digen_scene1_approved: false,
            digen_remaining_approved: false,
            qa_approved: false,
            qa_checks: [false, false, false, false, false],
            private_upload_approved: false,
            scheduled_publish_window: "",
            notes: "",
          };
          for (const k of ["digen_scene1_approved", "digen_remaining_approved", "qa_approved", "private_upload_approved"]) {
            if (k in body) cur[k] = Boolean(body[k]);
          }
          if (cur.digen_remaining_approved && !cur.digen_scene1_approved) {
            throw new Error("Scene-01 credit gate must be approved before approving remaining Digen scenes");
          }
          if (cur.private_upload_approved && !cur.qa_approved) {
            throw new Error("QA checklist gate must be approved before approving Private YouTube upload");
          }
          if (Array.isArray(body.qa_checks)) cur.qa_checks = body.qa_checks.slice(0, 5).map(Boolean);
          if ("scheduled_publish_window" in body) cur.scheduled_publish_window = String(body.scheduled_publish_window).slice(0, 300);
          if ("notes" in body) cur.notes = String(body.notes).slice(0, 500);
          cur.updated_at = ts;
          state.approvals[slug] = cur;
          const vid = state.videos.find((v) => v.slug === slug);
          if (vid) {
            if (cur.private_upload_approved) vid.status = "approved-for-upload";
            else if (cur.qa_approved) vid.status = "qa-passed";
            else if (cur.digen_scene1_approved) vid.status = "scene-1-approved";
          }
          await saveState(env, state);
          return jsonResponse(200, cur);
        }

        if (pathname === "/api/jobs") {
          const allowed = new Set([
            "research_niches",
            "pack_prompts",
            "digen_scene_01",
            "digen_remaining_scenes",
            "ffmpeg_render_local",
            "youtube_private_upload",
          ]);
          const jobType = String(body.job_type || "");
          if (!allowed.has(jobType)) throw new Error(`Unsupported job_type: ${jobType}`);
          const slug = slugify(body.video_slug || "pilot-01");
          const app = state.approvals[slug] || {};
          let status = "queued";
          if (jobType === "digen_scene_01" && !app.digen_scene1_approved) status = "awaiting_approval";
          if (jobType === "digen_remaining_scenes" && !app.digen_remaining_approved) status = "awaiting_approval";
          if (jobType === "youtube_private_upload" && !app.private_upload_approved) status = "awaiting_approval";
          const job = {
            id: `job-${Math.random().toString(36).slice(2, 10)}`,
            channel_id: String(body.channel_id || "ch-hawthorn"),
            video_slug: slug,
            job_type: jobType,
            target_runner: "local_engine",
            status,
            payload: body.payload && typeof body.payload === "object" ? body.payload : {},
            result_summary:
              status === "awaiting_approval"
                ? "Blocked until human approval gate is checked."
                : "Queued for Local Engine sync (python3 factory.py sync).",
            created_at: ts,
            updated_at: ts,
          };
          state.jobs.unshift(job);
          state.jobs = state.jobs.slice(0, 50);
          await saveState(env, state);
          return jsonResponse(200, job);
        }

        if (pathname === "/api/jobs/complete") {
          const job = state.jobs.find((j) => j.id === body.job_id);
          if (!job) throw new Error(`Unknown job_id: ${body.job_id}`);
          job.status = String(body.status || "completed");
          job.result_summary = String(body.result_summary || "").slice(0, 500);
          job.updated_at = ts;
          await saveState(env, state);
          return jsonResponse(200, job);
        }

        if (pathname === "/api/analytics") {
          const slug = slugify(body.video_slug);
          const id = String(body.id || `ana-${slug}`);
          const heatmap = String(body.studio_heatmap_peak || "").trim().slice(0, 200);
          const rec = {
            id,
            channel_id: String(body.channel_id || "ch-hawthorn"),
            video_slug: slug,
            published_at: String(body.published_at || ts.slice(0, 10)),
            views_48h: Math.max(0, Number(body.views_48h || 0)),
            viewed_vs_swiped_pct: Math.max(0, Math.min(100, Number(body.viewed_vs_swiped_pct || 0))),
            avg_completion_pct: Math.max(0, Math.min(200, Number(body.avg_completion_pct || 0))),
            ctr_pct: Math.max(0, Math.min(100, Number(body.ctr_pct || 0))),
            top_country: String(body.top_country || "US").toUpperCase().slice(0, 10),
            publish_slot_used: String(body.publish_slot_used || ""),
            studio_heatmap_peak: heatmap,
            retention_notes: String(body.retention_notes || "").slice(0, 600),
            updated_at: ts,
          };
          const idx = state.analytics.findIndex((a) => a.id === id);
          if (idx >= 0) state.analytics[idx] = rec;
          else state.analytics.unshift(rec);
          if (heatmap) {
            const ch = state.channels.find((c) => c.id === rec.channel_id);
            if (ch) ch.studio_heatmap_override = heatmap;
          }
          await saveState(env, state);
          return jsonResponse(200, rec);
        }

        if (pathname === "/api/sync") {
          if (body.settings) state.settings = validateSettings(body.settings);
          if (Array.isArray(body.channels) && body.channels.length) state.channels = body.channels;
          if (Array.isArray(body.ideas) && body.ideas.length) state.ideas = body.ideas;
          if (Array.isArray(body.videos) && body.videos.length) state.videos = body.videos;
          if (body.approvals && typeof body.approvals === "object") {
            state.approvals = { ...state.approvals, ...body.approvals };
          }
          if (Array.isArray(body.analytics)) state.analytics = body.analytics;
          await saveState(env, state);
          return jsonResponse(200, { ok: true, synced_at: ts, videos: state.videos.length, ideas: state.ideas.length });
        }

        return jsonResponse(404, { error: "Not found" });
      } catch (err) {
        const status = err && typeof err === "object" && "status" in err ? err.status : 400;
        return jsonResponse(status, { error: err instanceof Error ? err.message : "Bad request" });
      }
    }

    if (pathname.startsWith("/api/")) {
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

  async scheduled(_event, env) {
    // Phase 3 Cloud Coordinator readiness: unlocks awaiting_approval jobs once human gates are checked,
    // without initiating unapproved paid Digen or external AI calls.
    const { state } = await loadState(env);
    let changed = false;
    for (const job of state.jobs || []) {
      if (job.status === "awaiting_approval") {
        const app = state.approvals[job.video_slug] || {};
        const unlocked =
          (job.job_type === "digen_scene_01" && app.digen_scene1_approved) ||
          (job.job_type === "digen_remaining_scenes" && app.digen_remaining_approved) ||
          (job.job_type === "youtube_private_upload" && app.private_upload_approved);
        if (unlocked) {
          job.status = "queued";
          job.result_summary = "Approval gate verified by scheduled coordinator; ready for worker.";
          job.updated_at = nowIso();
          changed = true;
        }
      }
    }
    if (changed) {
      await saveState(env, state);
    }
  },
};
