# Harness — 不改 target 原始碼的瀏覽器 debug harness

[English](README.md) · [使用情境](docs/USE_CASES.md) · [架構圖](docs/architecture.md) · [決策記錄](docs/decisions.md)

Harness 把任意本地 HTML/JavaScript 應用 *從外面* 包起來：你不用動 target
的原始碼，把 Harness 指向 target 的資料夾、用瀏覽器開 proxy URL、隨意操作，
Harness 會把整段 session 錄成可驗證、可重播、可對比、可產出 Markdown 報告
的 trace。

## 你會拿到什麼

- **不需要 instrumentation 的 capture** — Harness 透過一個小 HTTP proxy
  serve target，並在每個 HTML response 注入 recorder script。target 不
  import 任何東西、不需要知道 Harness 存在、自己單獨跑也完全正常。
- **用 Playwright 重播** — 把存好的 trace 餵回去，Harness 用 headless
  Chromium 重現所有事件，並在同樣的 introspection 點再次 snapshot。
- **Divergence diff** — capture 和 replay 的狀態逐欄位比對。volatile 欄位
  （動畫 timer、自動產生的 id、GPU 可用性）透過 per-target policy 過濾，
  確保 report 第一個指出的 divergence 是語意上的差異，不是雜訊。
- **Markdown 報告** — trace 會變成一份可以貼進 PR、issue、或丟給其他
  agent 的自含文件。
- **Golden regression** — 把已知正確的 trace + report 釘住；Harness 每
  次 commit 都重跑，行為漂移時馬上紅。
- **Doctor 自我檢測** — 任何 run 之前先檢查環境（Python、Playwright、
  Chromium、port、target 資料夾、寫權限），*同時* 驗證自己的 diff 引擎還
  能正確壓掉當前 profile 列出的 volatile 欄位。

## 安裝

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

需要 Python 3.10+。Linux / macOS / Windows 都可以。

## Hello-world：用內建 fixture

repo 自帶一個最小 target，你不需要寫任何 config 就可以驗證安裝：

```bash
python harness_regress.py --golden examples/golden/simple-trace.json
```

預期輸出：

```
Golden regression passed: examples/golden/simple-trace.json
```

這個指令會 spawn fixture server、用 Playwright 重播內建 golden trace、
重新生成 report、並與 checked-in 版本比對。如果通過，你的安裝可以
capture、replay、diff、產 report，全部都通。

## Hello-world：錄你自己的 trace

把 Harness 指向任意本地 HTML/JS app。下面用真實案例
[meshWarp2](https://github.com/gino07172002/meshWarp2)（一個瀏覽器版的
2D 骨架動畫編輯器）做示範，但同樣流程適用任何 static web target。

目錄結構 — Harness 和 target 並列：

```
projects/
├── harness/              ← 本專案
└── meshWarp2/            ← target（另外 clone）
    ├── index.html
    ├── app/
    └── ...
```

在 `harness/` 裡面放一份 profile 描述 target：

```bash
mkdir -p examples/targets/meshwarp2
cat > examples/targets/meshwarp2/harness.profile.json <<'JSON'
{
  "name": "meshwarp2",
  "root": "../../../meshWarp2",
  "startupPath": "/",
  "host": "127.0.0.1",
  "port": 6181,
  "stateGlobals": [],
  "debugMethods": [
    "collectSlotBindingDebug",
    "collectAutosaveWeightDebug",
    "collectWeightedAttachmentIssues",
    "dumpGLState"
  ],
  "volatileFields": [
    "debugSnapshot.value.gl",
    "debugMethodResults.dumpGLState.value"
  ],
  "passiveProbes": {
    "domSnapshot": true,
    "domSelectors": [
      "#glCanvas", "#overlay", "#status",
      "#playBtn", "#stopBtn", "#animTime",
      "#fileSaveBtn", "#fileLoadBtn",
      "#undoBtn", "#redoBtn",
      "#boneTree", "#timelineTracks"
    ]
  },
  "environmentCapture": {
    "localStorage": {
      "mode": "allowlist",
      "keys": ["uiLayout:v3"]
    }
  }
}
JSON
```

關於這份 profile，幾個第一次寫真實 target 時都會遇到的誠實註記：

- meshWarp2 沒有把所有 introspection helper 收進 `window.debug`
  namespace。它的 helper 散落在 flat 全域 (`window.collectSlotBindingDebug`、
  `window.dumpGLState` 等)。Profile 處理得了 — `debugMethods` 就是一個
  「在 `window` 上呼叫的函式名稱」清單。你不需要動 target 的程式碼。
- `stateGlobals: []` 是刻意的。meshWarp2 把主要 state 鎖在 module
  scope，沒掛 `window`。Snapshot 的 `stateSummary` 會是空的 — 沒關係。
- Autosave key（`mesh_deformer_autosave_v1`）刻意沒進 `localStorage.keys`。
  它每幀都在變，要嘛把 trace 灌爆，要嘛跟 divergence 引擎吵架。如果你
  *要* capture 它，記得把對應的子樹列進 `volatileFields`。
- WebGL 可用性在你的機器和 Playwright headless replay 之間會不同。上面
  `volatileFields` 那兩條就是叫 diff 引擎整個 `gl` 子樹忽略。

接著 capture：

```bash
python harness_server.py --profile examples/targets/meshwarp2/harness.profile.json
```

用任意瀏覽器開 http://127.0.0.1:6181/，會看到右上角浮著一個小的
「HARNESS」面板。按 **Start**、在 target 裡操作要錄的內容、按 **Stop**、
再按 **Save**。Trace 會落在 `traces/<timestamp>.json`。

接著 replay：

```bash
python replay_runner.py traces/<timestamp>.json
```

產出 report：

```bash
python report_generator.py traces/<timestamp>.json --out reports/my-session.md
```

Report 的 divergence section 會列出第一個 capture 和 replay 不一致的
state 欄位。如果 `volatileFields` 列得對，那個欄位會是語意上的差異
（「骨架樹沒展開」），不是環境差異（「主機有 WebGL 但 headless Chromium
沒有」）。

## 目錄是什麼

```
harness/                 核心模組：proxy、replay、report、doctor、
                         schema validator、divergence、regression
harness/static/          被注入的 recorder (harness_client.js)
examples/targets/        參考 target — 內建 fixture、profile 範本
examples/golden/         self-regression 用的 golden trace 和 report，
                         包含 negative golden 證明 schema validator
                         真的會拒絕格式錯誤的 trace
docs/                    架構、決策記錄、runbooks、specs、
                         使用情境、AI 接手指南
tests/                   每一層 harness 的 pytest 覆蓋
```

## 適用 / 不適用

**適合 Harness 的情境**：target 是可以本地跑或可被 proxy 的靜態 / SPA
HTML/JS app；你至少能讀 source；你想要可重複的 capture/replay/diff over
UI 行為。典型場景：對自己擁有的創作工具做 regression check、給 AI agent
一個能 deterministic 重現的 UI bug 報告、為單頁應用建立 visual / state
regression 的 golden fixture。

**不適合 Harness 的情境**：target 是不能 proxy 的線上正式網站；登入流
程沒辦法 replay；依賴即時多人狀態；或不是 web 技術棧（mobile、native
desktop、embedded）。Native code 請看
[docs/cross-language-portability.md](docs/cross-language-portability.md)。

## 文件路線圖

給人類：
- [使用情境](docs/USE_CASES.md) — 從「我想 regression test 自己的創作工
  具」到「我想給 AI agent 可重現的 bug 報告」的具體場景
- [Walkthrough (中文)](docs/runbooks/harness-engineering-walkthrough.zh-TW.md)
  /
  [(English)](docs/runbooks/harness-engineering-walkthrough.md) — 端到端
  操作流程
- [第一次 capture](docs/runbooks/first-capture.md)
- [架構圖](docs/architecture.md)

給接手的 agent：
- [AI 接手指南 (中文)](docs/AI_HANDOFF.zh-TW.md)
- [Self-observing harness runbook](docs/runbooks/self-observing-harness.md)

給「在評估要不要用」的人：
- [跨語言可移植性](docs/cross-language-portability.md) — 什麼概念可以搬
  到非 web 環境、什麼不行

給想理解設計選擇的人：
- [決策記錄](docs/decisions.md)
- [Specs](docs/superpowers/specs/)

## 狀態

目前可用：zero-mod capture、Playwright replay、divergence diff（帶
comparison-time policy override）、profile-driven inspectors、doctor 帶
actionable hints 和 timing、golden regression（正向和反向）、自含 CI。

尚未支援：較深的 diagnostics（CDP 級別 breakpoint）、event-level
divergence、headed authenticated capture 流程。

## 授權

請看 [LICENSE](LICENSE)（若存在）；否則目前視為個人 / 教育用途。
