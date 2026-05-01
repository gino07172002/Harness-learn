# Trace Report Template — 給 target 端 agent 看的 bug 報告

這份模板是 harness 端 agent 寫給 target 端 agent（或開發者）看的。
目標：對方能在不重跑 trace 的情況下，**自己驗證每一條主張**。

## 為什麼有這份模板

第一次 d:/claude session 我們踩到一個雷：harness 端 agent 把
「pointerdown-without-click」誤讀成「guard 攔截」，送出去的 brief 被 target 端
agent 推翻。問題不是分析能力，是**報告格式**讓對方無法快速 cross-check：
prose 推論藏在文字裡、trace 證據被摘要過、source 推論跟 trace 證據混在一起。

這份模板把報告拆成五個區塊，每塊有嚴格規則。

## 模板規則

### 1. 報告 metadata（必填）

```
trace path: traces/<filename>.json
profile:    examples/targets/<name>/harness.profile.json
captured:   <ISO timestamp>
analyzer:   harness session <date>
```

### 2. 使用者敘述（原話，不改寫）

逐字記錄使用者描述的現象。如果是「以為」「感覺」，原話保留。
這段不做任何分析。

### 3. Trace 觀察事實（每條附 evidence locator）

每條都必須長這樣：

```
[FACT] <一句話事實>
  evidence: events[<i>] (t=<time>) | snapshots[<j>].<field path>
  raw: <從 trace JSON 直接複製的相關片段>
```

規則：
- **不能有形容詞** —「失敗」「異常」「卡住」全部禁用，改寫成可量測的描述
- **不能跳級** — 「點 X 後 Y 沒切換」不是事實，是兩個事實的合成。拆成「ev[N] click target=X」+「snapshot[N+1].field=value」
- **每條必須能讓對方 `python -c "import json; t=json.load(open('...')); print(t['snapshots'][N])"` 直接驗**

### 4. 推論（明確標 inference 等級）

每條長這樣：

```
[INFER lvl=<1|2|3>] <推論>
  from: [FACT #...]
  assumes: <顯式列出所有假設>
  weakness: <這條推論最可能錯在哪>
```

`lvl` 定義：
- **1 = 直接讀**：一個 fact 換個說法（例：fact「snapshot.hasMesh=true」→ infer「state.mesh 被建立」前提是「hasMesh = !!state.mesh」這個 source 假設明確列在 assumes）
- **2 = 跨欄位 / 跨時間關聯**：兩個以上 fact 的合理因果（例：「ev[N] 是 click + snapshot[N+1] 的 ws 改變」→「click 觸發了切換」）
- **3 = source 行為推測**：對 target codebase 的猜測（例：「rebuildMesh 早退因為 sourceCanvas 沒 ready」）。**lvl 3 必須在 weakness 寫「需要 target agent 驗證」**

規則：
- 不在這區寫 source 程式碼推論之外的東西（不寫修法、不寫 bug 結論）
- assumes 區塊裡寫的 source 假設必須能 grep 到。如果你沒實際 grep 過，標 assumes: <unverified>

### 5. 給 target agent 的問題（不是 fix 提案）

每條長這樣：

```
[Q] <一個是非或具體值的問題>
  why: <這個問題能怎麼幫忙判斷有沒有 bug>
```

規則：
- **不是要修法的問題**（例：「應該用方案 A 還是 B?」 → 禁止）
- **是 source 層具體問題**（例：「函式 X 第 N 行的 guard `!state.mesh` 在 import 完成那一刻會是什麼值？」）
- 每條問題附「為什麼問這個」 — target agent 才知道這條問題的 stake

### 6. 不寫的東西

- ❌ 「Bug 修法選項 A / B / C」 — harness 端不知道 target codebase 的 invariants，不能寫修法
- ❌ 「我推測 root cause 是…」 — 改寫成 [Q] 問句
- ❌ 「這個 bug 嚴重」/「這個 bug 簡單」 — 主觀評斷，target agent 自己判斷

## 流程

1. Capture trace（手動或 headless）
2. 跑 `harness_validate_trace.py` 確認 schema 合法
3. 套這個模板填一份 markdown
4. 寫完後**自己讀一遍**，找出：
   - 是不是有 [FACT] 用了形容詞
   - 是不是有 [INFER] 缺 assumes
   - 是不是不小心寫了「應該怎麼修」
5. **找 trace 內反證證據**：對自己每條 [INFER]，主動翻 trace 找會推翻它的紀錄。如果找到，要嘛降級 INFER，要嘛刪掉
6. 才送出

## 範例

實例參考：`docs/reports/<date>-<short-slug>.md`（每次正式報告產一份）。
