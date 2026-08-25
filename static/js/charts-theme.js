// ============================================================
// Shared Chart.js theming for ARMS.
// Colors are the validated data-viz palette (light + dark steps),
// matched to the DaisyUI card surfaces:
//   light -> corporate (surface #ffffff)
//   dark  -> business  (surface #1d232a)
// Call armsViz() at render time and applyChartTheme() before
// constructing any chart so fonts/ticks follow the active theme.
// ============================================================
(function () {
  var LIGHT = {
    mode: 'light',
    surface: '#ffffff',
    series1: '#2a78d6',            // categorical slot 1 (blue)
    refGray: 'rgba(130,130,130,.45)', // de-emphasis reference (e.g. "Max")
    grid: '#e8e6df',               // hairline gridline
    tick: '#898781',               // axis/label muted ink
    cat: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
  };
  var DARK = {
    mode: 'dark',
    surface: '#1d232a',
    series1: '#3987e5',
    refGray: 'rgba(170,170,170,.45)',
    grid: '#333a44',
    tick: '#8f959e',
    cat: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
  };

  // Current theme's chart tokens (reads the DaisyUI data-theme attribute).
  window.armsViz = function () {
    return document.documentElement.getAttribute('data-theme') === 'business' ? DARK : LIGHT;
  };

  // '#rrggbb' + alpha -> 'rgba(r,g,b,a)'
  window.hexAlpha = function (hex, alpha) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
  };

  // Sync Chart.js global defaults with the active theme.
  window.applyChartTheme = function () {
    if (!window.Chart) return;
    var v = window.armsViz();
    Chart.defaults.color = v.tick;
    Chart.defaults.borderColor = v.grid;
    Chart.defaults.font.family = "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif";
  };
})();
