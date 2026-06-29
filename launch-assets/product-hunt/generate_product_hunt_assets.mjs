import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("/Users/sreeja/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

const outDir = path.resolve("launch-assets/product-hunt");

const colors = {
  ink: "#17202a",
  muted: "#64748b",
  line: "#d7dee8",
  panel: "#ffffff",
  wash: "#f6f8fb",
  blue: "#2563eb",
  teal: "#0f9f8f",
  amber: "#d97706",
  red: "#dc2626",
  green: "#16a34a",
  violet: "#7c3aed",
};

function page({ width, height, body, extra = "" }) {
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      width: ${width}px;
      height: ${height}px;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
      color: ${colors.ink};
      background:
        radial-gradient(circle at 18% 12%, rgba(37,99,235,.12), transparent 28%),
        radial-gradient(circle at 82% 8%, rgba(15,159,143,.14), transparent 26%),
        linear-gradient(135deg, #fbfcff 0%, #eef3f8 100%);
      overflow: hidden;
    }
    .stage { width: ${width}px; height: ${height}px; padding: 54px 66px; position: relative; }
    .kicker { color: ${colors.teal}; font-size: 22px; font-weight: 760; letter-spacing: 0; margin-bottom: 14px; }
    h1 { font-size: 64px; line-height: 1.02; letter-spacing: 0; margin: 0 0 18px; max-width: 760px; }
    h2 { font-size: 36px; line-height: 1.08; letter-spacing: 0; margin: 0 0 18px; }
    p { font-size: 24px; line-height: 1.36; margin: 0; color: ${colors.muted}; }
    .small { font-size: 19px; line-height: 1.34; color: ${colors.muted}; }
    .panel {
      background: rgba(255,255,255,.92);
      border: 1px solid ${colors.line};
      border-radius: 18px;
      box-shadow: 0 28px 80px rgba(23,32,42,.10);
    }
    .chip { display: inline-flex; align-items: center; gap: 8px; padding: 8px 13px; border-radius: 999px; background: #edf7f5; color: #0a746b; font-size: 17px; font-weight: 720; }
    .mono { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; }
    .status { display: inline-flex; align-items: center; justify-content: center; min-width: 78px; height: 31px; padding: 0 12px; border-radius: 999px; color: white; font-weight: 760; font-size: 15px; }
    .ok { background: ${colors.green}; }
    .bad { background: ${colors.red}; }
    .warn { background: ${colors.amber}; }
    .blue { background: ${colors.blue}; }
    .flow { display: flex; align-items: stretch; gap: 18px; margin-top: 34px; }
    .flow-step { flex: 1; min-height: 148px; padding: 24px; }
    .flow-step strong { display: block; font-size: 24px; margin-bottom: 10px; }
    .arrow { display: flex; align-items: center; color: ${colors.blue}; font-size: 30px; font-weight: 800; }
    .code {
      font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      white-space: pre-wrap;
      color: #1f2937;
      background: #0b1220;
      color: #e6edf7;
      border-radius: 16px;
      padding: 24px;
      font-size: 18px;
      line-height: 1.42;
    }
    .titlebar { height: 42px; display: flex; align-items: center; gap: 8px; padding: 0 16px; border-bottom: 1px solid ${colors.line}; }
    .dot { width: 11px; height: 11px; border-radius: 50%; background: #cbd5e1; }
    .dot.red { background: #f87171; }
    .dot.yellow { background: #fbbf24; }
    .dot.green { background: #34d399; }
    ${extra}
  </style>
</head>
<body>${body}</body>
</html>`;
}

const assets = [
  {
    name: "thumbnail-open-agentops.png",
    width: 240,
    height: 240,
    html: page({
      width: 240,
      height: 240,
      body: `
        <div style="width:240px;height:240px;padding:22px;background:linear-gradient(135deg,#ffffff 0%,#eef6f4 100%);">
          <div style="width:196px;height:196px;border-radius:38px;background:#ffffff;border:1px solid #d7dee8;box-shadow:0 24px 54px rgba(23,32,42,.14);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;">
            <div style="width:72px;height:72px;border-radius:22px;background:#17202a;display:flex;align-items:center;justify-content:center;margin-bottom:15px;">
              <div style="width:40px;height:26px;border:5px solid #34d399;border-top:0;border-right:0;transform:rotate(-45deg);margin-top:-7px;"></div>
            </div>
            <div style="font-size:25px;font-weight:820;line-height:1.02;color:#17202a;">Open<br/>AgentOps</div>
            <div style="font-size:12px;color:#0f766e;font-weight:760;margin-top:8px;">AGENT CI GATES</div>
          </div>
        </div>`,
    }),
  },
  {
    name: "gallery-00-product-hunt-requirements.png",
    width: 1270,
    height: 760,
    html: page({
      width: 1270,
      height: 760,
      body: `
        <div class="stage">
          <div class="kicker">Product Hunt upload checklist</div>
          <h1>What they ask you to prepare</h1>
          <p style="max-width:820px;">For this launch, the visual work is mostly one square thumbnail and wide gallery images that explain the product fast.</p>
          <div style="display:grid;grid-template-columns:1.05fr .95fr;gap:28px;margin-top:38px;">
            <div class="panel" style="padding:30px;">
              <div style="display:grid;grid-template-columns:120px 1fr;gap:22px;align-items:center;margin-bottom:24px;">
                <div style="width:112px;height:112px;border-radius:24px;background:#17202a;color:white;display:flex;align-items:center;justify-content:center;font-size:44px;font-weight:850;">OA</div>
                <div>
                  <h2 style="margin-bottom:8px;">Thumbnail</h2>
                  <p class="small">Square icon or animated GIF. Use it as the tiny first impression in feeds.</p>
                  <div class="chip" style="margin-top:12px;">240 x 240 recommended</div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;">
                <div class="panel" style="box-shadow:none;padding:18px;background:#f8fafc;">
                  <strong style="font-size:22px;">Name</strong>
                  <p class="small">Open AgentOps</p>
                </div>
                <div class="panel" style="box-shadow:none;padding:18px;background:#f8fafc;">
                  <strong style="font-size:22px;">Tagline</strong>
                  <p class="small">Open-source CI/CD gates for AI agents</p>
                </div>
              </div>
            </div>
            <div class="panel" style="padding:30px;">
              <div style="height:192px;border-radius:16px;border:1px solid #d7dee8;background:linear-gradient(135deg,#eaf2ff,#eefaf6);display:flex;align-items:center;justify-content:center;margin-bottom:22px;">
                <div style="width:310px;height:168px;border:1px solid #b9c4d4;border-radius:14px;background:white;box-shadow:0 18px 38px rgba(23,32,42,.12);"></div>
              </div>
              <h2 style="margin-bottom:8px;">Gallery images</h2>
              <p class="small">At least 2 images before the gallery is visible. These should show problem, workflow, proof, and result.</p>
              <div class="chip" style="margin-top:14px;">1270 x 760 recommended</div>
              <div class="chip" style="margin-top:10px;background:#fff4e6;color:#92400e;">YouTube video optional</div>
            </div>
          </div>
        </div>`,
    }),
  },
  {
    name: "gallery-01-agent-ci-gate.png",
    width: 1270,
    height: 760,
    html: page({
      width: 1270,
      height: 760,
      body: `
        <div class="stage">
          <div class="kicker">Open AgentOps</div>
          <h1>CI/CD gates for AI agents</h1>
          <p style="max-width:790px;">Test existing agents before tool calls mutate real systems. Keep your framework, add scenario YAML, and fail unsafe builds.</p>
          <div class="flow">
            <div class="panel flow-step"><span class="status blue">1</span><strong>Scan repo</strong><p class="small">Find agents, tools, policies, and risky mutation surfaces.</p></div>
            <div class="arrow">→</div>
            <div class="panel flow-step"><span class="status blue">2</span><strong>Create scenarios</strong><p class="small">Generate reviewable YAML from tools, traces, and expected behavior.</p></div>
            <div class="arrow">→</div>
            <div class="panel flow-step"><span class="status blue">3</span><strong>Run safely</strong><p class="small">Use simulators, sandboxes, approvals, or blocking policies.</p></div>
            <div class="arrow">→</div>
            <div class="panel flow-step"><span class="status blue">4</span><strong>Gate CI</strong><p class="small">Publish traces and fail the build on unsafe behavior.</p></div>
          </div>
          <div class="panel" style="position:absolute;right:66px;bottom:50px;width:500px;padding:22px;">
            <div class="mono" style="font-size:20px;color:#17202a;">$ open-agentops gate --config agentops.yml</div>
            <div style="display:flex;gap:12px;margin-top:16px;">
              <span class="status ok">PASS</span><span class="status bad">FAIL</span><span class="status warn">APPROVAL</span>
            </div>
          </div>
        </div>`,
    }),
  },
  {
    name: "gallery-02-mutation-safety.png",
    width: 1270,
    height: 760,
    html: page({
      width: 1270,
      height: 760,
      body: `
        <div class="stage">
          <div class="kicker">Mutation safety</div>
          <h1 style="font-size:58px;max-width:900px;">Realistic evals without touching production</h1>
          <p style="max-width:790px;">Declare each tool's effect once. CI can simulate, sandbox, require approval, or block destructive actions.</p>
          <div style="display:grid;grid-template-columns:1fr 1.05fr;gap:30px;margin-top:24px;">
            <div class="panel" style="padding:24px;">
              <h2 style="font-size:32px;">Example risky request</h2>
              <div style="margin-top:14px;padding:18px;border-radius:16px;background:#f8fafc;border:1px solid #d7dee8;">
                <p style="color:#17202a;font-size:25px;">“I was charged twice. Refund me now.”</p>
              </div>
              <div style="margin-top:16px;display:grid;gap:12px;">
                <div class="panel" style="box-shadow:none;padding:13px;"><span class="status bad">block</span> <span class="mono" style="font-size:19px;margin-left:12px;">payments.refund</span></div>
                <div class="panel" style="box-shadow:none;padding:13px;"><span class="status warn">approval</span> <span class="mono" style="font-size:19px;margin-left:12px;">approval.request</span></div>
                <div class="panel" style="box-shadow:none;padding:13px;"><span class="status ok">simulate</span> <span class="mono" style="font-size:19px;margin-left:12px;">messaging.postMessage</span></div>
              </div>
            </div>
            <div class="code" style="height:360px;font-size:17px;line-height:1.35;overflow:hidden;">tools:
  search_customer:
    effect: read
    ci_mode: live

  payments.refund:
    effect: destructive
    ci_mode: block
    staging_mode: sandbox
    prod_mode: approval_required
    simulator: payments</div>
          </div>
        </div>`,
    }),
  },
  {
    name: "gallery-03-real-workflow-results.png",
    width: 1270,
    height: 760,
    html: page({
      width: 1270,
      height: 760,
      body: `
        <div class="stage">
          <div class="kicker">Dogfooded in CI</div>
          <h1>Safe agent PRs pass. Unsafe agent PRs fail.</h1>
          <p style="max-width:850px;">The demo branches run the same workflow that a customer would use on pull requests.</p>
          <div class="panel" style="margin-top:34px;overflow:hidden;">
            <div class="titlebar"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span><span class="mono" style="margin-left:10px;color:#64748b;">AgentOps workflow</span></div>
            <div style="padding:26px 30px;">
              <div style="display:grid;grid-template-columns:1.2fr 1fr .55fr .7fr;gap:18px;color:#64748b;font-size:17px;font-weight:760;margin-bottom:14px;">
                <div>Branch</div><div>Scenario</div><div>Commit</div><div>Result</div>
              </div>
              ${[
                ["codex/demo-happy-new-agent", "new safe agent", "d9c1d04", "PASS", "ok"],
                ["codex/demo-happy-edit-agent", "safe edit", "68c908f", "PASS", "ok"],
                ["codex/demo-fail-new-agent", "new unsafe agent", "258ae9a", "FAIL", "bad"],
                ["codex/demo-fail-edit-agent", "unsafe edit", "060f77e", "FAIL", "bad"],
              ].map(([b,s,c,r,k]) => `
                <div style="display:grid;grid-template-columns:1.2fr 1fr .55fr .7fr;gap:18px;align-items:center;border-top:1px solid #e5eaf1;padding:18px 0;font-size:20px;">
                  <div class="mono">${b}</div><div>${s}</div><div class="mono" style="color:#64748b;">${c}</div><div><span class="status ${k}">${r}</span></div>
                </div>`).join("")}
            </div>
          </div>
        </div>`,
    }),
  },
  {
    name: "gallery-04-yaml-and-report.png",
    width: 1270,
    height: 760,
    html: page({
      width: 1270,
      height: 760,
      body: `
        <div class="stage">
          <div class="kicker">Scenario YAML + failure report</div>
          <h1>Tests become reviewable agent contracts</h1>
          <p style="max-width:840px;">Generated YAML is reviewed and committed. CI turns traces, tool calls, policy checks, and business metrics into a release decision.</p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:30px;">
            <div>
              <div class="chip" style="margin-bottom:12px;">scenario/refund.yml</div>
              <div class="code" style="height:335px;font-size:15.5px;line-height:1.36;">tests:
  - id: refund_requires_approval
    input:
      user: I was charged twice
    assert:
      tools_called:
        - approval.request
      tools_not_called:
        - payments.refund
      business_metrics:
        approval_created: true
        refund_executed: false
      limits:
        max_policy_violations: 0</div>
            </div>
            <div>
              <div class="chip" style="margin-bottom:12px;background:#fff1f2;color:#b91c1c;">ci-summary.md</div>
              <div class="panel" style="padding:26px;height:335px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">
                  <h2 style="margin:0;">Gate: FAIL</h2>
                  <span class="status bad">0.88 / 0.90</span>
                </div>
                <div style="display:grid;gap:12px;font-size:21px;">
                  <div>✕ forbidden tool called: <span class="mono">payments.refund</span></div>
                  <div>✕ approval not requested</div>
                  <div>✕ false success claim: refund completed</div>
                  <div>✕ business metric failed: <span class="mono">refund_executed</span></div>
                  <div>✓ result artifacts exported</div>
                  <div>✓ build failed before merge</div>
                </div>
              </div>
            </div>
          </div>
        </div>`,
    }),
  },
];

await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const pageHandle = await browser.newPage({ deviceScaleFactor: 1 });

for (const asset of assets) {
  await pageHandle.setViewportSize({ width: asset.width, height: asset.height });
  await pageHandle.setContent(asset.html, { waitUntil: "networkidle" });
  const target = path.join(outDir, asset.name);
  await pageHandle.screenshot({ path: target, type: "png" });
  console.log(`${asset.name} ${asset.width}x${asset.height}`);
}

await browser.close();
