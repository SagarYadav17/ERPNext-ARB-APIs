frappe.ready(function () {
  fetch("/api/method/arb.arb_apis.doctype.tracking_settings.get_tracking_keys")
    .then(res => res.json())
    .then(r => {
      const data = r.message;
      if (!data || !data.enable_tracking || !data.ga_id) return;

      initGA(data.ga_id);
    })
    .catch(err => console.error("GA fetch error", err));
});

function initGA(gaId) {
  // Prevent duplicate loading
  if (window.gtag) return;

  const script = document.createElement("script");
  script.async = true;
  script.src = "https://www.googletagmanager.com/gtag/js?id=" + gaId;

  script.onload = function () {
    window.dataLayer = window.dataLayer || [];
    function gtag(){ dataLayer.push(arguments); }
    window.gtag = gtag;

    gtag("js", new Date());
    gtag("config", gaId, {
      debug_mode: true,
      send_page_view: true
    });

    console.log("Google Analytics loaded:", gaId);
  };

  document.head.appendChild(script);
}

