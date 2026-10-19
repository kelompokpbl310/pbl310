document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-dash-sidebar]");
  const overlay = document.querySelector("[data-dash-overlay]");
  const open = () => {
    sidebar?.classList.remove("-translate-x-full");
    overlay?.classList.remove("hidden");
  };
  const close = () => {
    if (window.innerWidth >= 1024) return;
    sidebar?.classList.add("-translate-x-full");
    overlay?.classList.add("hidden");
  };
  document.querySelector("[data-dash-open]")?.addEventListener("click", open);
  document.querySelector("[data-dash-close]")?.addEventListener("click", close);
  overlay?.addEventListener("click", close);

  // Filter status pesanan (frontend only)
  const btns = [...document.querySelectorAll("[data-status-filter] [data-filter]")];
  const rows = [...document.querySelectorAll("[data-order-rows] tr")];
  const empty = document.querySelector("[data-empty]");
  btns.forEach((b) =>
    b.addEventListener("click", () => {
      btns.forEach((x) => {
        const on = x === b;
        x.classList.toggle("bg-maroon", on);
        x.classList.toggle("text-white", on);
        x.classList.toggle("bg-white", !on);
        x.classList.toggle("text-maroon", !on);
      });
      const f = b.dataset.filter;
      let n = 0;
      rows.forEach((r) => {
        const show = f === "Semua" || r.dataset.status === f;
        r.classList.toggle("hidden", !show);
        if (show) n++;
      });
      empty?.classList.toggle("hidden", n > 0);
    }),
  );
});
