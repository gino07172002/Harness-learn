# Harness Engineering 實作導覽

這份導覽是給你親手跑流程用的。

目標不是只看到測試變綠，而是理解每個 artifact 到底證明了什麼。

先切到 harness 專案目前的實作 worktree：

```powershell
cd D:\harness\.worktrees\self-observing-harness
```

## 人跑，還是 Agent 跑？

Harness engineering 應該同時支援人和 agent。

人通常負責決定：

- 哪些行為重要
- 哪些證據可信
- 一個失敗到底是產品 bug、harness bug，還是環境問題
- 哪些 regression 嚴重到應該擋下改動

Agent 和自動化通常負責跑：

- 可重複的檢查
- capture/replay 流程
- trace validation
- report generation
- golden regression
- CI jobs

重要原則是：人和 agent 應該使用同一套 commands 和 artifacts。

如果 agent 跑得出來，但人不能重現，這個 harness 不夠透明。

如果人能手動跑，但不能自動化，這個 harness 不夠可重複。

## 整體循環

這個專案使用的 harness engineering loop 是：

```text
Doctor
  -> Capture
  -> Validate Trace
  -> Replay
  -> Report
  -> Inspect Run Log
  -> Golden Regression
```

每一站都在回答一個工程問題。

## 1. Doctor

問題：

```text
我現在能信任這台機器來跑 harness 嗎？
```

執行：

```powershell
python harness_doctor.py --target examples/targets/simple --port 6173
```

預期：

```text
HARNESS_DOCTOR
ok: true
```

這證明：

- Python 可用。
- 必要套件可以 import。
- Chromium 可以啟動。
- 指定 port 沒被佔用。
- target 有 `index.html`。
- `traces/`、`reports/`、`runs/` 可以寫入。
- 被注入的 harness client 存在。

Harness engineering 觀念：

在 harness 還沒證明自己的環境健康以前，不要急著相信任何 replay 失敗。

## 2. Capture

問題：

```text
harness 能不能在不修改 target 的情況下觀測它？
```

啟動 proxy server：

```powershell
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

打開：

```text
http://127.0.0.1:6173
```

在頁面中：

1. 按 `Start`。
2. 點 `Increment`。
3. 在 input 裡輸入一小段文字。
4. 點 canvas。
5. 按 `Save`。

預期會產生 artifacts：

```powershell
Get-ChildItem traces
Get-ChildItem runs
```

這證明：

- proxy 能 serving target。
- harness 能注入 `harness_client.js`。
- browser client 能記錄 events 和 snapshots。
- server 能保存 trace。
- server 能寫 run log。

Harness engineering 觀念：

trace 是 target 端發生事情的證據。

run log 是 harness 基礎設施自己做了什麼的證據。

## 3. Validate Trace

問題：

```text
這份 debug artifact 格式正確嗎？
```

選最新的 trace：

```powershell
$trace = Get-ChildItem traces\*.json | Sort-Object LastWriteTime | Select-Object -Last 1
python harness_validate_trace.py $trace.FullName
```

預期：

```text
Trace valid: ...
```

這證明：

- trace 有後續 harness 流程需要的欄位。
- 如果欄位缺失或型別錯誤，會回報精確路徑。

Harness engineering 觀念：

Artifacts 需要 contract。沒有 trace contract，後面的 replay/report 失敗就會變成猜謎。

## 4. Replay

問題：

```text
harness 能不能重現剛剛 capture 到的行為？
```

保持 proxy server 開著，然後在另一個 terminal 執行：

```powershell
$trace = Get-ChildItem traces\*.json | Sort-Object LastWriteTime | Select-Object -Last 1
$runLog = Get-ChildItem runs\*.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
python replay_runner.py $trace.FullName --run-log $runLog.FullName
```

預期：

```json
{
  "ok": true,
  "completedEvents": 13,
  "firstFailure": null
}
```

這證明：

- trace 可以驅動 browser automation。
- replay 結果會寫回 trace。
- replay 完成事件會附加到 run log。

Harness engineering 觀念：

Replay 是把「使用者操作故事」變成「可重現 debug artifact」的地方。

## 5. Report

問題：

```text
人或 AI 能不能不用看錄影，也理解剛剛發生了什麼？
```

執行：

```powershell
$trace = Get-ChildItem traces\*.json | Sort-Object LastWriteTime | Select-Object -Last 1
$runLog = Get-ChildItem runs\*.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
python report_generator.py $trace.FullName --out reports/demo-report.md --run-log $runLog.FullName
```

打開報告：

```powershell
Get-Content reports\demo-report.md
```

這證明：

- trace 可以被摘要。
- report 會包含 event count、operation timeline、errors、replay status、snapshot evidence。
- report generation 事件會附加到 run log。

Harness engineering 觀念：

Report 不是裝飾。它是從原始證據走向 debug 判斷的橋。

## 6. Inspect Run Log

問題：

```text
harness 能不能解釋它自己做了什麼？
```

執行：

```powershell
$runLog = Get-ChildItem runs\*.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content $runLog.FullName
```

尋找這類事件：

```text
proxy.started
html.injected
client.served
trace.received
trace.saved
replay.completed
report.generated
```

這證明：

- harness 不是黑盒子。
- 如果流程失敗，run log 可以幫你縮小是哪個階段失敗。

Harness engineering 觀念：

不能診斷自己的 harness，最後會變成問題的一部分。

## 7. Golden Regression

問題：

```text
和已知正確行為相比，harness 有沒有退化？
```

如果 fixture target 還沒啟動，先啟動：

```powershell
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

在另一個 terminal：

```powershell
python harness_regress.py --golden examples/golden/simple-trace.json
```

預期：

```text
Golden regression passed: examples\golden\simple-trace.json
```

這證明：

- golden trace 仍然有效。
- replay 仍然能跑。
- report generation 仍然產生穩定的預期段落。

Harness engineering 觀念：

Golden traces 是 harness 用來保護自己，避免默默退化的安全網。

## 如何讀失敗

當事情失敗時，先問是哪一層失敗：

```text
Doctor failed      -> 環境或安裝問題
Capture failed     -> proxy、injection、browser client 或 trace save 問題
Validation failed  -> trace schema 問題
Replay failed      -> 重現流程或 target availability 問題
Report failed      -> 摘要/report generation 問題
Run log missing    -> harness 自我觀測問題
Regression failed  -> harness 行為改變了
```

核心習慣是：不要一看到錯誤就立刻修症狀。先定位是哪一層壞掉。

## 哪些該自動化？

學習或調查奇怪失敗時，人應該親手跑完整 walkthrough。

自動化和 CI 應該跑可重複的子集合：

```powershell
python -m pytest -v
node --check harness/static/harness_client.js
python harness_doctor.py --target examples/targets/simple --port 6173
python harness_regress.py --golden examples/golden/simple-trace.json
```

Golden regression 需要 fixture server 正在運行。在 CI 裡，要先背景啟動
`harness_server.py`，再執行 regression command。
