"use strict";

const API_URL = "http://127.0.0.1:8000";
const MAX_TEXT_CHARS = 50000;
const scanButton = document.getElementById("scan");
const statusNode = document.getElementById("status");
const resultNode = document.getElementById("result");
const investigateButton = document.getElementById("investigate");
let scannedPage = null;

// Injected only into the active tab after an explicit user click.
// Reads rendered text from the top frame; never reads form values or HTML.
function extractPageText(limit) {
  const text = (document.body?.innerText || "").trim();
  let structuredEmployer = null;
  const names = new Set();
  function inspectStructured(value, depth = 0) {
    if (!value || typeof value !== "object" || depth > 8) return;
    if (Array.isArray(value)) { value.slice(0, 30).forEach(item => inspectStructured(item, depth + 1)); return; }
    const types = Array.isArray(value["@type"]) ? value["@type"] : [value["@type"]];
    if (types.includes("JobPosting")) {
      const org = value.hiringOrganization;
      const name = typeof org === "string" ? org : org?.name;
      if (typeof name === "string" && name.length <= 100) names.add(name.trim());
    }
    if (value["@graph"]) inspectStructured(value["@graph"], depth + 1);
  }
  for (const script of Array.from(document.querySelectorAll('script[type="application/ld+json"]')).slice(0, 30)) {
    if (script.textContent.length > 100000) continue;
    try { inspectStructured(JSON.parse(script.textContent)); } catch { /* Invalid metadata is ignored. */ }
  }
  if (names.size === 1) structuredEmployer = [...names][0];
  return {
    structuredEmployer,
    text: text.slice(0, limit),
    title: document.title.slice(0, 500),
    url: location.origin + location.pathname, // Exclude query strings and fragments.
    originalLength: text.length,
    truncated: text.length > limit,
  };
}

function renderResult(data, page) {
  const risk = document.getElementById("risk");
  risk.textContent = `${data.risk_level} concern`;
  risk.className = `risk ${data.risk_level}`;
  document.getElementById("score").textContent = `${data.risk_score}/100 rule points`;
  document.getElementById("summary").textContent = data.summary;
  document.getElementById("coverage").textContent = `${data.characters_analyzed.toLocaleString()} characters analyzed${page.truncated ? ` \u00b7 Truncated from ${page.originalLength.toLocaleString()} characters; later content was not scanned` : " \u00b7 Top frame only"}.`;
  const findings = document.getElementById("findings");
  findings.replaceChildren();
  for (const finding of data.findings) {
    const item = document.createElement("article");
    item.className = "finding";
    const title = document.createElement("h3");
    const severity = finding.points >= 30 ? "high" : finding.points >= 20 ? "medium" : "low";
    title.textContent = `${finding.label} (+${finding.points})`;
    const priority = document.createElement("span");
    priority.className = `severity ${severity}`;
    priority.textContent = `Severity: ${severity} (rule priority)`;
    const explanation = document.createElement("p");
    explanation.textContent = finding.explanation;
    const evidence = document.createElement("blockquote");
    evidence.textContent = finding.evidence;
    item.append(title, priority, explanation, evidence);
    findings.append(item);
  }
  document.getElementById("disclaimer").textContent = data.disclaimer;
  const ml = data.ml_prediction;
  document.getElementById("ml-prediction").textContent = ml?.status === "available"
    ? `${ml.label === "fraudulent" ? "Potentially fraudulent" : "Predicted legitimate"} \u00b7 ${(ml.fraud_probability * 100).toFixed(1)}% model output for fraud`
    : "ML prediction unavailable";
  document.getElementById("ml-note").textContent = ml?.note || "Train the model and restart the backend.";
  renderSecurity(data, page);
  document.getElementById("start-intro").hidden = true;
  resultNode.hidden = false;
}

scanButton.addEventListener("click", async () => {
  scanButton.disabled = true;
  investigateButton.disabled = true;
  scannedPage = null;
  document.getElementById("employer-name").value = "";
  document.getElementById("company-website").value = "";
  document.getElementById("employer-preview").textContent = "";
  document.getElementById("investigation-report").hidden = true;
  document.getElementById("investigation-status").textContent = "";
  resultNode.hidden = true;
  statusNode.className = "";
  statusNode.textContent = "Reading visible page text\u2026";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https?:\/\//i.test(tab.url || "")) {
      throw new Error("Open a regular HTTP or HTTPS job posting first. Chrome internal pages, PDFs, and local files cannot be scanned.");
    }
    if (privateInterfaceURL(tab.url)) throw new Error("Open a public job posting. Private mail, messaging, and account pages are excluded.");
    let extracted;
    try {
      [extracted] = await chrome.scripting.executeScript({
        target: { tabId: tab.id }, func: extractPageText, args: [MAX_TEXT_CHARS],
      });
    } catch {
      throw new Error("Chrome blocked access to this page. Try a regular job posting outside the Chrome Web Store or PDF viewer.");
    }
    const page = extracted?.result;
    if (!page?.text) throw new Error("No readable page text found. Wait for the posting to load and try again.");
    statusNode.textContent = "Analyzing with local rules and model\u2026";
    let response;
    try {
      response = await fetch(`${API_URL}/analyze`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: page.text, title: page.title, url: page.url.slice(0, 4096), structured_employer_name: page.structuredEmployer || null }),
        signal: AbortSignal.timeout(15000),
      });
    } catch {
      throw new Error("Cannot reach the local backend. Start FastAPI at http://127.0.0.1:8000 and try again.");
    }
    if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. Check the backend terminal and text limit configuration.`);
    const data = await response.json();
    if (!["low", "medium", "high"].includes(data.risk_level) || !Array.isArray(data.findings)) {
      throw new Error("The backend returned an unexpected response. Check that VeriShield AI is running on port 8000.");
    }
    renderResult(data, page);
    scannedPage = page;
    investigateButton.disabled = false;
    try {
      const preview = await fetch(`${API_URL}/investigate/preview`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(investigationPayload()), signal: AbortSignal.timeout(5000),
      });
      if (preview.ok) {
        const context = await preview.json();
        document.getElementById("employer-preview").textContent = context.employer_name
          ? `Detected employer: ${context.employer_name} (${context.employer_extraction}). Correct the name below if needed.`
          : "Employer not identified. Enter the employer name below.";
      }
    } catch { /* Preview failure must not break the working local scan. */ }
    statusNode.textContent = "Scan complete. Review the evidence below.";
  } catch (error) {
    statusNode.className = "error";
    statusNode.textContent = error.message || "Scan failed. Please try again.";
  } finally {
    scanButton.disabled = false;
  }
});

function safeSourceLink(url, label) {
  const anchor = document.createElement("a");
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) return document.createTextNode(label);
    anchor.href = parsed.href;
  } catch {
    return document.createTextNode(label);
  }
  anchor.textContent = label;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

function renderInvestigation(report) {
  const target = document.getElementById("investigation-report");
  target.replaceChildren();
  function paragraph(text) {
    const node = document.createElement("p");
    node.textContent = text;
    target.append(node);
  }
  function heading(text) {
    const node = document.createElement("h4");
    node.textContent = text;
    target.append(node);
  }
  paragraph(`${report.employer_name || "Employer not identified"} \u00b7 ${report.status.replaceAll("_", " ")}`);
  paragraph(report.message);
  paragraph(`Verification status: ${report.verification_status || "unverified"}`);
  for (const [category, label] of [
    ["confirmed_official", "Official sources (operator-confirmed)"],
    ["independent_employer_related", "Independent employer-related sources"],
    ["unverified_employer_related", "Unverified employer-related sources"],
  ]) {
    heading(label);
    const group = report.sources_retrieved.filter(source => source.source_type === category);
    if (!group.length) paragraph("None established.");
    for (const source of group) {
      const item = document.createElement("p");
      item.append(safeSourceLink(source.url, `${source.id}: ${source.title}`));
      target.append(item);
      if (source.encoding_repaired) paragraph("Known text encoding artifacts repaired for display.");
      paragraph(`${source.identity_reason} \u00b7 Rank ${source.rank_score.toFixed(3)} \u00b7 Entity ${source.entity_match.toFixed(2)} \u00b7 ${source.retrieved_at}`);
    }
  }
  const diagnostics = document.createElement("details");
  const diagnosticsLabel = document.createElement("summary");
  diagnosticsLabel.textContent = `Diagnostics: ${(report.excluded_sources || []).length} excluded sources`;
  diagnostics.append(diagnosticsLabel);
  const queries = document.createElement("p");
  queries.textContent = `Extraction: ${report.employer_extraction}; normalized: ${report.normalized_employer || "unknown"}; queries: ${(report.search_queries || []).join("; ")}`;
  diagnostics.append(queries);
  for (const excluded of report.excluded_sources || []) {
    const item = document.createElement("p");
    item.append(safeSourceLink(excluded.url, excluded.title || excluded.url));
    const reason = document.createElement("span");
    reason.textContent = ` \u00b7 ${excluded.stage}: ${excluded.reason} \u00b7 Entity ${excluded.entity_match.toFixed(2)}`;
    item.append(reason);
    diagnostics.append(item);
  }
  target.append(diagnostics);
  heading("Related supporting passages");
  if (!report.supporting_evidence.length) paragraph("Insufficient employer-specific evidence retrieved.");
  for (const evidence of report.supporting_evidence) {
    const excerpt = document.createElement("blockquote");
    excerpt.textContent = evidence.excerpt;
    target.append(excerpt);
    const citation = document.createElement("p");
    citation.append(safeSourceLink(evidence.url, `${evidence.claim_id} \u00b7 ${evidence.source_id} \u00b7 Similarity ${evidence.cosine_similarity.toFixed(3)}`));
    target.append(citation);
  }
  heading("Unverified claims");
  const claims = document.createElement("ul");
  for (const claim of report.unverified_claims) {
    const item = document.createElement("li");
    item.textContent = `${claim.claim_id}: ${claim.text} \u2014 ${claim.reason}`;
    claims.append(item);
  }
  target.append(claims);
  for (const warning of report.warnings) paragraph(`Note: ${warning}`);
  paragraph(report.limitations);
  if (report.domain_analysis || report.email_analysis || report.advisory) renderSecurity(report, scannedPage);
  target.hidden = false;
}

function investigationPayload() {
  return { text: scannedPage.text, title: scannedPage.title, url: scannedPage.url.slice(0, 4096),
    structured_employer_name: scannedPage.structuredEmployer || null,
    employer_name: document.getElementById("employer-name").value.trim() || null,
    official_website: document.getElementById("company-website").value.trim() || null };
}

investigateButton.addEventListener("click", async () => {
  if (!scannedPage) return;
  const status = document.getElementById("investigation-status");
  investigateButton.disabled = true;
  scanButton.disabled = true;
  document.getElementById("investigation-report").hidden = true;
  status.textContent = "Searching and fetching public sources with TinyFish\u2026 Keep this popup open (up to 90 seconds).";
  try {
    const response = await fetch(`${API_URL}/investigate`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(investigationPayload()),
      signal: AbortSignal.timeout(100000),
    });
    if (!response.ok) throw new Error(`Investigation returned HTTP ${response.status}. Check the employer name and public company URL, or retry if busy.`);
    const report = await response.json();
    renderInvestigation(report);
    status.textContent = `Investigation: ${report.status.replaceAll("_", " ")}.`;
  } catch (error) {
    status.textContent = error.name === "TimeoutError" ? "Investigation timed out. Local scan results are still available." : error.message || "Investigation failed. Check the backend and try again.";
  } finally {
    investigateButton.disabled = false;
    scanButton.disabled = false;
  }
});


function privateInterfaceURL(value) {
  try {
    const url = new URL(value);
    return ["mail.google.com", "outlook.live.com", "outlook.office.com", "outlook.office365.com", "mail.yahoo.com", "mail.proton.me"].includes(url.hostname)
      || /\/(inbox|messaging|messages|account|settings)(\/|$)/i.test(url.pathname);
  } catch { return true; }
}

function addParagraph(target, value, className = "") {
  const node = document.createElement("p");
  node.textContent = value;
  node.className = className;
  target.append(node);
  return node;
}

function addDetails(target, pairs) {
  const list = document.createElement("dl");
  list.className = "details-grid";
  for (const [label, value] of pairs) {
    const term = document.createElement("dt"); term.textContent = label;
    const description = document.createElement("dd"); description.textContent = value || "Not available";
    list.append(term, description);
  }
  target.append(list);
}

function renderSecurityFindings(target, findings) {
  for (const finding of findings || []) {
    const item = document.createElement("div");
    item.className = "finding";
    const badge = document.createElement("span");
    badge.className = `severity ${["info", "low", "medium", "high"].includes(finding.severity) ? finding.severity : "info"}`;
    badge.textContent = `${finding.severity}: ${finding.code.replaceAll("_", " ")}`;
    item.append(badge);
    addParagraph(item, finding.explanation);
    if (finding.compared_domain) addParagraph(item, `${finding.observed_domain || "Unknown"} compared with ${finding.compared_domain}`, "muted");
    target.append(item);
  }
}

function renderDomainAnalysis(domain) {
  const target = document.getElementById("domain-analysis");
  target.replaceChildren();
  if (!domain) { addParagraph(target, "Domain verification unavailable. Restart the updated backend and rescan."); return; }
  addDetails(target, [["Current hostname", domain.hostname], ["Registered domain", domain.registered_domain],
    ["Established employer", (domain.established_employer_domains || []).join(", ") || "Unknown - verification unavailable"],
    ["Establishment basis", domain.establishment_basis]]);
  if (domain.unicode_hostname && domain.unicode_hostname !== domain.hostname) addParagraph(target, `Unicode hostname: ${domain.unicode_hostname}`, "muted");
  addParagraph(target, domain.message);
  if (domain.candidate_domains?.length) addParagraph(target, `Unverified domain candidates: ${domain.candidate_domains.join(", ")}. These are not established ownership.`, "note");
  renderSecurityFindings(target, domain.findings);
  addParagraph(target, domain.limitations, "note");
}

function renderEmailAnalysis(analysis) {
  const target = document.getElementById("email-analysis");
  target.replaceChildren();
  if (!analysis) { addParagraph(target, "Recruitment email analysis unavailable. Restart the updated backend and rescan."); return; }
  addParagraph(target, analysis.message);
  for (const email of analysis.emails || []) {
    const item = document.createElement("article"); item.className = "email-card";
    addParagraph(item, email.address, "email-address");
    addDetails(item, [["Email domain", email.email_domain], ["Registered domain", email.registered_domain],
      ["Employer domains", (email.established_employer_domains || []).join(", ") || "Unknown"], ["Assessment", email.assessment.replaceAll("_", " ")]]);
    addParagraph(item, email.explanation);
    renderSecurityFindings(item, email.findings);
    target.append(item);
  }
  if (analysis.truncated) addParagraph(target, "Only the first 10 relevant email addresses were assessed.", "note");
  addParagraph(target, analysis.scope_note, "note");
}

function renderSecurity(data, page) {
  const info = data.job_information || { job_title: page?.title, employer_name: data.employer_name, current_website: page?.url, analyzed_at: new Date().toISOString() };
  const details = document.getElementById("job-details");
  details.replaceChildren();
  addDetails(details, [["Job / page title", info.job_title], ["Employer", info.employer_name || "Not identified"],
    ["Current website", info.current_website], ["Analysis timestamp", info.analyzed_at ? `${new Date(info.analyzed_at).toLocaleString()} (local)` : "Unavailable"]]);
  const advisory = data.advisory || { category: "Insufficient information", reasons: ["Updated assessment fields are unavailable; rescan with the updated backend."], recommendation: "Review the individual findings and verify the employer independently. No authenticity verdict is available." };
  const categories = { "No major warning indicators detected": "no-major", "Review recommended": "review", "Elevated warning indicators": "elevated", "Insufficient information": "insufficient" };
  const risk = document.getElementById("risk");
  risk.textContent = advisory.category;
  risk.className = `risk ${categories[advisory.category] || "insufficient"}`;
  const reasons = document.getElementById("advisory-reasons"); reasons.replaceChildren();
  for (const reason of advisory.reasons || []) { const item = document.createElement("li"); item.textContent = reason; reasons.append(item); }
  document.getElementById("recommendation").textContent = advisory.recommendation;
  renderDomainAnalysis(data.domain_analysis);
  renderEmailAnalysis(data.email_analysis);
}
