(function () {
  // tickCount is volatile by design: it changes every time anyone reads it,
  // so capture and replay snapshots will always diverge on this field unless
  // the harness honors the profile's volatileFields list.
  let tickCounter = 0;

  window.state = {
    count: 0,
    get tickCount() {
      tickCounter += 1;
      return tickCounter;
    }
  };

  window.debug = {
    snapshot() {
      return {
        count: window.state.count,
        tick: window.state.tickCount
      };
    },
    actionLog() { return []; },
    errors() { return []; },
    timing() { return { frameMs: 0 }; }
  };

  function renderStatus() {
    document.getElementById("status").textContent = JSON.stringify(window.debug.snapshot(), null, 2);
  }

  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("incrementBtn").addEventListener("click", () => {
      window.state.count += 1;
      renderStatus();
    });
    renderStatus();
  });
})();
