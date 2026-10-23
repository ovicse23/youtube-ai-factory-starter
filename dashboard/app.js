"use strict";

(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    runtime: "hybrid",
    storageMode: "loading",
    activeView: "channels",
    selectedChannelId: "all",
    selectedVideoSlug: "pilot-01",
    pendingGateSceneIndex: 0,
    settings: null,
    channels: [],
    ideas: [],
    videos: [],
    approvals: {},
    jobs: [],
    analytics: [],
    vidiqLedger: (window.YAF_SEED_DATA && window.YAF_SEED_DATA.vidiqLedger) || {},
    vidiqKeywords: (window.YAF_SEED_DATA && window.YAF_SEED_DATA.vidiqKeywords) || [],
    uploadPlan: null,
  };

  let toastTimer = null;
  function toast(message, isError = false) {
    const el = $("#global-toast");
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
    el.classList.toggle("error", Boolean(isError));
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.hidden = true;
    }, 4200);
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined) continue;
      if (k === "className") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "dataset") {
        for (const [dk, dv] of Object.entries(v)) node.dataset[dk] = dv;
      } else if (typeof v === "boolean") {
        if (v) node.setAttribute(k, "");
      } else {
        node.setAttribute(k, String(v));
      }
    }
    for (const child of children) {
      if (child === null || child === undefined) continue;
      node.append(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  async function apiJson(path, options = {}) {
    const opts = { ...options };
    opts.headers = { ...(options.headers || {}) };
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof ArrayBuffer) && !(opts.body instanceof Blob)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const resp = await fetch(path, opts);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.error || `Request failed (${resp.status})`);
    }
    return data;
  }

  // Mandatory Safari / cross-browser fallback for <dialog closedby="any">
  function setupDialogFallbacks() {
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      $$("dialog").forEach((dialog) => {
        dialog.addEventListener("click", (event) => {
          if (event.target !== dialog) return;
          const rect = dialog.getBoundingClientRect();
          const isDialogContent =
            rect.top <= event.clientY &&
            event.clientY <= rect.top + rect.height &&
            rect.left <= event.clientX &&
            event.clientX <= rect.left + rect.width;
          if (isDialogContent) return;
          dialog.close();
        });
      });
    }
    $$("[data-close-dialog]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dlg = document.getElementById(btn.dataset.closeDialog);
        if (dlg) dlg.close();
      });
    });
  }

  function switchView(viewName) {
    state.activeView = viewName;
    $$(".nav-btn").forEach((btn) => {
      if (btn.dataset.view === viewName) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    });
    $$(".view-panel").forEach((panel) => {
      panel.hidden = panel.id !== `view-${viewName}`;
    });
  }

  function getActiveVideo() {
    const scoped = filterByChannel(state.videos);
    return (
      state.videos.find((v) => v.slug === state.selectedVideoSlug) ||
      scoped[0] ||
      state.videos[0] ||
      null
    );
  }

  function filterByChannel(items) {
    if (state.selectedChannelId === "all") return items;
    return items.filter((item) => item.channel_id === state.selectedChannelId);
  }

  function packScenePrompt(video, scene, index) {
    return [
      `PROJECT: ${video.title}`,
      `ASPECT RATIO: ${video.aspect}`,
      `TARGET DURATION: ${scene.duration_seconds} seconds`,
      `GLOBAL CONTINUITY: ${video.style_bible || "Maintain strict character and lighting continuity."}`,
      `SCENE ${String(index + 1).padStart(2, "0")}: ${scene.name || "Untitled"}`,
      `VIDEO PROMPT:\n${scene.prompt}`,
      `NARRATION/VOICE (if supported): ${scene.narration || ""}`,
      "Avoid copyrighted characters, deceptive realism and unwanted on-screen text.",
    ].join("\n");
  }

  function renderTopbarAndSidebar() {
    const s = state.settings;
    const isCloud = state.runtime.includes("cloudflare");
    $("#runtime-mode-pill").textContent = isCloud ? "Cloudflare Control Center" : "Local Engine (127.0.0.1)";
    const activeCh = state.channels.find((c) => c.id === state.selectedChannelId);
    $("#active-channel-pill").textContent = activeCh ? `Channel: ${activeCh.name}` : `All Channels (${state.channels.length})`;
    if (s) {
      const modeLabel = s.research.provider.toUpperCase();
      $("#active-provider-pill").textContent = `Research: ${modeLabel}`;
      $("#sidebar-markets").textContent = s.research.target_countries.join(", ");
    }

    const sel = $("#sidebar-channel-select");
    const prev = state.selectedChannelId;
    sel.replaceChildren(el("option", { value: "all", text: `All Channels (${state.channels.length})` }));
    state.channels.forEach((ch) => {
      sel.append(el("option", { value: ch.id, text: `${ch.name} (${ch.handle})` }));
    });
    sel.value = state.channels.some((c) => c.id === prev) ? prev : "all";

    // Populate channel dropdowns inside modals & editors
    ["#ep-channel", "#idea-channel", "#new-ep-channel"].forEach((id) => {
      const box = $(id);
      if (!box) return;
      const cur = box.value;
      box.replaceChildren();
      state.channels.forEach((ch) => {
        box.append(el("option", { value: ch.id, text: `${ch.name} (${ch.handle})` }));
      });
      if (state.channels.some((c) => c.id === cur)) box.value = cur;
      else if (state.selectedChannelId !== "all") box.value = state.selectedChannelId;
    });

    if (state.uploadPlan && state.uploadPlan.slots && state.uploadPlan.slots[0]) {
      const slot = state.uploadPlan.slots[0];
      $("#sidebar-next-slot").textContent = `${slot.best_days.slice(0, 3).join("/")} · Public ${slot.creator_local.public_publish}`;
    }
  }

  function renderChannelsView() {
    const s = state.settings;
    const scopedIdeas = filterByChannel(state.ideas);
    const scopedVideos = filterByChannel(state.videos);
    $("#kpi-channels-count").textContent = `${state.channels.length} Channel${state.channels.length === 1 ? "" : "s"}`;
    $("#kpi-storage-mode").textContent = state.storageMode;
    if (s) {
      const pMap = { auto: "Auto (vidIQ + Gemini)", vidiq: "vidIQ MCP Primary", gemini: "Gemini + Local Skills" };
      $("#kpi-provider").textContent = pMap[s.research.provider] || s.research.provider;
      $("#kpi-tz-label").textContent = s.publishing.creator_timezone;
    }
    $("#kpi-vidiq-credits").textContent = `vidIQ ${state.vidiqLedger.planName || "Max"}: ${state.vidiqLedger.totalCredits || 6142} credits`;
    $("#kpi-pipeline-counts").textContent = `${scopedIdeas.length} Ideas · ${scopedVideos.length} Videos`;
    const queuedCount = state.jobs.filter((j) => j.status === "queued" || j.status === "awaiting_approval").length;
    $("#kpi-queue-summary").textContent = `${queuedCount} active queue item${queuedCount === 1 ? "" : "s"}`;

    if (state.uploadPlan && state.uploadPlan.slots && state.uploadPlan.slots[0]) {
      const primary = state.uploadPlan.slots[0];
      $("#kpi-publish-time").textContent = primary.creator_local.public_publish.split(" ")[0];
      $("#kpi-private-buffer").textContent = `PRIVATE ${primary.creator_local.private_upload} (${primary.best_days.slice(0, 3).join("/")})`;
    }

    const grid = $("#channels-card-grid");
    grid.replaceChildren();
    state.channels.forEach((ch) => {
      const isFocused = state.selectedChannelId === ch.id;
      const vidCount = state.videos.filter((v) => v.channel_id === ch.id).length;
      const ideaCount = state.ideas.filter((i) => i.channel_id === ch.id).length;

      const focusBtn = el("button", {
        type: "button",
        className: isFocused ? "sm" : "secondary sm",
        text: isFocused ? "Focused Channel ✓" : "Focus Channel",
      });
      focusBtn.addEventListener("click", () => {
        state.selectedChannelId = isFocused ? "all" : ch.id;
        renderAll();
      });

      const ideasBtn = el("button", { type: "button", className: "ghost sm", text: `Open Ideas (${ideaCount})` });
      ideasBtn.addEventListener("click", () => {
        state.selectedChannelId = ch.id;
        renderAll();
        switchView("ideas");
      });

      const card = el("article", { className: "subgrid-card" }, [
        el("div", {}, [
          el("div", { className: "scene-head" }, [
            el("strong", { text: ch.name }),
            el("span", { className: "pill pill-good", text: ch.handle }),
          ]),
          el("div", { className: "hint", text: `${ch.niche} · Default ${ch.default_aspect}` }),
        ]),
        el("div", {}, [
          el("p", {
            text: `Target Tier-1 Markets: ${(ch.target_countries || []).join(", ")} · Creator TZ: ${ch.creator_timezone} · ${vidCount} video(s) in studio.`,
          }),
          el("div", {
            className: "hint",
            text: ch.studio_heatmap_override
              ? `28-Day Studio Heatmap Override: ${ch.studio_heatmap_override}`
              : "28-Day Studio Heatmap: Using research benchmarks until 28d channel data accumulates.",
          }),
        ]),
        el("div", { className: "btn-row" }, [focusBtn, ideasBtn]),
      ]);
      grid.append(card);
    });

    const remoteOrigin = window.location.origin.includes("127.0.0.1")
      ? "https://youtube-ai-factory.ovi-cse23.workers.dev"
      : window.location.origin;
    $("#sync-cli-commands").textContent = [
      "# Phase 1 Local Engine <-> Phase 2 Cloudflare Control Center Sync",
      `python3 factory.py sync --mode pull --remote ${remoteOrigin}   # Pull online channel/idea/gate edits locally`,
      "python3 factory.py pack pilot-01                               # Pack Digen scene prompts + Top-Tier schedule",
      "python3 factory.py render pilot-01                             # Stitch MP4 clips locally with FFmpeg (0 Workers CPU)",
      `python3 factory.py sync --mode push --remote ${remoteOrigin}   # Push local episodes, status & analytics to Cloudflare`,
    ].join("\n");
  }

  function describeProviderSelection() {
    const provider = document.querySelector('input[name="provider"]:checked')?.value || "auto";
    const fb = $("#settings-fallback").checked;
    $("#settings-fallback").disabled = provider === "gemini";
    const explainMap = {
      gemini:
        "Gemini-only mode: Uses Antigravity + web citations + local YouTube Skills. vidIQ MCP will never be called or charged.",
      vidiq: fb
        ? "vidIQ primary: Queries live vidIQ MCP metrics first and falls back to qualitative Gemini research if unavailable."
        : "Strict vidIQ mode: Uses vidIQ MCP exclusively; stops immediately if disconnected or out of credits.",
      auto: fb
        ? "Auto mode: Prefers live vidIQ MCP when connected and funded; falls back transparently to Gemini + web."
        : "Auto (no fallback): Checks vidIQ MCP first and halts if unavailable because Gemini fallback is disabled.",
    };
    $("#settings-explain").textContent = explainMap[provider];
  }

  function renderProviderView() {
    const s = state.settings;
    if (!s) return;
    const radio = document.querySelector(`input[name="provider"][value="${s.research.provider}"]`);
    if (radio) radio.checked = true;
    $("#settings-depth").value = s.research.depth;
    $("#settings-tz").value = s.publishing.creator_timezone;
    $("#settings-fallback").checked = Boolean(s.research.fallback_to_gemini);
    const activeSet = new Set(s.research.target_countries || []);
    $$(".provider-country-cb").forEach((cb) => {
      cb.checked = activeSet.has(cb.value);
    });
    describeProviderSelection();
    $("#master-prompt-box").textContent =
      (window.YAF_SEED_DATA && window.YAF_SEED_DATA.masterPrompt) || "See MASTER_PROMPT.md in workspace.";
  }

  function renderIdeasView() {
    const query = ($("#idea-search-input")?.value || "").trim().toLowerCase();

    const kwBody = $("#vidiq-table-body");
    kwBody.replaceChildren();
    state.vidiqKeywords
      .filter((row) => !query || JSON.stringify(row).toLowerCase().includes(query))
      .forEach((row) => {
        kwBody.append(
          el("tr", {}, [
            el("th", { scope: "row", text: row.keyword }),
            el("td", { text: `${row.overall}` }),
            el("td", { text: `${row.competition} (${row.competitionLabel})` }),
            el("td", { text: row.monthlySearches }),
            el("td", { text: row.usVolume }),
            el("td", { text: row.growth30d }),
            el("td", { text: row.topOpportunity }),
          ])
        );
      });

    const cards = $("#ideas-card-grid");
    cards.replaceChildren();
    filterByChannel(state.ideas)
      .filter((idea) => !query || JSON.stringify(idea).toLowerCase().includes(query))
      .forEach((idea) => {
        const promoteBtn = el("button", { type: "button", className: "sm", text: "Promote to Video →" });
        promoteBtn.addEventListener("click", async () => {
          try {
            const promoted = await apiJson("/api/ideas/promote", {
              method: "POST",
              body: { idea_id: idea.id },
            });
            await refreshBootstrap(false);
            state.selectedVideoSlug = promoted.slug;
            renderAll();
            switchView("videos");
            toast(`Promoted "${promoted.title}" into Videos Studio!`);
          } catch (err) {
            toast(err.message, true);
          }
        });

        const hooksList = el("ol", { className: "arch-list" });
        (idea.hooks || []).slice(0, 3).forEach((h) => hooksList.append(el("li", { text: h })));

        const srcLinks = el("div", { className: "tag-list" });
        (idea.sources || []).forEach((src) => {
          srcLinks.append(
            el("a", {
              href: src.url,
              target: "_blank",
              rel: "noopener noreferrer",
              className: "pill",
              text: `↗ ${src.label}`,
            })
          );
        });

        cards.append(
          el("article", { className: "subgrid-card" }, [
            el("div", {}, [
              el("div", { className: "scene-head" }, [
                el("strong", { text: idea.title }),
                el("span", { className: "pill pill-good", text: `${idea.score}/100` }),
              ]),
              el("div", { className: "hint", text: `${idea.niche} · ${idea.aspect} · ${idea.status}` }),
              el("div", { className: "hint", text: idea.vidiq_summary }),
            ]),
            el("div", {}, [
              el("p", { text: idea.promise }),
              el("div", { className: "field-label", text: "3-Hook Blueprint (1–3s):" }),
              hooksList,
              el("div", { className: "hint", text: `Best Slot: ${idea.upload_slot}` }),
            ]),
            el("div", { className: "scene-head" }, [srcLinks, promoteBtn]),
          ])
        );
      });
  }

  function updateScriptTimingHint() {
    const scriptText = ($("#ep-script")?.value || "").trim();
    const words = scriptText ? scriptText.split(/\s+/).length : 0;
    const estSec = Math.round(words / 2.4);
    const sceneDurs = $$(".scene-dur-input").reduce((acc, inp) => acc + (Number(inp.value) || 0), 0);
    $("#script-timing-hint").textContent = `${words} words · ~${estSec}s spoken narration vs ${sceneDurs}s total scene duration`;
  }

  function collectVideoFormPayload() {
    const cur = getActiveVideo() || {};
    const scenes = $$(".scene-editor-row").map((row, idx) => ({
      name: $(".scene-name-input", row).value.trim() || `Scene ${idx + 1}`,
      duration_seconds: Number($(".scene-dur-input", row).value || 8),
      narration: $(".scene-narr-input", row).value.trim(),
      prompt: $(".scene-prompt-input", row).value.trim(),
      clipStatus: row.dataset.clipStatus || "missing",
      clipUrl: row.dataset.clipUrl || "",
    }));
    return {
      slug: cur.slug || "pilot-01",
      channel_id: $("#ep-channel").value || "ch-hawthorn",
      title: $("#ep-title").value.trim(),
      niche: $("#ep-niche").value.trim(),
      aspect: $("#ep-aspect").value,
      status: cur.status || "prompts-packed",
      style_bible: $("#ep-style-bible").value.trim(),
      hooks: [$("#ep-hook-1").value.trim(), $("#ep-hook-2").value.trim(), $("#ep-hook-3").value.trim()],
      script: $("#ep-script").value.trim(),
      scenes,
      seo: {
        title: $("#ep-seo-title").value.trim(),
        tags: $("#ep-seo-tags").value
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        description: $("#ep-seo-desc").value.trim(),
        thumbnail_brief: $("#ep-seo-thumb").value.trim(),
      },
      contains_synthetic_media: $("#ep-synthetic").checked,
      made_for_kids: $("#ep-kids").checked,
    };
  }

  function renderSceneEditorRow(scene, index) {
    const nameInput = el("input", { type: "text", className: "scene-name-input", value: scene.name || `Scene ${index + 1}` });
    const durInput = el("input", {
      type: "number",
      className: "scene-dur-input",
      min: "1",
      max: "120",
      value: String(scene.duration_seconds || 8),
    });
    durInput.addEventListener("input", updateScriptTimingHint);
    const narrInput = el("input", { type: "text", className: "scene-narr-input", value: scene.narration || "" });
    const promptInput = el("textarea", { className: "scene-prompt-input", rows: "3" }, [scene.prompt || ""]);

    const removeBtn = el("button", { type: "button", className: "danger sm", text: "Remove" });
    const row = el(
      "div",
      {
        className: "scene-card scene-editor-row",
        dataset: { clipStatus: scene.clipStatus || "missing", clipUrl: scene.clipUrl || "" },
      },
      [
        el("div", { className: "scene-head" }, [
          el("strong", { text: `Scene ${String(index + 1).padStart(2, "0")}` }),
          removeBtn,
        ]),
        el("div", { className: "form-grid" }, [
          el("div", { className: "field" }, [el("label", { text: "Scene Name" }), nameInput]),
          el("div", { className: "field" }, [el("label", { text: "Duration (seconds)" }), durInput]),
        ]),
        el("div", { className: "field" }, [el("label", { text: "Voiceover Beat" }), narrInput]),
        el("div", { className: "field" }, [el("label", { text: "Digen Visual Prompt" }), promptInput]),
      ]
    );
    removeBtn.addEventListener("click", () => {
      if ($$(".scene-editor-row").length <= 1) {
        toast("At least one scene is required.", true);
        return;
      }
      row.remove();
      updateScriptTimingHint();
    });
    return row;
  }

  function renderVideosView() {
    const selector = $("#video-selector");
    const scoped = filterByChannel(state.videos);
    const list = scoped.length ? scoped : state.videos;
    selector.replaceChildren();
    list.forEach((v) => {
      selector.append(el("option", { value: v.slug, text: `${v.title} (${v.slug})` }));
    });

    const active = getActiveVideo();
    if (!active) return;
    state.selectedVideoSlug = active.slug;
    selector.value = active.slug;

    $("#video-status-pill").textContent = `Status: ${active.status || "draft"}`;
    $("#ep-title").value = active.title || "";
    if ($("#ep-channel") && active.channel_id) $("#ep-channel").value = active.channel_id;
    $("#ep-niche").value = active.niche || "";
    $("#ep-aspect").value = active.aspect || "9:16";
    $("#ep-style-bible").value = active.style_bible || "";
    const hooks = active.hooks || [];
    $("#ep-hook-1").value = hooks[0] || "";
    $("#ep-hook-2").value = hooks[1] || "";
    $("#ep-hook-3").value = hooks[2] || "";
    $("#ep-script").value = active.script || "";

    const scenesBox = $("#scenes-editor-list");
    scenesBox.replaceChildren();
    (active.scenes || []).forEach((sc, idx) => scenesBox.append(renderSceneEditorRow(sc, idx)));
    updateScriptTimingHint();

    const seo = active.seo || {};
    $("#ep-seo-title").value = seo.title || active.title || "";
    $("#ep-seo-tags").value = (seo.tags || []).join(", ");
    $("#ep-seo-desc").value = seo.description || "";
    $("#ep-seo-thumb").value = seo.thumbnail_brief || "";
    $("#ep-synthetic").checked = active.contains_synthetic_media !== false;
    $("#ep-kids").checked = Boolean(active.made_for_kids);

    renderDigenCards(active);

    $("#local-ffmpeg-commands").textContent = [
      `# Local Engine Digen + FFmpeg Commands for "${active.slug}" (Zero Workers CPU Usage)`,
      `python3 factory.py pack ${active.slug}`,
      `python3 scripts/digen_request.py ${active.slug} --scene 1                 # Dry-run Scene 1 (0 credits)`,
      `python3 scripts/digen_request.py ${active.slug} --scene 1 --confirm-spend # After Gate 1 approval`,
      `python3 factory.py render ${active.slug}                                  # Local FFmpeg stitch + audio mix`,
    ].join("\n");
  }

  function renderDigenCards(video) {
    const grid = $("#digen-scenes-grid");
    grid.replaceChildren();
    const app = state.approvals[video.slug] || {};

    (video.scenes || []).forEach((scene, idx) => {
      const sceneNum = String(idx + 1).padStart(2, "0");
      const fname = `scene-${sceneNum}.mp4`;
      const isWide = video.aspect === "16:9";
      const gateOpen = idx === 0 ? Boolean(app.digen_scene1_approved) : Boolean(app.digen_remaining_approved);

      const stage = el("div", { className: isWide ? "video-stage wide" : "video-stage" });
      if (scene.clipUrl) {
        stage.append(
          el("video", {
            src: scene.clipUrl,
            controls: true,
            width: isWide ? "480" : "270",
            height: isWide ? "270" : "480",
          })
        );
      } else {
        stage.append(
          el("div", {
            className: "video-placeholder",
            text: `No ${fname} uploaded yet. Preview prompt or attach MP4 from Digen.`,
          })
        );
      }

      const dryRunBtn = el("button", {
        type: "button",
        className: gateOpen ? "sm" : "secondary sm",
        text: gateOpen ? "Prompt & Queue Digen" : "Dry-Run / Credit Gate",
      });
      dryRunBtn.addEventListener("click", () => {
        state.pendingGateSceneIndex = idx;
        $("#credit-gate-summary").textContent =
          idx === 0
            ? `Scene 01 of "${video.title}" (${scene.duration_seconds}s). Approve Scene-01 gate first before Scenes 2..N.`
            : `Scene ${sceneNum} of "${video.title}". Requires Scene-01 verification first.`;
        $("#credit-gate-prompt-preview").textContent = packScenePrompt(video, scene, idx);
        $("#credit-gate-dialog").showModal();
      });

      const fileInput = el("input", { type: "file", accept: "video/mp4" });
      fileInput.addEventListener("change", async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;
        try {
          toast(`Uploading ${fname}...`);
          const resp = await fetch(`/api/media/${video.slug}/${fname}`, {
            method: "PUT",
            headers: { "Content-Type": "video/mp4" },
            body: file,
          });
          if (resp.ok) {
            const out = await resp.json();
            scene.clipStatus = "ready";
            scene.clipUrl = `${out.url}?t=${Date.now()}`;
            toast(`Saved ${fname} (${Math.round(file.size / 1024)} KB) to media storage!`);
          } else {
            scene.clipStatus = "ready-local-preview";
            scene.clipUrl = URL.createObjectURL(file);
            toast(`Previewing ${fname} locally in browser.`);
          }
          renderDigenCards(video);
        } catch {
          scene.clipUrl = URL.createObjectURL(file);
          renderDigenCards(video);
          toast(`Previewing ${fname} in browser.`);
        }
      });

      const uploadLabel = el("label", { className: "file-label" }, [`Attach ${fname}`, fileInput]);

      grid.append(
        el("article", { className: "scene-card" }, [
          el("div", { className: "scene-head" }, [
            el("strong", { text: `Scene ${sceneNum}: ${scene.name}` }),
            el("span", {
              className: scene.clipUrl ? "pill pill-good" : gateOpen ? "pill pill-accent" : "pill",
              text: scene.clipUrl ? "Clip Ready" : gateOpen ? "Gate Approved" : `${scene.duration_seconds}s · Locked`,
            }),
          ]),
          stage,
          el("pre", { tabindex: "0" }, [el("code", { text: packScenePrompt(video, scene, idx) })]),
          el("div", { className: "btn-row" }, [dryRunBtn, uploadLabel]),
        ])
      );
    });
  }

  function renderApprovalsView() {
    const video = getActiveVideo();
    if (!video) return;
    const app = state.approvals[video.slug] || {
      video_slug: video.slug,
      digen_scene1_approved: false,
      digen_remaining_approved: false,
      qa_approved: false,
      qa_checks: [false, false, false, false, false],
      private_upload_approved: false,
      scheduled_publish_window: "Wed/Thu/Fri 22:00–00:00 Asia/Dhaka",
    };

    $("#gate-scene1-cb").checked = Boolean(app.digen_scene1_approved);
    $("#gate-remaining-cb").disabled = !app.digen_scene1_approved;
    $("#gate-remaining-cb").checked = Boolean(app.digen_remaining_approved);
    $("#gate1-badge").textContent = app.digen_remaining_approved
      ? "All Scenes Unlocked"
      : app.digen_scene1_approved
      ? "Scene 1 Approved"
      : "Locked";
    $("#gate1-badge").className = app.digen_scene1_approved ? "pill pill-good" : "pill pill-warn";

    const checks = app.qa_checks || [false, false, false, false, false];
    $$(".qa-check").forEach((cb, i) => {
      cb.checked = Boolean(checks[i]);
    });
    const allQaChecked = $$(".qa-check").every((cb) => cb.checked);
    $("#approve-qa-btn").disabled = !allQaChecked;
    $("#gate2-badge").textContent = app.qa_approved ? "QA Passed ✓" : "Pending QA";
    $("#gate2-badge").className = app.qa_approved ? "pill pill-good" : "pill pill-warn";

    $("#gate-schedule-window").value = app.scheduled_publish_window || "";
    $("#gate-upload-cb").disabled = !app.qa_approved;
    $("#gate-upload-cb").checked = Boolean(app.private_upload_approved);
    $("#gate3-badge").textContent = app.private_upload_approved ? "Approved (Private)" : app.qa_approved ? "Ready to Approve" : "Awaiting QA";
    $("#gate3-badge").className = app.private_upload_approved ? "pill pill-good" : "pill pill-warn";

    const overall = $("#overall-gate-badge");
    if (app.private_upload_approved) {
      overall.textContent = `${video.slug}: Approved for Private Upload`;
      overall.className = "pill pill-good";
    } else if (app.qa_approved) {
      overall.textContent = `${video.slug}: QA Passed`;
      overall.className = "pill pill-accent";
    } else {
      overall.textContent = `${video.slug}: Human Gates Active`;
      overall.className = "pill pill-warn";
    }

    $("#cli-publish-commands").textContent = [
      `# Approved Private Upload Pipeline for "${video.slug}"`,
      `python3 scripts/youtube_upload.py ${video.slug}                          # Dry-run OAuth & compliance check`,
      `python3 scripts/youtube_upload.py ${video.slug} --confirm-private-upload # Uploads strictly as PRIVATE`,
      `# Then in YouTube Studio, schedule Private -> Public for: ${app.scheduled_publish_window || "Top-Tier overlap slot"}`,
    ].join("\n");

    renderSchedulePlanner();
    renderJobsQueue();
  }

  function renderSchedulePlanner() {
    const plan = state.uploadPlan;
    const container = $("#schedule-slots-container");
    if (!plan || !container) return;
    container.replaceChildren();

    (plan.slots || []).forEach((slot, idx) => {
      const captionId = `slot-cap-${idx}`;
      const tbody = el("tbody");
      tbody.append(
        el("tr", {}, [
          el("th", { scope: "row", text: `Creator (${slot.creator_local.timezone})` }),
          el("td", { text: slot.creator_local.private_upload }),
          el("td", { text: slot.creator_local.public_publish }),
        ])
      );
      for (const [market, conv] of Object.entries(slot.markets || {})) {
        tbody.append(
          el("tr", {}, [
            el("th", { scope: "row", text: `${market} (${conv.timezone})` }),
            el("td", { text: conv.private_upload }),
            el("td", { text: conv.public_publish }),
          ])
        );
      }

      const selectSlotBtn = el("button", { type: "button", className: "secondary sm", text: "Use Slot in Gate 3" });
      selectSlotBtn.addEventListener("click", () => {
        const summary = `${slot.best_days.slice(0, 3).join("/")} · Public ${slot.creator_local.public_publish} (Private ${slot.creator_local.private_upload})`;
        $("#gate-schedule-window").value = summary;
        toast("Copied window into Gate 3 Scheduled Release field.");
      });

      container.append(
        el("div", { className: "scene-card", style: "--mb: 12px;" }, [
          el("div", { className: "scene-head" }, [
            el("div", {}, [
              el("strong", { text: `${idx + 1}. ${slot.name}` }),
              el("div", { className: "hint", text: `Best days: ${slot.best_days.join(", ")} · ${slot.rationale}` }),
            ]),
            selectSlotBtn,
          ]),
          el("div", { tabindex: "0", role: "region", "aria-labelledby": captionId, className: "table-wrapper" }, [
            el("table", { style: "--label-2: 'Private Upload Buffer'; --label-3: 'Public Release Window';" }, [
              el("caption", { id: captionId, text: `${slot.name} (${plan.reference_date} DST-aware)` }),
              el("thead", {}, [
                el("tr", {}, [
                  el("th", { scope: "col", text: "Region / Timezone" }),
                  el("th", { scope: "col", text: "Upload PRIVATE (Indexing Buffer)" }),
                  el("th", { scope: "col", text: "Schedule PUBLIC Release" }),
                ]),
              ]),
              tbody,
            ]),
          ]),
        ])
      );
    });
  }

  function renderJobsQueue() {
    const tbody = $("#jobs-table-body");
    if (!tbody) return;
    tbody.replaceChildren();
    state.jobs.forEach((job) => {
      const actionCell = el("td");
      if (job.status !== "completed") {
        const doneBtn = el("button", { type: "button", className: "secondary sm", text: "Mark Done" });
        doneBtn.addEventListener("click", async () => {
          try {
            await apiJson("/api/jobs/complete", {
              method: "POST",
              body: { job_id: job.id, status: "completed", result_summary: "Completed via Hybrid Control Center." },
            });
            await refreshBootstrap(false);
            toast(`Marked job ${job.job_type} completed.`);
          } catch (err) {
            toast(err.message, true);
          }
        });
        actionCell.append(doneBtn);
      } else {
        actionCell.textContent = "✓ Verified";
      }

      const badgeClass =
        job.status === "completed" ? "pill pill-good" : job.status === "awaiting_approval" ? "pill pill-warn" : "pill pill-accent";

      tbody.append(
        el("tr", {}, [
          el("th", { scope: "row", text: job.job_type }),
          el("td", { text: job.video_slug }),
          el("td", { text: job.target_runner }),
          el("td", {}, [el("span", { className: badgeClass, text: job.status })]),
          el("td", { text: job.result_summary || "" }),
          actionCell,
        ])
      );
    });
  }

  function buildRetentionDiagnostic(rec) {
    const stay = Number(rec.viewed_vs_swiped_pct || 0);
    const comp = Number(rec.avg_completion_pct || 0);
    if (stay < 68) return "Test Hook Option 2: raise 0–2s visual contrast to lift Viewed-vs-Swiped-Away %.";
    if (comp < 80) return "Tighten Scene 3 beat: add visual state change at 14–18s to boost completion.";
    return "Strong feed velocity — produce Episode 2 sequel in same series style bible!";
  }

  function renderAnalyticsView() {
    const videoSelect = $("#ana-video-slug");
    if (videoSelect) {
      videoSelect.replaceChildren();
      state.videos.forEach((v) => {
        videoSelect.append(el("option", { value: v.slug, text: `${v.title} (${v.slug})` }));
      });
      if (state.selectedVideoSlug) videoSelect.value = state.selectedVideoSlug;
    }
    if (!$("#ana-published-at").value) {
      $("#ana-published-at").value = new Date().toISOString().slice(0, 10);
    }

    const rows = filterByChannel(state.analytics);
    $("#ana-kpi-count").textContent = `${rows.length} Release${rows.length === 1 ? "" : "s"}`;
    if (rows.length) {
      const avgStay = (rows.reduce((a, r) => a + Number(r.viewed_vs_swiped_pct || 0), 0) / rows.length).toFixed(1);
      const avgComp = (rows.reduce((a, r) => a + Number(r.avg_completion_pct || 0), 0) / rows.length).toFixed(1);
      $("#ana-kpi-stay").textContent = `${avgStay}%`;
      $("#ana-kpi-completion").textContent = `${avgComp}%`;
    } else {
      $("#ana-kpi-stay").textContent = "—";
      $("#ana-kpi-completion").textContent = "—";
    }

    const activeCh = state.channels.find((c) => c.id === state.selectedChannelId) || state.channels[0];
    const override = activeCh && activeCh.studio_heatmap_override;
    $("#ana-kpi-heatmap").textContent = override ? "Active Override" : "Benchmark Mode";
    $("#analytics-heatmap-pill").textContent = override ? `Studio Peak: ${override}` : "Benchmark Mode (Pre-28d Data)";

    const tbody = $("#analytics-table-body");
    tbody.replaceChildren();
    if (!rows.length) {
      tbody.append(
        el("tr", {}, [
          el("th", { scope: "row", text: "No published runs logged yet" }),
          el("td", { text: "—" }),
          el("td", { text: "—" }),
          el("td", { text: "—" }),
          el("td", { text: "US/UK/CA/AU" }),
          el("td", { text: "Publish your private pilot and log 48h YouTube Studio metrics above." }),
        ])
      );
      return;
    }

    rows.forEach((rec) => {
      tbody.append(
        el("tr", {}, [
          el("th", { scope: "row", text: `${rec.video_slug} (${rec.published_at})` }),
          el("td", { text: Number(rec.views_48h || 0).toLocaleString() }),
          el("td", { text: `${rec.viewed_vs_swiped_pct}%` }),
          el("td", { text: `${rec.avg_completion_pct}%` }),
          el("td", { text: rec.top_country }),
          el("td", { text: rec.retention_notes || buildRetentionDiagnostic(rec) }),
        ])
      );
    });
  }

  function renderAll() {
    renderTopbarAndSidebar();
    renderChannelsView();
    renderProviderView();
    renderIdeasView();
    renderVideosView();
    renderApprovalsView();
    renderAnalyticsView();
  }

  async function refreshUploadPlanFromPlanner() {
    const aspect = $("#sched-aspect").value || "9:16";
    const tz = $("#sched-tz").value || "Asia/Dhaka";
    const dateVal = $("#sched-date").value || "";
    const countries = $$(".market-cb")
      .filter((cb) => cb.checked)
      .map((cb) => cb.value);
    if (!countries.length) return;
    const qs = new URLSearchParams({ aspect, tz, countries: countries.join(",") });
    if (dateVal) qs.set("date", dateVal);
    try {
      state.uploadPlan = await apiJson(`/api/upload-plan?${qs.toString()}`);
      renderSchedulePlanner();
      renderTopbarAndSidebar();
    } catch (err) {
      toast(err.message, true);
    }
  }

  function downloadTextFile(filename, content, mime = "text/plain;charset=utf-8") {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function refreshBootstrap(showNotification = false) {
    try {
      const data = await apiJson("/api/bootstrap");
      state.runtime = data.runtime || "hybrid";
      state.storageMode = data.storageMode || "connected";
      state.settings = data.settings;
      state.channels = data.channels || [];
      state.ideas = data.ideas || [];
      state.videos = data.videos || [];
      state.approvals = data.approvals || {};
      state.jobs = data.jobs || [];
      state.analytics = data.analytics || [];
      if (data.vidiqLedger) state.vidiqLedger = data.vidiqLedger;
      if (data.vidiqKeywords) state.vidiqKeywords = data.vidiqKeywords;
      if (data.uploadPlan) {
        state.uploadPlan = data.uploadPlan;
        $("#sched-date").value = data.uploadPlan.reference_date || new Date().toISOString().slice(0, 10);
        $("#sched-tz").value = data.settings.publishing.creator_timezone;
      }
      renderAll();
      if (showNotification) toast("Synced state from Control Center.");
    } catch (err) {
      // Offline fallback to window.YAF_SEED_DATA
      const seed = window.YAF_SEED_DATA || {};
      state.storageMode = "offline_seed_fallback";
      state.videos = seed.episodes || [];
      renderAll();
      toast(`Loaded local seed data (${err.message})`, true);
    }
  }

  function bindEvents() {
    setupDialogFallbacks();

    $$(".nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.dataset.view));
    });
    $$("[data-goto]").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.dataset.goto));
    });

    $("#sidebar-channel-select").addEventListener("change", (e) => {
      state.selectedChannelId = e.target.value;
      renderAll();
    });

    $("#refresh-sync-btn").addEventListener("click", () => refreshBootstrap(true));

    $("#export-bundle-btn").addEventListener("click", () => {
      downloadTextFile(
        `youtube-ai-factory-sync-${new Date().toISOString().slice(0, 10)}.json`,
        JSON.stringify(
          {
            settings: state.settings,
            channels: state.channels,
            ideas: state.ideas,
            videos: state.videos,
            approvals: state.approvals,
            jobs: state.jobs,
            analytics: state.analytics,
          },
          null,
          2
        ),
        "application/json"
      );
      toast("Exported Hybrid Sync JSON bundle.");
    });

    // Modals open
    $("#open-channel-modal-btn").addEventListener("click", () => $("#channel-dialog").showModal());
    $("#open-idea-modal-btn").addEventListener("click", () => $("#idea-dialog").showModal());
    $("#open-new-video-btn").addEventListener("click", () => $("#new-video-dialog").showModal());

    // Create channel submit
    $("#channel-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const created = await apiJson("/api/channels", {
          method: "POST",
          body: {
            name: $("#ch-name").value,
            handle: $("#ch-handle").value,
            niche: $("#ch-niche").value,
            default_aspect: $("#ch-aspect").value,
            creator_timezone: $("#ch-tz").value,
            target_countries: $("#ch-countries").value,
          },
        });
        $("#channel-dialog").close();
        $("#channel-form").reset();
        state.selectedChannelId = created.id;
        await refreshBootstrap(false);
        toast(`Saved channel ${created.name}!`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    // Provider settings
    $$('input[name="provider"]').forEach((r) => r.addEventListener("change", describeProviderSelection));
    $("#settings-fallback").addEventListener("change", describeProviderSelection);

    $("#save-settings-btn").addEventListener("click", async () => {
      const countries = $$(".provider-country-cb")
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);
      if (!countries.length) {
        toast("Select at least one target country.", true);
        return;
      }
      try {
        const provider = document.querySelector('input[name="provider"]:checked')?.value || "auto";
        await apiJson("/api/research-settings", {
          method: "POST",
          body: {
            provider,
            depth: $("#settings-depth").value,
            fallback_to_gemini: $("#settings-fallback").checked,
            target_countries: countries,
            creator_timezone: $("#settings-tz").value,
          },
        });
        await refreshBootstrap(false);
        toast(`Saved Research Provider: ${provider.toUpperCase()} (Digen video locked).`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    $("#preview-plan-btn").addEventListener("click", async () => {
      try {
        const topic = $("#research-topic-input").value || "Find 5 original YouTube niches";
        const resp = await fetch(`/api/research-plan?topic=${encodeURIComponent(topic)}`);
        if (!resp.ok) throw new Error("Failed to build research plan");
        $("#agent-instructions-box").textContent = await resp.text();
        toast("Generated routed Antigravity job brief.");
      } catch (err) {
        toast(err.message, true);
      }
    });

    $("#copy-plan-btn").addEventListener("click", async () => {
      const txt = $("#agent-instructions-box").textContent;
      await navigator.clipboard.writeText(txt).catch(() => {});
      toast("Copied Agent Job Brief to clipboard.");
    });

    $("#copy-master-prompt-btn").addEventListener("click", async () => {
      await navigator.clipboard.writeText($("#master-prompt-box").textContent).catch(() => {});
      toast("Copied Master Prompt to clipboard.");
    });

    $("#queue-research-job-btn").addEventListener("click", async () => {
      try {
        await apiJson("/api/jobs", {
          method: "POST",
          body: {
            channel_id: state.selectedChannelId === "all" ? "ch-hawthorn" : state.selectedChannelId,
            video_slug: state.selectedVideoSlug,
            job_type: "research_niches",
            payload: { topic: $("#research-topic-input").value },
          },
        });
        await refreshBootstrap(false);
        toast("Queued research job for Local Engine!");
      } catch (err) {
        toast(err.message, true);
      }
    });

    // Ideas search & create
    $("#idea-search-input").addEventListener("input", renderIdeasView);
    $("#clear-idea-search-btn").addEventListener("click", () => {
      $("#idea-search-input").value = "";
      renderIdeasView();
    });

    $("#idea-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await apiJson("/api/ideas", {
          method: "POST",
          body: {
            title: $("#idea-title").value,
            channel_id: $("#idea-channel").value,
            score: Number($("#idea-score").value || 85),
            niche: $("#idea-niche").value,
            promise: $("#idea-promise").value,
            hooks: $("#idea-hooks").value,
          },
        });
        $("#idea-dialog").close();
        $("#idea-form").reset();
        await refreshBootstrap(false);
        toast("Added idea to backlog!");
      } catch (err) {
        toast(err.message, true);
      }
    });

    // Videos editor
    $("#video-selector").addEventListener("change", (e) => {
      state.selectedVideoSlug = e.target.value;
      renderVideosView();
      renderApprovalsView();
    });

    $("#ep-script").addEventListener("input", updateScriptTimingHint);

    $("#add-scene-btn").addEventListener("click", () => {
      const idx = $$(".scene-editor-row").length;
      $("#scenes-editor-list").append(
        renderSceneEditorRow(
          {
            name: `Scene ${idx + 1}`,
            duration_seconds: 8,
            narration: "",
            prompt: "Vertical 9:16 stylized 3D shot maintaining exact character and lighting continuity, zero text.",
          },
          idx
        )
      );
      updateScriptTimingHint();
    });

    $("#save-video-btn").addEventListener("click", async () => {
      try {
        const payload = collectVideoFormPayload();
        const saved = await apiJson("/api/videos", { method: "POST", body: payload });
        state.selectedVideoSlug = saved.slug;
        await refreshBootstrap(false);
        toast(`Saved "${saved.title}" & packed ${saved.scenes.length} Digen prompts!`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    $("#download-video-json-btn").addEventListener("click", () => {
      const v = getActiveVideo();
      if (!v) return;
      downloadTextFile(`${v.slug}-episode.json`, JSON.stringify(v, null, 2), "application/json");
    });

    $("#download-all-prompts-btn").addEventListener("click", () => {
      const v = getActiveVideo();
      if (!v) return;
      const allTxt = (v.scenes || []).map((sc, i) => packScenePrompt(v, sc, i)).join("\n\n" + "=".repeat(60) + "\n\n");
      downloadTextFile(`${v.slug}-digen-prompts.txt`, allTxt);
      toast(`Downloaded ${v.scenes.length} packed Digen prompts.`);
    });

    $("#queue-render-job-btn").addEventListener("click", async () => {
      const v = getActiveVideo();
      if (!v) return;
      try {
        await apiJson("/api/jobs", {
          method: "POST",
          body: { channel_id: v.channel_id || "ch-hawthorn", video_slug: v.slug, job_type: "ffmpeg_render_local" },
        });
        await refreshBootstrap(false);
        toast(`Queued local FFmpeg render job for ${v.slug}.`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    $("#new-video-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const title = $("#new-ep-title").value.trim();
        const created = await apiJson("/api/videos", {
          method: "POST",
          body: {
            slug: $("#new-ep-slug").value.trim(),
            title,
            channel_id: $("#new-ep-channel").value,
            niche: $("#new-ep-niche").value.trim(),
            aspect: $("#new-ep-aspect").value,
            hooks: [`Opening visual surprise for ${title}`, "High-stakes countdown hook", "Macro close-up curiosity hook"],
            script: `${title}. Watch closely as the hidden mechanism unfolds in three crisp scenes.`,
            scenes: [
              { name: "Opening Hook (0–8s)", duration_seconds: 8, narration: title, prompt: `Stylized 3D opening macro shot for ${title}, crisp lighting, zero text.` },
              { name: "Escalation / Cutaway (8–16s)", duration_seconds: 8, narration: "Inside, a tiny detail carries the load.", prompt: `Continuing exact visual continuity for ${title}, close-up motion reveal, no text.` },
              { name: "Payoff Resolution (16–24s)", duration_seconds: 8, narration: "And that keeps everything running safely.", prompt: `Pull-back resolution shot for ${title}, coherent proportions, no text.` },
            ],
          },
        });
        $("#new-video-dialog").close();
        $("#new-video-form").reset();
        state.selectedVideoSlug = created.slug;
        await refreshBootstrap(false);
        switchView("videos");
        toast(`Created video episode "${created.slug}"!`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    // Credit gate modal actions
    $("#copy-scene-prompt-btn").addEventListener("click", async () => {
      await navigator.clipboard.writeText($("#credit-gate-prompt-preview").textContent).catch(() => {});
      toast("Copied scene prompt to clipboard.");
    });

    $("#credit-gate-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const v = getActiveVideo();
      if (!v) return;
      try {
        await apiJson("/api/approvals", {
          method: "POST",
          body: { video_slug: v.slug, digen_scene1_approved: true },
        });
        await apiJson("/api/jobs", {
          method: "POST",
          body: {
            channel_id: v.channel_id || "ch-hawthorn",
            video_slug: v.slug,
            job_type: "digen_scene_01",
            payload: { scene: state.pendingGateSceneIndex + 1 },
          },
        });
        $("#credit-gate-dialog").close();
        await refreshBootstrap(false);
        toast(`Approved Scene-01 gate & queued Digen job for ${v.slug}!`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    // Approvals Gates 1, 2, 3
    $("#gate-scene1-cb").addEventListener("change", (e) => {
      $("#gate-remaining-cb").disabled = !e.target.checked;
      if (!e.target.checked) $("#gate-remaining-cb").checked = false;
    });

    $("#save-gate1-btn").addEventListener("click", async () => {
      const v = getActiveVideo();
      if (!v) return;
      try {
        await apiJson("/api/approvals", {
          method: "POST",
          body: {
            video_slug: v.slug,
            digen_scene1_approved: $("#gate-scene1-cb").checked,
            digen_remaining_approved: $("#gate-remaining-cb").checked,
          },
        });
        await refreshBootstrap(false);
        toast("Updated Gate 1 (Digen Credit Spend).");
      } catch (err) {
        toast(err.message, true);
      }
    });

    $$(".qa-check").forEach((cb) => {
      cb.addEventListener("change", () => {
        $("#approve-qa-btn").disabled = !$$(".qa-check").every((x) => x.checked);
      });
    });

    $("#approve-qa-btn").addEventListener("click", async () => {
      const v = getActiveVideo();
      if (!v) return;
      try {
        await apiJson("/api/approvals", {
          method: "POST",
          body: {
            video_slug: v.slug,
            qa_checks: $$(".qa-check").map((c) => c.checked),
            qa_approved: true,
          },
        });
        await refreshBootstrap(false);
        toast(`Gate 2 QA approved for ${v.slug}!`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    $("#save-gate3-btn").addEventListener("click", async () => {
      const v = getActiveVideo();
      if (!v) return;
      try {
        await apiJson("/api/approvals", {
          method: "POST",
          body: {
            video_slug: v.slug,
            private_upload_approved: $("#gate-upload-cb").checked,
            scheduled_publish_window: $("#gate-schedule-window").value.trim(),
          },
        });
        await refreshBootstrap(false);
        toast(`Saved Gate 3 Private Upload & Release Schedule for ${v.slug}!`);
      } catch (err) {
        toast(err.message, true);
      }
    });

    $("#download-seo-pack-btn").addEventListener("click", () => {
      const v = getActiveVideo();
      if (!v) return;
      const app = state.approvals[v.slug] || {};
      const seo = v.seo || {};
      const content = [
        `TITLE: ${seo.title || v.title}`,
        "",
        `DESCRIPTION:\n${seo.description || ""}`,
        "",
        `TAGS: ${(seo.tags || []).join(", ")}`,
        "",
        `THUMBNAIL BRIEF:\n${seo.thumbnail_brief || ""}`,
        "",
        `SYNTHETIC MEDIA DISCLOSURE: ${v.contains_synthetic_media !== false ? "Yes" : "No"}`,
        `MADE FOR KIDS: ${v.made_for_kids ? "Yes" : "No"}`,
        `TARGET RELEASE SLOT: ${app.scheduled_publish_window || "Wed/Thu/Fri 22:00–00:00 Asia/Dhaka"}`,
      ].join("\n");
      downloadTextFile(`${v.slug}-seo-schedule-pack.txt`, content);
    });

    // Upload schedule planner controls
    ["#sched-aspect", "#sched-tz", "#sched-date"].forEach((id) => {
      $(id).addEventListener("change", refreshUploadPlanFromPlanner);
    });
    $$(".market-cb").forEach((cb) => cb.addEventListener("change", refreshUploadPlanFromPlanner));

    $("#copy-schedule-btn").addEventListener("click", async () => {
      if (!state.uploadPlan) return;
      const lines = state.uploadPlan.slots.map(
        (s, i) =>
          `${i + 1}. ${s.name} (${s.best_days.join(", ")}) — Private: ${s.creator_local.private_upload} -> Public: ${s.creator_local.public_publish} (${s.creator_local.timezone})`
      );
      await navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
      toast("Copied Top-Tier Upload Schedule to clipboard.");
    });

    $("#export-ics-btn").addEventListener("click", () => {
      const refDate = ($("#sched-date").value || new Date().toISOString().slice(0, 10)).replace(/-/g, "");
      const v = getActiveVideo();
      const ics = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//YouTube AI Factory//Top-Tier Upload Planner//EN",
        "BEGIN:VEVENT",
        `UID:yaf-${Date.now()}@youtube-ai-factory`,
        `DTSTAMP:${refDate}T120000Z`,
        `DTSTART:${refDate}T140000Z`,
        `DTEND:${refDate}T160000Z`,
        `SUMMARY:Upload PRIVATE (${v ? v.slug : "pilot"}) -> Schedule US/UK/CA/AU Peak`,
        "DESCRIPTION:Upload as PRIVATE 1-2h before 16:00-18:00 UTC (12:00-14:00 US ET / 17:00-19:00 UK / 22:00-00:00 BDT).",
        "END:VEVENT",
        "END:VCALENDAR",
      ].join("\r\n");
      downloadTextFile("youtube-top-tier-upload-slot.ics", ics, "text/calendar;charset=utf-8");
      toast("Downloaded .ics calendar reminder!");
    });

    // Job queue quick enqueue buttons
    $$("[data-enqueue-job]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const v = getActiveVideo();
        try {
          const job = await apiJson("/api/jobs", {
            method: "POST",
            body: {
              channel_id: v ? v.channel_id : "ch-hawthorn",
              video_slug: v ? v.slug : "pilot-01",
              job_type: btn.dataset.enqueueJob,
            },
          });
          await refreshBootstrap(false);
          toast(`Enqueued ${job.job_type} (${job.status}).`);
        } catch (err) {
          toast(err.message, true);
        }
      });
    });

    // Analytics form submit
    $("#analytics-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const slug = $("#ana-video-slug").value;
      const vid = state.videos.find((v) => v.slug === slug);
      try {
        await apiJson("/api/analytics", {
          method: "POST",
          body: {
            channel_id: vid ? vid.channel_id : "ch-hawthorn",
            video_slug: slug,
            published_at: $("#ana-published-at").value,
            views_48h: Number($("#ana-views-48h").value || 0),
            viewed_vs_swiped_pct: Number($("#ana-stay-pct").value || 0),
            avg_completion_pct: Number($("#ana-completion-pct").value || 0),
            top_country: $("#ana-top-country").value,
            publish_slot_used: $("#ana-slot-used").value,
            studio_heatmap_peak: $("#ana-heatmap-peak").value,
            retention_notes: $("#ana-notes").value,
          },
        });
        await refreshBootstrap(false);
        toast(`Saved post-release analytics for ${slug}!`);
      } catch (err) {
        toast(err.message, true);
      }
    });
  }

  bindEvents();
  refreshBootstrap(false);
})();
