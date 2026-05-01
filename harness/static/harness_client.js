(function () {
  if (window.__ZERO_MOD_HARNESS__) {
    return;
  }

  const bootstrap = window.__HARNESS_BOOTSTRAP__ || { version: 1, targetName: "target" };
  const DEFAULT_DEBUG_METHODS = ["snapshot", "actionLog", "errors", "timing"];
  const debugMethods = Array.isArray(bootstrap.debugMethods) && bootstrap.debugMethods.length
    ? bootstrap.debugMethods.slice()
    : DEFAULT_DEBUG_METHODS.slice();
  const stateGlobals = Array.isArray(bootstrap.stateGlobals) && bootstrap.stateGlobals.length
    ? bootstrap.stateGlobals.slice()
    : ["state"];
  const consoleIgnorePatterns = (Array.isArray(bootstrap.consoleIgnorePatterns) ? bootstrap.consoleIgnorePatterns : [])
    .map((p) => { try { return new RegExp(p); } catch (_) { return null; } })
    .filter((r) => r !== null);
  const volatileFields = Array.isArray(bootstrap.volatileFields) ? bootstrap.volatileFields.slice() : [];
  const passiveProbes = bootstrap.passiveProbes || {};
  const networkLog = [];
  const BUILTIN_WINDOW_KEYS = new Set();

  const trace = {
    version: 1,
    session: {
      id: new Date().toISOString().replace(/[:.]/g, "-"),
      targetName: bootstrap.targetName,
      harnessRunId: bootstrap.harnessRunId || null,
      targetRoot: null,
      proxyUrl: window.location.origin,
      url: window.location.href,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      controller: "user",
      mode: "capture",
      userAgent: navigator.userAgent,
      debugMethods: debugMethods.slice(),
      stateGlobals: stateGlobals.slice(),
      volatileFields: volatileFields.slice(),
      passiveProbes: passiveProbes,
      debugHelp: null
    },
    events: [],
    snapshots: [],
    console: [],
    errors: [],
    screenshots: [],
    replay: null
  };

  let captureActive = false;
  let lastPointerMoveAt = 0;

  function now() {
    return Math.round(performance.now() * 100) / 100;
  }

  function selectorHint(target) {
    if (!target || target === window || target === document) {
      return "";
    }
    if (target.id) {
      return "#" + CSS.escape(target.id);
    }
    if (target.getAttribute && target.getAttribute("data-testid")) {
      return '[data-testid="' + target.getAttribute("data-testid") + '"]';
    }
    return target.tagName ? target.tagName.toLowerCase() : "";
  }

  function targetMeta(target) {
    return {
      tag: target && target.tagName ? target.tagName.toLowerCase() : "",
      id: target && target.id ? target.id : "",
      classes: target && target.classList ? Array.from(target.classList).slice(0, 6) : [],
      selectorHint: selectorHint(target)
    };
  }

  function recordEvent(event, extra) {
    if (!captureActive) {
      return;
    }
    trace.events.push(Object.assign({
      type: event.type,
      time: now(),
      target: targetMeta(event.target)
    }, extra || {}));
    captureSnapshot("after:" + event.type);
    updatePanel();
  }

  function summarizeValue(value) {
    if (value === null) {
      return null;
    }
    const valueType = typeof value;
    if (valueType === "string") {
      return { type: "string", length: value.length, sample: value.slice(0, 80) };
    }
    if (valueType === "number" || valueType === "boolean") {
      return value;
    }
    if (Array.isArray(value)) {
      return { type: "array", length: value.length, sample: value.slice(0, 5) };
    }
    if (valueType === "object") {
      return {
        type: "object",
        constructor: value.constructor ? value.constructor.name : "Object",
        keys: Object.keys(value).slice(0, 30)
      };
    }
    return { type: valueType };
  }

  function safeCall(fn) {
    try {
      return { ok: true, value: fn() };
    } catch (error) {
      return { ok: false, error: String(error && error.message ? error.message : error) };
    }
  }

  function probeDomElement(selector) {
    const el = document.querySelector(selector);
    if (!el) return { selector, found: false };
    const rect = el.getBoundingClientRect();
    return {
      selector,
      found: true,
      tag: el.tagName.toLowerCase(),
      visible: rect.width > 0 && rect.height > 0,
      text: (el.textContent || "").slice(0, 120),
      value: "value" in el ? String(el.value).slice(0, 120) : null,
      checked: "checked" in el ? Boolean(el.checked) : null,
      disabled: "disabled" in el ? Boolean(el.disabled) : null,
      classes: Array.from(el.classList || []).slice(0, 8),
      attributes: ["aria-expanded", "aria-selected", "aria-pressed", "data-state", "data-active"]
        .reduce((acc, key) => { const v = el.getAttribute && el.getAttribute(key); if (v !== null && v !== undefined) acc[key] = v; return acc; }, {})
    };
  }

  function probeDom() {
    const out = {
      title: document.title,
      activeElement: selectorHint(document.activeElement),
      bodyChildCount: document.body ? document.body.children.length : 0,
      formFields: []
    };
    const fields = document.querySelectorAll("input, textarea, select");
    for (let i = 0; i < fields.length && i < 50; i++) {
      const f = fields[i];
      out.formFields.push({
        selector: selectorHint(f),
        type: f.type || f.tagName.toLowerCase(),
        value: String(f.value || "").slice(0, 80),
        checked: "checked" in f ? Boolean(f.checked) : null
      });
    }
    if (Array.isArray(passiveProbes.domSelectors)) {
      out.elements = passiveProbes.domSelectors.map(probeDomElement);
    }
    return out;
  }

  function probeStorage() {
    function summarizeStorage(s) {
      const keys = [];
      for (let i = 0; i < s.length && i < 100; i++) {
        const k = s.key(i);
        const v = s.getItem(k) || "";
        keys.push({ key: k, valueLength: v.length, sample: v.slice(0, 60) });
      }
      return { count: s.length, keys };
    }
    return {
      localStorage: summarizeStorage(window.localStorage),
      sessionStorage: summarizeStorage(window.sessionStorage),
      cookieCount: (document.cookie || "").split(";").filter((s) => s.trim()).length
    };
  }

  function probeWindowGlobals() {
    const own = Object.keys(window).filter((k) => !BUILTIN_WINDOW_KEYS.has(k) && !k.startsWith("__"));
    return own.slice(0, 80).map((k) => {
      const v = window[k];
      const t = typeof v;
      const entry = { name: k, type: t };
      if (v && t === "object") {
        entry.constructor = v.constructor ? v.constructor.name : "Object";
        try { entry.keys = Object.keys(v).slice(0, 20); } catch (_) { entry.keys = null; }
      } else if (t === "function") {
        entry.length = v.length;
      } else if (t === "string") {
        entry.length = v.length;
      } else if (t === "number" || t === "boolean") {
        entry.value = v;
      }
      return entry;
    });
  }

  function runPassiveProbes() {
    const out = {};
    if (passiveProbes.domSnapshot) out.dom = safeCall(probeDom);
    if (passiveProbes.storage) out.storage = safeCall(probeStorage);
    if (passiveProbes.windowGlobalsScan) out.windowGlobals = safeCall(probeWindowGlobals);
    if (passiveProbes.network) {
      out.networkRecent = networkLog.slice(-20);
    }
    return out;
  }

  function captureSnapshot(reason) {
    if (!captureActive) {
      return;
    }
    const snapshot = {
      time: now(),
      reason,
      url: window.location.href,
      debugSnapshot: null,
      debugActionLog: null,
      debugErrors: null,
      debugTiming: null,
      debugMethodResults: {},
      stateSummary: null,
      stateSummaries: {},
      passive: runPassiveProbes()
    };

    debugMethods.forEach((methodName) => {
      if (window.debug && typeof window.debug[methodName] === "function") {
        const result = safeCall(() => window.debug[methodName]());
        snapshot.debugMethodResults[methodName] = result;
        if (methodName === "snapshot") snapshot.debugSnapshot = result;
        else if (methodName === "actionLog") snapshot.debugActionLog = result;
        else if (methodName === "errors") snapshot.debugErrors = result;
        else if (methodName === "timing") snapshot.debugTiming = result;
      }
    });

    stateGlobals.forEach((globalName) => {
      if (globalName in window) {
        const summary = safeCall(() => summarizeValue(window[globalName]));
        snapshot.stateSummaries[globalName] = summary;
        if (globalName === "state") snapshot.stateSummary = summary;
      }
    });

    trace.snapshots.push(snapshot);
  }

  function captureDebugHelp() {
    if (window.debug && typeof window.debug.help === "function") {
      trace.session.debugHelp = safeCall(() => window.debug.help());
    }
  }

  function startCapture() {
    captureActive = true;
    captureDebugHelp();
    captureSnapshot("capture:start");
    updatePanel();
  }

  function stopCapture() {
    captureSnapshot("capture:stop");
    captureActive = false;
    updatePanel();
  }

  async function saveTrace() {
    captureSnapshot("capture:save");
    const response = await fetch("/__harness__/trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(trace)
    });
    const result = await response.json();
    panelStatus.textContent = result.ok ? "saved " + result.path : "save failed";
  }

  function consoleArgsIgnored(args) {
    if (consoleIgnorePatterns.length === 0) return false;
    for (let i = 0; i < args.length; i++) {
      const value = args[i];
      const text = typeof value === "string" ? value : (value && value.message ? String(value.message) : "");
      if (!text) continue;
      for (let j = 0; j < consoleIgnorePatterns.length; j++) {
        if (consoleIgnorePatterns[j].test(text)) return true;
      }
    }
    return false;
  }

  if (passiveProbes.network) {
    const originalFetch = window.fetch ? window.fetch.bind(window) : null;
    if (originalFetch) {
      window.fetch = function () {
        const startedAt = now();
        const args = arguments;
        const req = args[0];
        const method = (args[1] && args[1].method) || (req && req.method) || "GET";
        const url = typeof req === "string" ? req : (req && req.url) || "";
        return originalFetch.apply(window, args).then(
          (response) => {
            networkLog.push({ time: startedAt, kind: "fetch", method, url: String(url).slice(0, 200), status: response.status, durationMs: now() - startedAt });
            return response;
          },
          (error) => {
            networkLog.push({ time: startedAt, kind: "fetch", method, url: String(url).slice(0, 200), error: String(error && error.message || error).slice(0, 160), durationMs: now() - startedAt });
            throw error;
          }
        );
      };
    }
    const OrigXHR = window.XMLHttpRequest;
    if (OrigXHR && OrigXHR.prototype && OrigXHR.prototype.open && OrigXHR.prototype.send) {
      const origOpen = OrigXHR.prototype.open;
      const origSend = OrigXHR.prototype.send;
      OrigXHR.prototype.open = function (method, url) {
        this.__harness_method = method;
        this.__harness_url = String(url).slice(0, 200);
        return origOpen.apply(this, arguments);
      };
      OrigXHR.prototype.send = function () {
        const startedAt = now();
        this.addEventListener("loadend", () => {
          networkLog.push({ time: startedAt, kind: "xhr", method: this.__harness_method, url: this.__harness_url, status: this.status, durationMs: now() - startedAt });
        });
        return origSend.apply(this, arguments);
      };
    }
  }

  if (passiveProbes.windowGlobalsScan) {
    Object.getOwnPropertyNames(window).forEach((k) => BUILTIN_WINDOW_KEYS.add(k));
    BUILTIN_WINDOW_KEYS.add("__HARNESS_BOOTSTRAP__");
    BUILTIN_WINDOW_KEYS.add("__ZERO_MOD_HARNESS__");
  }

  const originalConsole = {};
  ["log", "info", "warn", "error", "debug"].forEach((level) => {
    originalConsole[level] = console[level].bind(console);
    console[level] = function () {
      const args = Array.from(arguments);
      if (!consoleArgsIgnored(args)) {
        trace.console.push({
          time: now(),
          level,
          args: args.map((value) => summarizeValue(value))
        });
      }
      originalConsole[level].apply(console, arguments);
    };
  });

  window.addEventListener("error", (event) => {
    trace.errors.push({
      time: now(),
      type: "error",
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    trace.errors.push({
      time: now(),
      type: "unhandledrejection",
      reason: String(event.reason)
    });
  });

  document.addEventListener("pointerdown", (event) => {
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("pointermove", (event) => {
    const eventTime = now();
    if (eventTime - lastPointerMoveAt < 50) {
      return;
    }
    lastPointerMoveAt = eventTime;
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("pointerup", (event) => {
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("click", (event) => {
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("keydown", (event) => {
    recordEvent(event, { key: { key: event.key.length === 1 ? "character" : event.key, code: event.code, ctrlKey: event.ctrlKey, shiftKey: event.shiftKey, altKey: event.altKey } });
  }, true);

  document.addEventListener("keyup", (event) => {
    recordEvent(event, { key: { key: event.key.length === 1 ? "character" : event.key, code: event.code, ctrlKey: event.ctrlKey, shiftKey: event.shiftKey, altKey: event.altKey } });
  }, true);

  document.addEventListener("input", (event) => {
    const target = event.target;
    recordEvent(event, { form: { valueLength: target && "value" in target ? String(target.value).length : 0 } });
  }, true);

  document.addEventListener("change", (event) => {
    const target = event.target;
    recordEvent(event, { form: { checked: target && "checked" in target ? Boolean(target.checked) : null, selectedIndex: target && "selectedIndex" in target ? target.selectedIndex : null } });
  }, true);

  document.addEventListener("wheel", (event) => {
    recordEvent(event, { wheel: { deltaX: event.deltaX, deltaY: event.deltaY, deltaMode: event.deltaMode } });
  }, true);

  const harnessStyle = document.createElement("style");
  harnessStyle.textContent = `
    @keyframes __harness_pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%      { opacity: 0.4; transform: scale(0.7); }
    }
    #__zero_mod_harness_panel {
      position: fixed;
      top: 12px;
      right: 12px;
      z-index: 2147483647;
      padding: 10px 14px;
      background: #1a1a1a;
      color: #fff;
      font: 14px system-ui, -apple-system, sans-serif;
      border: 2px solid #555;
      border-radius: 8px;
      display: flex;
      gap: 10px;
      align-items: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.4);
      transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
    }
    #__zero_mod_harness_panel.recording {
      background: #b00020;
      border-color: #ff5252;
      box-shadow: 0 0 16px rgba(255, 82, 82, 0.8);
    }
    #__zero_mod_harness_panel .__h_dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #555;
      flex-shrink: 0;
    }
    #__zero_mod_harness_panel.recording .__h_dot {
      background: #ff3030;
      animation: __harness_pulse 1s ease-in-out infinite;
      box-shadow: 0 0 8px #ff3030;
    }
    #__zero_mod_harness_panel .__h_status {
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    #__zero_mod_harness_panel .__h_counts {
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      font-size: 13px;
      opacity: 0.85;
    }
    #__zero_mod_harness_panel button {
      font: inherit;
      font-size: 13px;
      padding: 4px 10px;
      border: 1px solid #777;
      border-radius: 4px;
      background: #2a2a2a;
      color: #fff;
      cursor: pointer;
    }
    #__zero_mod_harness_panel button:hover:not(:disabled) {
      background: #3a3a3a;
    }
    #__zero_mod_harness_panel button:disabled {
      opacity: 0.35;
      cursor: not-allowed;
    }
  `;

  const panel = document.createElement("div");
  panel.id = "__zero_mod_harness_panel";

  const dot = document.createElement("span");
  dot.className = "__h_dot";

  const panelStatus = document.createElement("span");
  panelStatus.className = "__h_status";

  const panelCounts = document.createElement("span");
  panelCounts.className = "__h_counts";

  const startButton = document.createElement("button");
  const stopButton = document.createElement("button");
  const saveButton = document.createElement("button");
  startButton.textContent = "Start";
  stopButton.textContent = "Stop";
  saveButton.textContent = "Save";
  startButton.addEventListener("click", startCapture);
  stopButton.addEventListener("click", stopCapture);
  saveButton.addEventListener("click", saveTrace);
  panel.append(dot, panelStatus, panelCounts, startButton, stopButton, saveButton);

  function updatePanel() {
    if (captureActive) {
      panel.classList.add("recording");
      panelStatus.textContent = "● REC";
    } else {
      panel.classList.remove("recording");
      panelStatus.textContent = "HARNESS idle";
    }
    panelCounts.textContent = "e:" + trace.events.length + " s:" + trace.snapshots.length;
    startButton.disabled = captureActive;
    stopButton.disabled = !captureActive;
    saveButton.disabled = trace.events.length === 0 && trace.snapshots.length === 0;
  }

  window.__ZERO_MOD_HARNESS__ = {
    version: 1,
    trace,
    startCapture,
    stopCapture,
    saveTrace,
    captureSnapshot
  };

  window.addEventListener("DOMContentLoaded", () => {
    document.head.appendChild(harnessStyle);
    document.body.appendChild(panel);
    updatePanel();
  });
})();
