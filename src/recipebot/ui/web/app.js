// Cooksy web UI. Everything shown comes from the API's engine results.
"use strict";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : esc(n));

const SESSION = (() => {
  try {
    let id = localStorage.getItem("recipe-session");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("recipe-session", id); }
    return id;
  } catch { return Math.random().toString(36).slice(2); }
})();

const DIETS = [
  { key: "vegetarian", label: "Vegetarian", sub: "no meat or fish", emoji: "🥦", bg: "linear-gradient(160deg,#166534,#14532d)" },
  { key: "vegan", label: "Vegan", sub: "no animal products", emoji: "🌱", bg: "linear-gradient(160deg,#15803d,#3f6212)" },
  { key: "dairy", label: "Dairy-free", sub: "no milk, butter, cheese", emoji: "🥛", bg: "linear-gradient(160deg,#1d4ed8,#312e81)" },
  { key: "gluten", label: "Gluten-free", sub: "no wheat, pasta, bread", emoji: "🌾", bg: "linear-gradient(160deg,#a16207,#713f12)" },
  { key: "nuts", label: "Nut-free", sub: "no peanuts or tree nuts", emoji: "🥜", bg: "linear-gradient(160deg,#9a3412,#7c2d12)" },
  { key: "egg", label: "Egg-free", sub: "no eggs or mayonnaise", emoji: "🥚", bg: "linear-gradient(160deg,#a21caf,#701a75)" },
];

const CHAT_EXAMPLES = [
  ["Search", "Find a penne pasta recipe."],
  ["Follow-up restriction", "I cannot have dairy."],
  ["Open a result", "Show me the ingredients for the first one."],
  ["Statistics", "How many recipes contain both garlic and onion? What percentage of the dataset is that?"],
  ["Ranking", "Among recipes containing tomato, which five have the fewest instruction steps?"],
  ["What can I cook?", "I have eggs, onions, tomatoes, and rice. Suggest five recipes with no peanuts and at most six instruction steps."],
  ["Substitution", "Take this banana bread recipe and remove eggs."],
  ["Not in the dataset", "How many calories are in the first one?"],
];

const STAT_PRESETS = [
  ["Garlic + onion: how many, what %?", { operation: "percentage", include_all: ["garlic", "onion"] }],
  ["Tomato recipes with the fewest steps", { operation: "rank_by_steps", include_all: ["tomato"], k: 5, order: "fewest" }],
  ["Most common ingredients (no staples)", { operation: "top_ingredients", k: 10, exclude_staples: true }],
  ["Average ingredients per recipe", { operation: "ingredient_count_stats" }],
  ["Share of vegetarian recipes", { operation: "percentage", exclude: ["vegetarian"] }],
];

let busy = false;
let current = {};  // the session state from the last response

// ---------- API ----------
async function api(path, body) {
  let res;
  try {
    res = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch {
    throw new Error("The server is not reachable. Start it in a terminal with: uv run recipebot web " +
      "(and keep that terminal open), then reload this page.");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(typeof detail.detail === "string" ? detail.detail : `Request failed (${res.status})`);
  }
  return res.json();
}

// ---------- views ----------
function show(view) {
  $$(".view").forEach((v) => v.classList.toggle("hidden", v.id !== `view-${view}`));
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  if (view === "chat") $("#chat-input").focus();
}

// ---------- chat ----------
function addUser(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  $("#messages").append(el);
  scrollChat();
}

function addBot(html) {
  const el = document.createElement("div");
  el.className = "msg bot";
  el.innerHTML = `<div class="avatar">👩‍🍳</div><div class="bot-body">${html}</div>`;
  $("#messages").append(el);
  scrollChat();
  return el;
}

function scrollChat() { const m = $("#messages"); m.scrollTop = m.scrollHeight; }

function setBusy(on) {
  busy = on;
  $$(".send").forEach((b) => (b.disabled = on));
}

async function send(kind, label, payload, target) {
  if (busy) return;
  setBusy(true);
  addUser(label);
  const waiting = addBot(`<div class="bubble"><span class="typing"><i></i><i></i><i></i></span>
    <span class="muted small"> Thinking… (a local model on a CPU can take 5–60 s)</span></div>`);
  try {
    const turn = kind === "chat"
      ? await api("/api/chat", { session_id: SESSION, message: label })
      : await api("/api/action", { session_id: SESSION, label, patch: payload });
    waiting.remove();
    renderTurn(turn, target);
  } catch (err) {
    waiting.remove();
    addBot(`<div class="bubble"><b>Could not get an answer.</b><br>${esc(err.message)}</div>`);
    if (/not reachable/.test(err.message)) setStatus(false, "Server not running");
  } finally {
    setBusy(false);
  }
}

const sendChat = (text) => text.trim() && send("chat", text.trim());
const sendAction = (label, patch, target) => send("action", label, patch, target);

function renderTurn(turn, target) {
  const card = renderData(turn.data, turn);
  const meta = [`${turn.parser === "form" ? "from the form" : `parsed by ${turn.parser}`}`, `${turn.seconds}s`];
  if (turn.corrections.length) meta.push(`guards fixed ${turn.corrections.length}`);
  if (turn.grounding_removed.length) meta.push(`grounding removed ${turn.grounding_removed.length} sentence(s)`);
  const html = `
    ${turn.summary ? `<div class="bubble">${esc(turn.summary)}</div>` : ""}
    ${card || `<div class="bubble">${paragraphs(turn.reply)}</div>`}
    <div class="meta">${esc(meta.join(" · "))}</div>
    <details class="raw"><summary>Show the full text answer</summary><pre>${esc(turn.reply)}</pre></details>`;
  addBot(html);
  if (target && card) $(target).innerHTML = card;
  if (turn.llm_disabled) setStatus(null, `LLM unavailable: ${turn.llm_disabled}`);
  renderState(turn.state);
}

function paragraphs(text) {
  return esc(text).split(/\n{2,}/).map((p) => p.replace(/\n/g, "<br>")).join("<br><br>");
}

// ---------- result cards ----------
function renderData(data, turn) {
  if (!data) return "";
  switch (data.type) {
    case "search": return searchCard(data);
    case "recipe": return recipeCard(data.recipe);
    case "match": return matchCard(data);
    case "stats": return statsCard(data);
    case "substitution": return substitutionCard(data);
    default: return "";
  }
}

const idLink = (id) => `<a class="rid" href="#" data-recipe="${esc(id)}">${esc(id)}</a>`;
const chips = (items, cls = "") => items.map((x) => `<span class="chip ${cls}">${esc(x)}</span>`).join("");

function searchCard(d) {
  if (!d.results.length) {
    return `<div class="rcard"><b>No recipes found for "${esc(d.query)}"</b>
      ${d.notes.map((n) => `<p class="muted small">${esc(n)}</p>`).join("")}</div>`;
  }
  return `<div class="rcard">
      <b>${fmt(d.total)} recipes share a word with "${esc(d.query)}"${d.filters.length > 1 ? " and pass your constraints" : ""}.</b>
      <span class="muted small"> The ${d.results.length} most relevant:</span>
      ${d.notes.map((n) => `<div class="note" style="margin-top:8px">${esc(n)}</div>`).join("")}
    </div>
    ${d.results.map((r, i) => `
      <div class="rcard click" data-recipe="${esc(r.id)}">
        <div class="rtitle"><span class="rank">${i + 1}.</span>${esc(r.title)}</div>
        <div class="rid">${esc(r.id)}</div>
        <div class="facts">${chips([`${r.ingredient_count} ingredients`, `${r.steps} steps`])}${chips(r.matched_terms.map((t) => `matched: ${t}`), "ok")}</div>
        ${r.evidence.map((e) => `<div class="ev">✓ ${esc(e)}</div>`).join("")}
      </div>`).join("")}
    <div class="muted tiny">Click a recipe to open it, or ask for "the first one".</div>`;
}

function recipeCard(r, inModal = false) {
  if (!r) return "";
  const allergens = r.allergens.length || r.allergens_uncertain.length
    ? `${chips(r.allergens.map((a) => `contains ${a}`), "bad")}${chips(r.allergens_uncertain.map((a) => `may contain ${a}`), "need")}`
    : `<span class="chip ok">no allergen words found</span>`;
  return `<div class="rcard recipe" data-id="${esc(r.id)}">
    <div class="recipe-head">
      <h4>${esc(r.title)}</h4>
      <div class="muted small">${esc(r.source)} · ${r.ingredients.length} ingredients · ${r.steps.length} steps</div>
      ${idLink(r.id)}
    </div>
    <div class="tabs">
      <button class="tab on" data-tab="ing">Ingredients</button>
      <button class="tab" data-tab="steps">Steps</button>
      <button class="tab" data-tab="check">Allergen check</button>
    </div>
    <div data-pane="ing"><ul class="lines">${r.ingredients.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    <div data-pane="steps" class="hidden"><ol class="lines">${r.steps.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>
      ${r.steps_method === "sentence" ? `<p class="muted tiny">Stored as one paragraph; steps are its sentences.</p>` : ""}</div>
    <div data-pane="check" class="hidden"><div class="chips">${allergens}</div>
      <p class="muted tiny">Read from the ingredient text with word lists. Not a medical safety guarantee.</p></div>
    <p class="muted tiny">Cooking time, servings and nutrition are not in the dataset.</p>
    <div class="actions">
      <button class="btn small primary" data-adapt="${esc(r.id)}" data-title="${esc(r.title)}">Adapt this recipe</button>
      ${inModal ? `<button class="btn small ghost" data-close>Close</button>` : ""}
    </div>
    <form class="adapt-form hidden form" style="margin-top:10px">
      <label>Ingredient to replace or remove</label>
      <input class="field" name="ingredient" placeholder="e.g. butter, eggs, cream" required>
      <label>Restriction for the substitute</label>
      <select class="field" name="restriction"><option value="">none</option>
        ${DIETS.map((d) => `<option value="${d.key}">${esc(d.label)}</option>`).join("")}</select>
      <button class="btn small primary">Find an evidence-based substitute</button>
    </form>
  </div>`;
}

function matchCard(d) {
  const block = (m, i) => `
    <div class="rcard click" data-recipe="${esc(m.id)}">
      <div class="rtitle"><span class="rank">#${i + 1}</span>${esc(m.title)}</div>
      <div class="rid">${esc(m.id)}</div>
      <div class="muted small">${esc(m.reason)}</div>
      <div class="facts">${chips(m.matched.map((x) => `✓ ${x}`), "ok")}${chips(m.extra_required.map((x) => `+ ${x}`), "need")}${chips(m.unused.map((x) => `unused: ${x}`))}</div>
      ${m.staples_used.length ? `<div class="muted tiny">Staples assumed: ${esc(m.staples_used.join(", "))}</div>` : ""}
      ${m.quantity_notes.map((q) => `<div class="ev">${esc(q)}</div>`).join("")}
      ${m.form_notes.map((q) => `<div class="ev">Form: ${esc(q)}</div>`).join("")}
      ${m.violations.map((v) => `<div class="warn" style="margin-top:6px">Breaks a constraint: ${esc(v)}</div>`).join("")}
    </div>`;
  const head = d.no_match
    ? `<div class="warn"><b>No eligible recipe found.</b> None of the ${fmt(d.candidates)} recipes using your ingredients satisfies every constraint.${d.alternatives.length ? " Closest alternatives below; each one breaks a constraint, as marked." : ""}</div>`
    : `<b>${fmt(d.eligible)} of ${fmt(d.candidates)} recipes using your ingredients pass your constraints.</b>`;
  return `<div class="rcard">
      <div class="muted small">Your ingredients: ${esc(d.pantry.join(", ") || "none")}</div>${head}
      <div class="muted tiny" style="margin-top:6px">Ranking: ${esc(d.ranking_rule)}</div>
      ${d.notes.map((n) => `<div class="muted tiny">${esc(n)}</div>`).join("")}
    </div>
    ${(d.no_match ? d.alternatives : d.results).map(block).join("")}`;
}

function statsCard(d) {
  // A recipe ID is shown under its title rather than in its own (very wide) column.
  const cols = d.rows.length ? Object.keys(d.rows[0]).filter((c) => c !== "recipe_id") : [];
  const cell = (r, c) => c === "title" && r.recipe_id
    ? `${esc(r.title)}<br>${idLink(r.recipe_id)}` : esc(r[c]);
  const table = d.rows.length ? `<table class="t"><tr>${cols.map((c) => `<th>${esc(c.replace("_", " "))}</th>`).join("")}</tr>
    ${d.rows.map((r) => `<tr>${cols.map((c) => `<td>${cell(r, c)}</td>`).join("")}</tr>`).join("")}</table>` : "";
  return `<div class="rcard">
    <div class="answer">${esc(d.answer)}</div>
    <dl class="kv">
      <dt>Filters</dt><dd>${esc(d.filters.join("; ") || "none")}</dd>
      <dt>Recipes analysed</dt><dd>${fmt(d.denominator)}</dd>
      <dt>Method</dt><dd>${esc(d.method)}</dd>
    </dl>
    ${table}
    ${d.sample_ids.length ? `<div class="muted tiny" style="margin-top:8px">Example recipes: ${d.sample_ids.map(idLink).join(", ")}</div>` : ""}
    ${d.notes.map((n) => `<div class="muted tiny" style="margin-top:4px">${esc(n)}</div>`).join("")}
  </div>`;
}

const QTY_LABEL = { supported: "quantity from dataset", estimated: "estimated quantity", unknown: "quantity unknown" };
const QTY_CLASS = { supported: "ok", estimated: "need", unknown: "bad" };
const FIT_CLASS = { good: "ok", partial: "need", unknown: "", poor: "bad" };
const list = (items, tag = "ul") => `<${tag} class="lines">${items.map((x) => `<li>${esc(x)}</li>`).join("")}</${tag}>`;

function candidateBlock(c, i, chosen) {
  const supporting = c.supporting.slice(0, 3).map((s) => `<div class="ev">${s.kind === "direct" ? "direct" : "indirect"}: ${esc(s.title)} ${idLink(s.id)}${s.line ? ` · “${esc(s.line)}”` : ""}</div>`).join("");
  return `<div class="cand">
    <div class="cand-head"><span class="rank">#${i + 1}</span><b>${esc(c.name)}</b>
      <span class="badge ${esc(c.strength)}">${esc(c.strength)} evidence</span>
      <span class="chip small ${FIT_CLASS[c.fit] || ""}">${esc(c.fit)} fit</span>
      <span class="chip small">${c.direct ? "direct" : "indirect"} · ${c.support} recipe${c.support === 1 ? "" : "s"}</span>
      <span class="chip small ${QTY_CLASS[c.quantity.status]}">${esc(QTY_LABEL[c.quantity.status])}${c.quantity.text ? `: ${esc(c.quantity.text)}` : ""}</span>
      ${c.name === chosen ? `<span class="chip small ok">selected</span>` : ""}</div>
    <div class="muted small">Roles: ${esc(c.coverage_text)}</div>
    ${supporting}
    <div class="muted tiny">Limitation: ${esc(c.limitation)}</div>
  </div>`;
}

// Short answer first; everything that backs it up is folded below it.
function substitutionCard(d) {
  const a = d.adapted;
  const s = d.summary;
  const fold = (title, body, open = false) => body ? `
    <details class="sub-section fold" ${open ? "open" : ""}><summary><b>${title}</b></summary>${body}</details>` : "";

  const answer = `
    <div class="status ${esc(s.status)}">${esc(s.headline)}</div>
    <dl class="kv summary">${s.rows.map(([label, text]) => `<dt>${esc(label)}</dt><dd>${esc(text)}</dd>`).join("")}</dl>
    ${a && d.status === "incomplete" ? `<div class="caution" style="margin-top:8px">Incomplete recipe: the ${esc(a.substitute)} amount is not established by the dataset, so test a small batch first.</div>` : ""}`;

  const recipe = a ? `
    <ul class="lines">${a.ingredients.map((x) => `<li class="${x.changed ? "changed" : ""}">${esc(x.text)}</li>`).join("")}</ul>
    <div style="margin-top:8px"><b>Steps</b></div>${list(a.instructions, "ol")}
    <div class="muted small" style="margin-top:6px">Baking: ${esc(d.baking || "not given in the original recipe")} (from the original recipe; not re-tested)</div>
    <details style="margin-top:6px"><summary class="muted small">Original ingredients</summary>${list(d.original_ingredients)}</details>` : "";

  const why = a ? `
    <div class="muted small">Selected by ${esc(d.chosen_by)}. Amount (${esc(a.quantity.status)}): ${esc(a.quantity.basis)}</div>
    <ul class="lines ranking">${[...d.ranking_notes, ...d.uncertainty].map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <div class="muted tiny" style="margin-top:6px">Ranking rules: ${esc(d.ranking_rule)}</div>` : "";

  const evidence = `
    ${d.candidates.map((c, i) => candidateBlock(c, i, a ? a.substitute : null)).join("") || `<p class="muted">No candidates found.</p>`}
    ${d.same_dish_without.length ? `<div class="ev">Versions of this dish without ${esc(d.target)}: ${d.same_dish_without.map((x) => `${esc(x.title)} ${idLink(x.id)}`).join("; ")}</div>` : ""}
    ${d.notes.map((n) => `<div class="ev">Note: "${esc(n.sentence)}" ${idLink(n.id)}</div>`).join("")}
    <div class="muted tiny" style="margin-top:6px">${esc(d.comparison_scope)}. ${esc(d.evidence_types)}</div>`;

  const texture = d.texture.length ? `
    <table class="t"><tr><th>Property</th><th>Possible effect</th></tr>
      ${d.texture.map((t) => `<tr><td>${esc(t.property)}</td><td>${esc(t.prediction)}</td></tr>`).join("")}</table>
    ${d.moisture?.notes.length ? `<div style="margin-top:8px"><b>Moisture check</b> <span class="muted tiny">(risk: ${esc(d.moisture.risk)})</span></div>${list(d.moisture.notes)}` : ""}
    <div class="muted tiny" style="margin-top:6px">Predictions from cooking knowledge, not results recorded in the dataset.</div>`
    : d.expected_effects?.length ? list(d.expected_effects) : "";

  return `<div class="rcard">
    ${d.note ? `<div class="muted small">${esc(d.note)}</div>` : ""}
    ${answer}
    <div class="muted tiny" style="margin-top:6px">${esc(d.recipe.title)} · ${idLink(d.recipe.id)}</div>
    ${fold("Adapted recipe <span class=\"muted tiny\">(✱ changed)</span>", recipe)}
    ${fold("Why this choice", why)}
    ${d.target_lines.length ? fold(`Evidence from the dataset <span class="muted tiny">(${d.candidates.length} candidates)</span>`, evidence) : ""}
    ${fold(a ? "Texture and moisture" : `If you just leave out ${esc(d.target)}`, texture)}
    ${a ? fold("Limitations", list(d.limitations)) : ""}
    ${a ? `<div class="muted tiny" style="margin-top:8px">Not a guarantee that the dish is safe for an allergy.</div>` : ""}
  </div>`;
}

// ---------- recipe modal ----------
async function openRecipe(id) {
  try {
    const r = await api(`/api/recipe/${encodeURI(id)}`);
    $("#modal-card").innerHTML = recipeCard(r, true);
    $("#modal").classList.remove("hidden");
  } catch (err) {
    addBot(`<div class="bubble">${esc(err.message)}</div>`);
  }
}

function closeModal() { $("#modal").classList.add("hidden"); }

// ---------- state, status, overview ----------
// Diets are shown as the diet ("vegetarian"); other restrictions as "no dairy".
const DIET_NAMES = new Set(["vegetarian", "vegan", "pescatarian"]);
const isDiet = (term) => DIET_NAMES.has(term.toLowerCase());
const constraintLabel = (term) => (isDiet(term) ? term : `no ${term}`);

function renderState(s) {
  current = s || {};
  const box = $("#constraints");
  const items = (s.exclude || []).map((x) => `<span class="chip ${isDiet(x) ? "ok" : "bad"}">${esc(constraintLabel(x))}<button title="Remove" data-remove="${esc(x)}"><span class="i i-x"></span></button></span>`);
  if (s.max_steps) items.push(`<span class="chip need">at most ${s.max_steps} steps</span>`);
  box.innerHTML = items.join("") || `<span class="muted">None. Say "I can't have dairy" or pick a diet.</span>`;
  const bits = [];
  if (s.task === "search" && s.query) bits.push(`Active search: "${s.query}"`);
  if (s.task === "match" && s.pantry?.length) bits.push(`Your ingredients: ${s.pantry.join(", ")}`);
  $("#search-state").textContent = bits.join(" · ");
  const excluded = new Set((s.exclude || []).map((x) => x.toLowerCase()));
  $$(".tile").forEach((t) => t.classList.toggle("on", excluded.has(t.dataset.diet)));
}

function setStatus(on, text) {
  $("#llm-status").innerHTML = `<span class="dot ${on ? "on" : ""}"></span><span>${esc(text)}</span>`;
  $("#chat-sub").innerHTML = `<span class="dot ${on ? "on" : ""}"></span>${esc(on ? "Online · " + text.replace(/^LLM: /, "") : text)}`;
}

async function loadStatus() {
  try {
    const s = await api("/api/status");
    setStatus(Boolean(s.llm), s.llm ? `LLM: ${s.llm}` : "Offline parser (no LLM found)");
  } catch { setStatus(false, "Server not reachable"); }
}

async function loadOverview() {
  try {
    const o = await api("/api/overview");
    const max = Math.max(...o.top_ingredients.map((r) => r.recipes));
    $("#glance").innerHTML = `
      <div class="card stat-card"><div class="num">${fmt(o.complete)}</div><div class="lbl">complete recipes (of ${fmt(o.records)} records)</div></div>
      <div class="card stat-card"><div class="num">${Object.keys(o.sources).length} sources</div><div class="lbl">${Object.entries(o.sources).map(([k, v]) => `${esc(k)} ${fmt(v)}`).join(" · ")}</div></div>
      <div class="card stat-card"><div class="num">${o.mean_ingredients}</div><div class="lbl">ingredients per recipe on average (median ${o.median_ingredients}); median ${o.median_steps} steps</div></div>
      <div class="card stat-card"><div class="num">${fmt(o.substitution_pairs)}</div><div class="lbl">"X or Y" ingredient lines used as substitution evidence</div></div>
      <div class="card bars"><b>Most common ingredients</b> <span class="muted small">(share of recipes; salt, pepper and water left out)</span>
        ${o.top_ingredients.map((r) => `<div class="bar-row"><span>${esc(r.ingredient)}</span>
          <div class="bar-track"><div class="bar" style="width:${(100 * r.recipes / max).toFixed(1)}%"></div></div>
          <span class="muted small">${esc(r.share)}</span></div>`).join("")}
      </div>`;
  } catch (err) {
    $("#glance").innerHTML = `<div class="card">Could not load the overview: ${esc(err.message)}</div>`;
  }
}

// ---------- builders ----------
function buildStatic() {
  $("#diet-tiles").innerHTML = DIETS.map((d) => `
    <button class="tile" data-diet="${d.key}" style="background:${d.bg}">
      <span class="emoji">${d.emoji}</span>${esc(d.label)}<small>${esc(d.sub)}</small></button>`).join("");
  $("#cook-diets").innerHTML = DIETS.map((d) => `<span class="chip pick" data-key="${d.key}">${d.emoji} ${esc(d.label)}</span>`).join("");
  $("#chat-examples").innerHTML = CHAT_EXAMPLES.map(([t, q]) => `<button class="example" data-ask="${esc(q)}"><b>${esc(t)}</b><span class="muted">${esc(q)}</span></button>`).join("");
  $("#stat-presets").innerHTML = STAT_PRESETS.map(([label], i) => `<button class="pill" data-preset="${i}">${esc(label)}</button>`).join("");
}

function dietPatch(d) {
  const recipesWord = d.key === "nuts" ? "nut free" : d.key === "egg" ? "eggless" : d.label.toLowerCase();
  return { intent: "search", new_topic: true, query: recipesWord, add_exclude: [d.key] };
}

const splitList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

// ---------- events ----------
function wire() {
  $$(".nav-item").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  $("#expand").addEventListener("click", () => show("chat"));

  $("#hero-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat($("#hero-input").value); $("#hero-input").value = ""; });
  $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat($("#chat-input").value); $("#chat-input").value = ""; });

  $("#reset").addEventListener("click", async () => {
    const r = await api("/api/reset", { session_id: SESSION });
    renderState(r.state);
    $("#messages").innerHTML = "";
    addBot(`<div class="bubble">Started over. All constraints were cleared.</div>`);
    $("#cook-results").innerHTML = ""; $("#stats-results").innerHTML = "";
  });

  // Ingredient tags
  const pantry = [];
  const drawPantry = () => {
    $$("#pantry .chip").forEach((c) => c.remove());
    pantry.forEach((p, i) => $("#pantry-input").insertAdjacentHTML("beforebegin",
      `<span class="chip ok">${esc(p)}<button type="button" data-pantry="${i}"><span class="i i-x"></span></button></span>`));
  };
  $("#pantry-input").addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === ",") && e.target.value.trim()) {
      e.preventDefault();
      splitList(e.target.value).forEach((x) => pantry.includes(x) || pantry.push(x));
      e.target.value = ""; drawPantry();
    }
  });
  $("#pantry").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pantry]");
    if (b) { pantry.splice(Number(b.dataset.pantry), 1); drawPantry(); }
  });

  $("#cook-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const typed = $("#pantry-input").value.trim();
    if (typed) { splitList(typed).forEach((x) => pantry.includes(x) || pantry.push(x)); $("#pantry-input").value = ""; drawPantry(); }
    if (!pantry.length) { $("#pantry-input").focus(); return; }
    const diets = $$("#cook-diets .chip.on").map((c) => c.dataset.key);
    const exclude = [...diets, ...splitList($("#cook-exclude").value)];
    const steps = $("#cook-steps").value;
    const pref = $("#cook-pref").value;
    const limit = Number($("#cook-limit").value);
    const label = `I have ${pantry.join(", ")}.` + (exclude.length ? ` No ${exclude.join(", no ")}.` : "") + (steps ? ` At most ${steps} steps.` : "");
    sendAction(label, {
      intent: "match", pantry: pantry.map((name) => ({ name })), replace_pantry: true,
      add_exclude: exclude, max_steps: steps ? Number(steps) : null,
      preferences: [pref || "most_matched"], limit,
    }, "#cook-results");
  });

  $("#stats-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const op = $("#st-op").value;
    const req = { operation: op, include_all: splitList($("#st-include").value),
      title_contains: splitList($("#st-title").value), exclude: splitList($("#st-exclude").value),
      k: 10, order: "fewest", exclude_staples: op === "top_ingredients" };
    const label = `${$("#st-op").selectedOptions[0].text}` + (req.include_all.length ? ` containing ${req.include_all.join(" and ")}` : "")
      + (req.title_contains.length ? `, title with "${req.title_contains.join(" ")}"` : "") + (req.exclude.length ? `, excluding ${req.exclude.join(", ")}` : "");
    sendAction(label, { intent: "stats", stats: req }, "#stats-results");
  });

  // Delegated clicks: suggestion chips, tiles, recipe links, tabs, adapt, constraint removal
  document.addEventListener("click", (e) => {
    const t = e.target;
    const ask = t.closest("[data-ask]");
    if (ask) { sendChat(ask.dataset.ask); return; }
    const tile = t.closest(".tile");
    if (tile) { const d = DIETS.find((x) => x.key === tile.dataset.diet); sendAction(`Show ${d.label.toLowerCase()} recipes`, dietPatch(d)); return; }
    const preset = t.closest("[data-preset]");
    if (preset) { const [label, req] = STAT_PRESETS[Number(preset.dataset.preset)]; sendAction(label, { intent: "stats", stats: req }, "#stats-results"); return; }
    const pick = t.closest(".chip.pick");
    if (pick) { pick.classList.toggle("on"); return; }
    const remove = t.closest("[data-remove]");
    if (remove) { const term = remove.dataset.remove; sendAction(`${term} is fine now`, { intent: "clarify", remove_exclude: [term], message: `Removed the restriction: ${constraintLabel(term)}. It no longer applies to your searches.` }); return; }
    const tab = t.closest(".tab");
    if (tab) {
      const card = tab.closest(".recipe");
      $$(".tab", card).forEach((x) => x.classList.toggle("on", x === tab));
      $$("[data-pane]", card).forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== tab.dataset.tab));
      return;
    }
    const adapt = t.closest("[data-adapt]");
    if (adapt) { const f = $(".adapt-form", adapt.closest(".recipe")); f.classList.toggle("hidden"); $("input", f).focus(); return; }
    if (t.closest("[data-close]") || t.id === "modal") { closeModal(); return; }
    const rec = t.closest("[data-recipe]");
    if (rec && !t.closest("button")) { e.preventDefault(); openRecipe(rec.dataset.recipe); }
  });

  document.addEventListener("submit", (e) => {
    const f = e.target.closest(".adapt-form");
    if (!f) return;
    e.preventDefault();
    const card = f.closest(".recipe");
    const target = f.elements.ingredient.value.trim();  // not f.target: that is a form property
    const restriction = f.elements.restriction.value;
    const title = $("[data-adapt]", card).dataset.title;
    closeModal();
    sendAction(`Replace the ${target} in "${title}"${restriction ? ` (${constraintLabel(restriction)})` : ""}`, {
      intent: "substitute", recipe_id: card.dataset.id, substitute: { target },
      add_exclude: restriction ? [restriction] : [],
    });
  });

  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
}

buildStatic();
wire();
loadStatus();
loadOverview();
api(`/api/state/${SESSION}`).then(renderState).catch(() => {});
