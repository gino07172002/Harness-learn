# AI Handoff：Harness Engineering 專案接手指南

這份文件給全新的 Claude、Codex 或其他 AI agent 使用。

請不要假設你知道上一段對話。這個專案的設計目標之一，就是讓新模型只靠 repo 內的文件、測試、run logs、golden traces 和命令就能接手。

## 一句話說明

`d:\harness` 是一個學習與實作 Harness Engineering 的專案。

它不是一般 app。它的主體是 **harness 本身**：一套可以從外部包住本地 HTML/JavaScript app、注入觀測器、記錄使用者操作、保存 trace、重播行為、產生 report，並且觀測自己執行狀態的 debug harness。

外部專案，例如 `d:\claude`，只是 reference target / 測試材料，不是本專案的主體。

## 目前已完成

### 1. Zero-Mod Browser Debug Harness

目標：不修改 target 專案檔案，也能觀測它。

已完成能力：

- `harness_server.py`
  - serve local target directory
  - 動態注入 `harness/static/harness_client.js`
  - 接收 trace POST
- `harness/static/harness_client.js`
  - 記錄 pointer / keyboard / input / wheel events
  - 記錄 console / errors
  - 擷取 `window.debug.*` 和 `window.state` 摘要
  - 產生 trace
- `replay_runner.py`
  - 用 Playwright 重播 trace
  - 將 replay result 寫回 trace
- `report_generator.py`
  - 產生 AI / human 可讀 Markdown report

### 2. Self-Observing Harness

目標：不只觀測 target，也觀測 harness 自己。

已完成能力：

- `harness_doctor.py`
  - 檢查 Python、pytest、Playwright、Chromium、port、target、artifact 目錄、client file
- `harness_validate_trace.py`
  - 驗證 trace artifact 的基本 contract
- `runs/*.jsonl`
  - 記錄 harness 自己的 run events
  - 例如 `proxy.started`、`html.injected`、`trace.saved`、`replay.completed`、`report.generated`
- `harness_regress.py`
  - 使用 golden trace 做 regression
- `examples/golden/simple-trace.json`
  - 已知正確的 golden trace fixture
- `examples/golden/simple-report.md`
  - 已知正確的 golden report fixture

## 新 Agent 第一件事

先確認你在 repo root：

```powershell
cd d:\harness
```

然後讀這些文件，順序如下：

```text
docs/AI_HANDOFF.zh-TW.md
docs/superpowers/specs/2026-04-30-zero-mod-debug-harness-design.md
docs/superpowers/specs/2026-04-30-self-observing-harness-design.md
docs/runbooks/harness-engineering-walkthrough.zh-TW.md
docs/runbooks/self-observing-harness.md
```

如果你只能讀一份，先讀本文件。

## 新 Agent 第一批命令

先跑環境與測試，不要急著改 code。

```powershell
python -m pytest -v
node --check harness/static/harness_client.js
python harness_doctor.py --target examples/targets/simple --port 6173
```

預期：

```text
pytest: 30 passed
node --check: no output and exit 0
harness_doctor.py: HARNESS_DOCTOR / ok: true
```

## Golden Regression

Golden regression 需要 fixture server 正在運行。

Terminal 1：

```powershell
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Terminal 2：

```powershell
python harness_regress.py --golden examples/golden/simple-trace.json
```

預期：

```text
Golden regression passed: examples\golden\simple-trace.json
```

## 完整手動 Walkthrough

如果你要像人類學習者一樣完整跑一遍 Harness Engineering 流程，讀：

```text
docs/runbooks/harness-engineering-walkthrough.zh-TW.md
```

那份文件會帶你跑：

```text
Doctor
  -> Capture
  -> Validate Trace
  -> Replay
  -> Report
  -> Inspect Run Log
  -> Golden Regression
```

## 重要檔案地圖

### CLI wrappers

```text
harness_server.py
replay_runner.py
report_generator.py
harness_doctor.py
harness_validate_trace.py
harness_regress.py
```

### Core modules

```text
harness/proxy.py             proxy server, HTML injection, trace endpoint
harness/static/harness_client.js
                             injected browser recorder
harness/trace_store.py       trace persistence
harness/replay.py            Playwright replay
harness/report.py            Markdown report generation
harness/doctor.py            environment checks
harness/trace_validation.py  trace contract validation
harness/run_log.py           JSONL run logging
harness/regression.py        golden trace regression
harness/cli.py               CLI argument parsing and command entry points
```

### Fixtures and artifacts

```text
examples/targets/simple/     small local target used for repeatable tests
examples/golden/             golden trace/report fixtures
traces/                      generated trace artifacts, ignored except .gitkeep
reports/                     generated reports, ignored except .gitkeep
runs/                        generated run logs, ignored except .gitkeep
```

### Tests

```text
tests/test_proxy.py
tests/test_replay.py
tests/test_report.py
tests/test_trace_store.py
tests/test_doctor.py
tests/test_trace_validation.py
tests/test_run_log.py
tests/test_regression.py
tests/test_cli_smoke.py
```

## 這個專案裡的 Harness Engineering 定義

本專案的 harness engineering 不是只有「寫測試」。

它包含：

```text
Boundary        harness 和 target 分離
Doctor          先檢查 harness 能不能信任目前環境
Instrumentation 從外部注入觀測器
Artifacts       保存 traces / reports / runs
Validation      驗證 artifact contract
Replay          重現使用者操作
Diagnostics     report + run log 幫助定位問題
Regression      golden trace 防止 harness 自己退化
Runbooks        人和 agent 都能照同一流程重跑
```

## 如果發生失敗，先分層

不要一看到錯誤就亂改。

先判斷是哪一層失敗：

```text
Doctor failed      -> environment/setup 問題
Capture failed     -> proxy / injection / browser client / trace save 問題
Validation failed  -> trace schema 問題
Replay failed      -> reproduction / target availability 問題
Report failed      -> report generation 問題
Run log missing    -> harness self-observability 問題
Regression failed  -> harness behavior drift 或 golden fixture 問題
```

優先看：

```text
runs/*.jsonl
traces/*.json
reports/*.md
pytest output
harness_doctor.py output
```

## 不要做什麼

請不要：

- 一開始就改 `d:\claude`
- 把 `d:\claude` 當成本專案主體
- 跳過 doctor 直接相信 replay 失敗
- 產生 trace 後不驗證 trace
- 修改 golden fixture 卻不說明原因
- 只讓 agent 能跑，卻讓人不能照 runbook 重現
- 只做口頭說明，不把重要流程寫進 repo

## 接下來合理 Roadmap

下一階段可以從這些方向選：

### A. CI / Automation

讓 GitHub Actions 或本地 CI 自動跑：

```text
pytest
node --check harness_client.js
doctor
golden regression
```

### B. Self-Contained Golden Regression

目前 `harness_regress.py` 需要 fixture server 先手動啟動。

可以改成 regression command 自己：

```text
start fixture server
run regression
stop fixture server
```

### C. Replay Divergence Diff

目前 replay 會回報成功/失敗，但還不夠會說：

```text
第幾步開始 state 不一樣
哪個 snapshot field 改變
console/error 在哪一步出現
```

### D. CDP / GDB-Like Debugging

往最初目標前進：

```text
Chrome DevTools Protocol
pause-on-exception
call stack
local variables
heap snapshot
performance trace
breakpoint control
```

### E. Target Profiles

讓不同 target 有自己的 config：

```text
target name
target root
startup URL
state globals
snapshot functions
ignored volatile fields
```

## 建議新 Agent 的第一個回覆

如果你是新 agent，讀完本文件後，請先回報：

```text
1. 你理解這個專案是什麼
2. 你跑了哪些驗證命令
3. 驗證結果
4. 你認為下一步最合理做什麼
5. 是否有任何文件或 artifact 讓你困惑
```

不要直接開始大改。

## 給使用者的交接提示

你可以在全新的 Claude 環境貼這句：

```text
請在 d:\harness 閱讀 docs/AI_HANDOFF.zh-TW.md，照裡面的流程接手這個 Harness Engineering 專案。先不要改程式，先跑 handoff 文件要求的驗證，然後回報你理解的架構、驗證結果、以及下一步建議。
```
