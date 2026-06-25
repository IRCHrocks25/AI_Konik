(function () {
  if (window.__sopAssistantLoaderInit) return;
  window.__sopAssistantLoaderInit = true;

  var script = document.currentScript;
  if (!script) {
    var scripts = document.getElementsByTagName("script");
    script = scripts[scripts.length - 1];
  }
  if (!script) return;

  var ds = script.dataset || {};
  var slug = (ds.assistant || "").trim();
  if (!slug) return;

  var origin = "{{ public_origin|escapejs }}";
  var qp = new URLSearchParams();
  ["brand", "greeting", "logoUrl", "orbLogoUrl", "launcherLabel"].forEach(function (key) {
    if (!ds[key]) return;
    var param = key.replace(/[A-Z]/g, function (m) { return "_" + m.toLowerCase(); });
    qp.set(param, ds[key]);
  });

  var iframeUrl = origin + "/embed/assistant/" + encodeURIComponent(slug) + "/";
  var qs = qp.toString();
  if (qs) iframeUrl += "?" + qs;

  var btn = document.createElement("button");
  btn.type = "button";
  btn.setAttribute("aria-label", ds.launcherLabel || "Open assistant");
  btn.textContent = ds.launcherLabel || "Need help? Ask us!";
  btn.style.cssText = [
    "position:fixed",
    "right:20px",
    "bottom:20px",
    "z-index:2147483646",
    "border:0",
    "border-radius:999px",
    "padding:12px 18px",
    "background:#0d7c66",
    "color:#fff",
    "font:600 14px Arial,sans-serif",
    "cursor:pointer",
    "box-shadow:0 10px 28px rgba(0,0,0,.28)"
  ].join(";");

  var panel = document.createElement("div");
  panel.style.cssText = [
    "position:fixed",
    "right:20px",
    "bottom:72px",
    "width:min(420px,calc(100vw - 24px))",
    "height:min(760px,calc(100vh - 100px))",
    "z-index:2147483646",
    "background:#fff",
    "border-radius:16px",
    "overflow:hidden",
    "display:none",
    "box-shadow:0 18px 42px rgba(0,0,0,.3)"
  ].join(";");

  var iframe = document.createElement("iframe");
  iframe.src = iframeUrl;
  iframe.title = ds.brand ? ds.brand + " assistant" : "AI assistant";
  iframe.allow = "microphone; camera";
  iframe.style.cssText = "border:0;width:100%;height:100%;";
  panel.appendChild(iframe);

  var close = document.createElement("button");
  close.type = "button";
  close.setAttribute("aria-label", "Close assistant");
  close.textContent = "×";
  close.style.cssText = [
    "position:absolute",
    "right:10px",
    "top:8px",
    "z-index:2",
    "border:0",
    "background:rgba(0,0,0,.45)",
    "color:#fff",
    "width:28px",
    "height:28px",
    "border-radius:999px",
    "cursor:pointer",
    "font-size:18px",
    "line-height:1"
  ].join(";");
  panel.appendChild(close);

  function toggle(open) {
    panel.style.display = open ? "block" : "none";
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  btn.addEventListener("click", function () {
    toggle(panel.style.display === "none");
  });
  close.addEventListener("click", function () { toggle(false); });

  document.body.appendChild(panel);
  document.body.appendChild(btn);
})();
