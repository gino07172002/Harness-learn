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
