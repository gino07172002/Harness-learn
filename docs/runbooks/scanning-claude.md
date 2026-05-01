# Runbook：用 Harness 掃描 d:/claude

這份 runbook 紀錄第一次把 harness 套到外部 real target（`d:/claude`，一個 Web Spine-like Mesh Deformer）的結果，以及對 harness 後續方向的啟示。

## 為什麼留這份

- 證明 zero-mod injection 在不是自己造的 fixture 上也 work
- 把 d:/claude 的 introspection 介面寫下來，下一個 agent 不必重新探勘
- 把「harness 還缺什麼」的 finding 鎖進 repo，避免口頭交接遺失

## 怎麼跑

Profile 已經放在 [examples/targets/claude-ref/harness.profile.json](../../examples/targets/claude-ref/harness.profile.json)。
不放在 d:/claude 內，避免污染外部專案。

```powershell
python harness_doctor.py --profile examples/targets/claude-ref/harness.profile.json
python harness_server.py --profile examples/targets/claude-ref/harness.profile.json
```

Server 起在 port 6180（避開 simple 的 6173）。

要做 headless smoke probe（不需要人類互動），用：

```powershell
python -c "
import asyncio
from playwright.async_api import async_playwright
async def probe():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        await page.goto('http://127.0.0.1:6180/', wait_until='load', timeout=20000)
        await page.wait_for_timeout(2500)
        result = await page.evaluate('''() => ({
            hasHarness: !!window.__ZERO_MOD_HARNESS__,
            debugMethods: window.debug ? Object.keys(window.debug) : [],
            hasState: 'state' in window,
        })''')
        print(result)
        await browser.close()
asyncio.run(probe())
"
```

## 第一次掃描的結果（2026-05-01）

### Harness 端：注入正常

- `window.__ZERO_MOD_HARNESS__` / `window.__HARNESS_BOOTSTRAP__` 都進去了
- 浮動 panel `#__zero_mod_harness_panel` 進 DOM
- `runs/*.jsonl` 留下 `proxy.started` → `html.injected` → `client.served` 的完整 chain

### d:/claude 自帶 `window.debug` 介面（19 個 method）

```text
snapshot, mesh, slots, bones, constraints, animations,
timing, setTimingEnabled, errors, warnings,
actionLog, actionLogText, findSlot, findBone,
recordError, recordWarning, recordAction,
clear, help
```

對 harness 而言這是金礦。目前 client.js 只抓 4 個（`snapshot` / `actionLog` / `errors` / `timing`），其他 9 個結構性 inspector（mesh / slots / bones / constraints / animations / findSlot / findBone / help）沒抓。

### `window.state` 不存在

- `'state' in window` = false
- `appState` / `spineState` / `editorState` / `project` / `app` 都不存在
- d:/claude 把 state 完全封閉在 module / closure 裡，只透過 `window.debug.*` getter 暴露

→ profile 裡的 `stateGlobals` 對 d:/claude 一個都沒命中。

### Console 訊號

- 12 條訊息，0 個 pageerror
- 主要是 WebGL 噪音：`Automatic fallback to software WebGL`、`CONTEXT_LOST_WEBGL`、然後 `context restored`
- 這是 Playwright headless 沒 GPU 造成的環境噪音，**不是 d:/claude bug**
- d:/claude 對 context lost 有 recovery 邏輯且運作正常（`[main-gl] resources rebuilt after context restore`）

## 對 Harness 後續方向的啟示

### 1. `stateGlobals` 在 real target 不夠用

現實是 target 把 state 封在 closure，靠 method 暴露。Harness 需要 **debug-method-driven** 的 snapshot 機制：

profile 應該支援：

```json
{
  "debugMethods": ["snapshot", "mesh", "slots", "bones",
                   "constraints", "animations", "actionLog",
                   "errors", "warnings", "timing"]
}
```

client.js capture 時依列表呼叫 + summarize，與既有 `safeCall` / `summarizeValue` 鏈路接上。
Fixture 端用最小集合 `["snapshot", "actionLog", "errors", "timing"]` 保留現狀。

### 2. Console 比對需要白名單

要把 d:/claude 拉進 golden regression，console 必須能 ignore 已知噪音：

```json
{
  "consoleIgnorePatterns": [
    "Automatic fallback to software WebGL",
    "CONTEXT_LOST_WEBGL",
    "GroupMarkerNotSet"
  ]
}
```

[harness/divergence.py](../../harness/divergence.py) 與 capture 端 console 過濾都要吃這個。

### 3. Capture 一次 `window.debug.help()` 寫進 trace metadata

如果 target 自帶 help method（像 d:/claude 這樣），harness 應該在 capture 開始時呼叫一次並把結果存進 `trace.session.debugHelp`。
未來 agent 看 trace 就知道「這個 target 提供哪些 inspector」，不必再重新探勘。

## 不要做什麼

- 不要把 profile 寫進 `d:/claude` 自己的目錄。Harness 與 target 的 boundary 是設計核心，污染 target 違反 zero-mod 原則
- 不要為了讓 console diff 變綠就修改 d:/claude — 噪音來源是 Playwright 環境，修法在 harness profile，不在 target
- 不要假設 `window.state` 在所有 target 都存在；roadmap E 已經把 stateGlobals 抽成 profile 欄位，但 client.js 還沒消費 — 看 roadmap F

## Harness 抓到的 vs Target 揭露的

掃完 d:/claude 後，把抓到的資訊依「來源」分三層。對未來掃任何 target 都適用。

### 層 1：Harness 自己挖（zero-mod，不依賴 target 配合）

這層對任何 web app 都成立：
- 完整 user event 序列（pointer / click / key / wheel / input / change），含時間戳、座標、selector hint
- Console 全紀錄（log / info / warn / error / debug；`consoleIgnorePatterns` 過濾後）
- Page errors / unhandled promise rejections
- Viewport / URL / userAgent

來源：`harness/static/harness_client.js` document-level capture-phase listener + `console.*` monkey-patch + `window.addEventListener('error'/'unhandledrejection')`。

實作位置：`harness_client.js:160-233` 那一帶。

### 層 2：Target 自願揭露（透過 `window.debug.*`）

這層是 target 主動把資訊放上 window namespace。Harness 透過 `profile.debugMethods` 列表決定要呼叫哪些。
d:/claude 的例子：
- `debug.snapshot()` 高階狀態（bones / slots / activeSlot / animTime / workspace）
- `debug.bones()` / `debug.slots()` / `debug.constraints()` 結構化 detail
- `debug.actionLog()` target 自己的 action history
- `debug.errors()` / `debug.warnings()` target 自己的 error bucket
- `debug.help()` 自描述文件

如果 target 不暴露 `window.debug`，這層整個拿不到。

### 層 3：Harness 主動加值

原料來自層 1 / 2，但呈現是 harness 做的：
- 每個 user event 後**自動**呼叫所有 `debugMethods` 取 snapshot（一次 capture 可能跑數百次）
- 跨 snapshot diff 找出 state transition（bones 0→1→2→3 那種）
- Trace 序列化讓 replay 重放
- Divergence diff 抓 capture vs replay 的首個不同欄位

### Brutal test：如果 target 完全沒 `window.debug`

剩下：完整 events、console、errors、timing、操作路徑可重播
失去：每步之後的 internal state、最終結構（bones / slot / position）

換句話說：**「使用者做了什麼」是 harness 抓的；「做完之後 internal state 變怎樣」是 target 揭露的**。

## False positive 案例：pointerdown 落空被誤讀成 guard 攔截（2026-05-01）

第二次 capture 後（traces/20260501T030806636535Z.json），分析者（這個 agent）從 trace 推論「第一次 import 圖後 Object workspace 切換被 `state.mesh` guard 攔下」，並向 d:/claude 那邊送了一份 brief 要求修 bug。

d:/claude 那邊讀完 source 後 push back，三點都對：

1. **`hasMesh = !!state.mesh`**（d:/claude 的 `debug.js:73`）。trace 顯示 `hasMesh: true` 就直接證明 `state.mesh` 已建立。分析者並排寫了「`hasMesh: true`」跟「state.mesh: null（推斷）」，兩者邏輯上不可能同時成立 — 沒做最基本的自我反證。

2. **「點 Object 沒切換」的關鍵證據是 ev 64 的 pointerdown-without-click**。但 d:/claude 的 workspace tab handler bind 在 `click`，不是 `pointerdown`。pointerup 落在按鈕外就沒 click event、handler 從來沒跑 — 這是 DOM event flow 不是 app 邏輯。把這一筆當「guard 攔截」的證據是把物理層跟邏輯層混在一起。

3. **trace 裡所有真正 click `#workspaceTabObject` 的事件，ws 都成功切到 object**。沒有任何一筆「完整 click + ws 沒切」的紀錄能支撐 bug 假設。

### 教訓

- **跨層敘事要分清**：「使用者覺得點不到」（體感）≠「guard 攔下」（邏輯）≠「click handler 沒跑」（DOM 事件）。Trace 通常只能直接回答最後一層。
- **`hasMesh` 跟 `state.mesh` 是同源訊號** — 不查 target 的 debug 實作就推「兩者不同步」是無中生有。下次推任何「狀態 A 跟狀態 B 不一致」的結論前，先 grep target 的 debug.js 確認兩個欄位的計算來源。
- **pointerdown-without-click 是 harness 端值得標記的訊號**（手滑、cursor 飄走、被 capture 攔截、其他 listener `preventDefault`），但**不該被當成「app 拒絕了使用者意圖」的證據**。Harness 後續可以加一個 derived event：dangling-pointerdown，但分析者要記得它的語意是「物理層意圖偵測」不是「邏輯層拒絕」。
- **沒有完整 click + ws 不變的紀錄之前，不要送 fix brief**。要嘛請使用者重錄一次有完整 click 的 trace，要嘛不開單。

### 對 harness 的後續啟示（待做）

- 在 trace post-processing 加一個 derived event `pointerdown.unmatched`：當 pointerdown 之後 N ms 內同 element 沒對應的 pointerup/click 就標記，提醒分析者「這是物理事故不是邏輯拒絕」
- Report generator 在 timeline 裡用視覺區分「真正 click」與「dangling pointerdown」

## 後續

**Roadmap F 已完成**。`examples/targets/claude-ref/harness.profile.json` 已配置：

- `debugMethods`：10 個（snapshot, mesh, slots, bones, constraints, animations, actionLog, errors, warnings, timing）
- `consoleIgnorePatterns`：7 條 WebGL 噪音正則

第二次掃描（headless capture）證實：
- `__HARNESS_BOOTSTRAP__` 三個 list 全進
- 10 個 method 全部 invoke 成功且 result 寫進 `snapshot.debugMethodResults`
- `trace.session.debugHelp` 抓到 d:/claude 的 inline 文件
- 9 條原始 WebGL 警告全被 filter，`trace.console` length = 0

下一步可選：用這次的 capture 當素材建 `examples/golden/claude-smoke-trace.json` 真實 golden，把 d:/claude 拉進 regression。但要注意 timing/animations 等 volatile 欄位需要 normalize 規則 — `volatileFields` schema 已存在但 divergence 還沒消費，這是真正接 d:/claude 進 regression 前必補的一塊。
