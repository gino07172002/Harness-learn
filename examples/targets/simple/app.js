(function () {
  window.state = {
    count: 0,
    name: "",
    points: []
  };

  window.debug = {
    snapshot() {
      return {
        count: window.state.count,
        nameLength: window.state.name.length,
        pointCount: window.state.points.length
      };
    },
    actionLog() {
      return window.state.points.map((point, index) => ({
        index,
        x: point.x,
        y: point.y
      }));
    },
    errors() {
      return [];
    },
    timing() {
      return { frameMs: 0 };
    }
  };

  function renderStatus() {
    document.getElementById("status").textContent = JSON.stringify(window.debug.snapshot(), null, 2);
  }

  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("incrementBtn").addEventListener("click", () => {
      window.state.count += 1;
      renderStatus();
    });

    document.getElementById("nameInput").addEventListener("input", (event) => {
      window.state.name = event.target.value;
      renderStatus();
    });

    document.getElementById("drawCanvas").addEventListener("pointerdown", (event) => {
      window.state.points.push({ x: event.offsetX, y: event.offsetY });
      renderStatus();
    });

    renderStatus();
  });
})();
