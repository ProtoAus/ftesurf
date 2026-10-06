const results = await runs.all([
  {
    key: "scout",
    agent: "scout",
    context: "fresh",
    task: "Read-only setup smoke test. Read .pi/settings.json and CONTRIBUTING.md. Report the native subagent model policy and the warning about git clean. Do not edit, stage, commit, push, build, deploy, or read credentials/private documents. Keep the report under 200 words.",
    output: "setup-smoke/scout.md"
  },
  {
    key: "worker",
    agent: "worker",
    context: "fork",
    acceptance: {
      level: "checked",
      criteria: ["Run the requested read-only Git checks and inspect settings without changing project files"],
      evidence: ["commands-run", "no-staged-files", "residual-risks"]
    },
    task: "Read-only setup smoke test, not an implementation task. Use bash to run git rev-parse --show-toplevel and git diff --check, then read .pi/settings.json. Report cwd, command exit results, and native model policy. If contact_supervisor is available, send one non-blocking progress_update saying the setup smoke commands ran (no secrets). Do not edit, stage, commit, push, build, deploy, or read credentials/private documents. Keep the report under 200 words.",
    output: "setup-smoke/worker.md"
  }
]);
for (const result of results) {
  if (!result.ok) throw new Error("Setup smoke child failed: " + JSON.stringify(result));
}
const review = await runs.run("review", {
  agent: "reviewer",
  context: "fresh",
  task: "Read-only review of Pi setup files only: .pi/settings.json, .pi/README.md, .pi/workflows/subagents-smoke.js, and the Pi allowlist block in .gitignore. Check model inheritance, preservation of user-wide settings, secret/runtime exclusion, and the smoke workflow contract. No edits, staging, commits, builds, deploys, or private/credential reads. Report concrete defects or no findings, under 300 words. Smoke reports follow:\n" + results.map(result => result.output).join("\n"),
  output: "setup-smoke/review.md"
});
if (!review.ok) throw new Error("Setup review failed: " + JSON.stringify(review));
return [...results, review].map(result => ({
  runId: result.runId,
  ok: result.ok,
  output: result.output,
  outputReference: result.outputReference,
  outputPathMapping: result.outputPathMapping,
  artifactPaths: result.artifactPaths
}));
