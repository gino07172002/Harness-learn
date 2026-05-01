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
      stateSummaries: {}
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

  const panel = document.createElement("div");
  panel.id = "__zero_mod_harness_panel";
  panel.style.position = "fixed";
  panel.style.top = "8px";
  panel.style.right = "8px";
  panel.style.zIndex = "2147483647";
  panel.style.padding = "8px";
  panel.style.background = "#111";
  panel.style.color = "#fff";
  panel.style.font = "12px system-ui, sans-serif";
  panel.style.border = "1px solid #555";
  panel.style.borderRadius = "4px";
  panel.style.display = "flex";
  panel.style.gap = "6px";
  panel.style.alignItems = "center";

  const panelStatus = document.createElement("span");
  const startButton = document.createElement("button");
  const stopButton = document.createElement("button");
  const saveButton = document.createElement("button");
  startButton.textContent = "Start";
  stopButton.textContent = "Stop";
  saveButton.textContent = "Save";
  startButton.addEventListener("click", startCapture);
  stopButton.addEventListener("click", stopCapture);
  saveButton.addEventListener("click", saveTrace);
  panel.append(panelStatus, startButton, stopButton, saveButton);

  function updatePanel() {
    panelStatus.textContent = "HARNESS " + (captureActive ? "recording" : "idle") + " e:" + trace.events.length + " s:" + trace.snapshots.length;
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
    document.body.appendChild(panel);
    updatePanel();
  });
})();
