export const meta = { name: "implement-review", description: "Parallel implement → independent review → bounded repair → test, over independent tickets" };

// Saved pi-herdr workflow. Invoke explicitly, e.g.:
//   herdr_run_workflow { name: "implement-review", args: { tickets: [{ label: "t1", brief: "..." }] } }
// args:
//   tickets: [{ label, brief, spec? }]        required — one entry per independent ticket
//   isolation: "worktree" | "none"           default "none"; "worktree" for heavy parallel edits
//   base: "<git ref>"                        diff base for reviews, default: merge-base with main
//   maxRepairRounds: 1                       bounded repair rounds (default 1)

const tickets = (args && Array.isArray(args.tickets) ? args.tickets : [])
  .filter((t) => t && t.label && t.brief)
  .slice(0, 8);
if (!tickets.length) {
  log("no tickets in args.tickets — nothing to do");
  return { error: "provide args.tickets: [{ label, brief, spec? }]" };
}
const isolation = args && args.isolation === "worktree" ? "worktree" : "none";
const base = (args && args.base) || "";
const maxRounds = (args && args.maxRepairRounds) || 1;
const results = [];

function worktreePath(reportText) {
  // implementers report `WORKTREE: <absolute path>` first when isolated
  const m = typeof reportText === "string" ? reportText.match(/WORKTREE:\s*(\S+)/) : null;
  return m ? m[1] : "";
}

function diffHint(path) {
  if (path) return `The implementation lives in the worktree at ${path}. Use bash with git -C ${path} and read files under ${path}; never rely on this session's cwd.`;
  return `The implementation was made in the current working tree; review the actual diff (base: ${base || "merge-base with main"}).`;
}

function implementPrompt(t) {
  return [
    isolation === "worktree" ? "WORKTREE: report the absolute path of your working directory as the first line of your final message, formatted exactly `WORKTREE: <path>`." : "WORKTREE: none",
    "Task: " + t.brief,
    t.spec ? "Relevant spec/ticket: " + t.spec : "",
    "Implement exactly this task. Respect AGENTS.md. Do not broaden scope. Run the relevant tests. Report changed files, test commands and results, and remaining concerns.",
  ].filter(Boolean).join("\n\n");
}

function reviewPrompt(t, implReport, round) {
  const path = worktreePath(implReport);
  return [
    "Review round " + round + " for ticket " + t.label + ".",
    t.spec ? "Spec/ticket: " + t.spec : "",
    diffHint(path),
    "Inspect the real diff, compare against the task, check for regressions, scope creep, and missing tests. Use bash only for read-only git commands and running tests. Reply PASS or CHANGES REQUIRED with concrete numbered findings.",
  ].filter(Boolean).join("\n\n");
}

function repairPrompt(t, reviewText) {
  return [
    "A reviewer returned CHANGES REQUIRED for your work on ticket " + t.label + ":",
    reviewText,
    "Address exactly these findings. Do not broaden scope. Run the relevant tests. Report what you changed.",
  ].join("\n\n");
}

phase("implement");
const implReports = await parallel(tickets.map((t) => async () => {
  const opts = { label: "impl-" + t.label, agentType: "implementer" };
  if (isolation === "worktree") opts.isolation = "worktree";
  try { return await agent(implementPrompt(t), opts); } catch (e) { log("implement failed: " + t.label); return null; }
}));

phase("review");
let reviews = await parallel(tickets.map((t, i) => async () => {
  if (!implReports[i]) return null;
  try { return await agent(reviewPrompt(t, implReports[i], 1), { label: "rev-" + t.label, agentType: "reviewer" }); }
  catch (e) { log("review failed: " + t.label); return null; }
}));

phase("repair");
for (let round = 1; round <= maxRounds; round++) {
  const needsRepair = tickets
    .map((t, i) => ({ t, i }))
    .filter(({ i }) => implReports[i] && typeof reviews[i] === "string" && reviews[i].includes("CHANGES REQUIRED"));
  if (!needsRepair.length) break;
  log("repair round " + round + ": " + needsRepair.map(({ t }) => t.label).join(", "));
  await parallel(needsRepair.map(({ t, i }) => async () => {
    try { implReports[i] = await agent(repairPrompt(t, reviews[i]), { label: "impl-" + t.label, resume: "impl-" + t.label }); }
    catch (e) { log("repair failed: " + t.label); }
  }));
  const reReviews = await parallel(needsRepair.map(({ t, i }) => async () => {
    try { return await agent(reviewPrompt(t, implReports[i], round + 1), { label: "rev" + (round + 1) + "-" + t.label, agentType: "reviewer" }); }
    catch (e) { log("re-review failed: " + t.label); return reviews[i]; }
  }));
  needsRepair.forEach(({ i }, j) => { reviews[i] = reReviews[j]; });
}

phase("test");
const testReports = await parallel(tickets.map((t, i) => async () => {
  if (!implReports[i]) return null;
  const path = worktreePath(implReports[i]);
  const prompt = [
    "Run the relevant tests, lint/typecheck/build if provided, for ticket " + t.label + ".",
    t.spec ? "Spec/ticket: " + t.spec : "",
    path ? "The code lives in the worktree at " + path + ". cd into it (or use git -C) to run commands; report failures with file and command context." : "Run in the current working tree; report failures with file and command context.",
    "Do not modify files. Report exact commands and results.",
  ].filter(Boolean).join("\n\n");
  try { return await agent(prompt, { label: "test-" + t.label, agentType: "tester" }); }
  catch (e) { log("test failed: " + t.label); return null; }
}));

for (let i = 0; i < tickets.length; i++) {
  const review = reviews[i];
  results.push({
    label: tickets[i].label,
    implemented: Boolean(implReports[i]),
    worktree: worktreePath(implReports[i] || "") || null,
    verdict: !implReports[i] ? "implement-failed" : (typeof review === "string" && review.includes("CHANGES REQUIRED") ? "CHANGES REQUIRED" : (typeof review === "string" && review.includes("PASS") ? "PASS" : "review-unavailable")),
    tests: testReports[i] ? "see test report" : "not run",
  });
}

log("implement-review settled");
return { isolation, results, reviewReports: reviews, testReports, implReports };
