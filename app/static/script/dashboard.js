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

  // Product view toggle (grid/list)
  const gridBtn = document.getElementById('view-grid');
  const listBtn = document.getElementById('view-list');
  const gridView = document.getElementById('grid-view');
  const listView = document.getElementById('list-view');

  if (gridBtn && listBtn && gridView && listView) {
    const setView = (view) => {
      const isGrid = view === 'grid';
      gridView.classList.toggle('hidden', !isGrid);
      listView.classList.toggle('hidden', isGrid);
      gridBtn.classList.toggle('bg-maroon', isGrid);
      gridBtn.classList.toggle('text-white', isGrid);
      gridBtn.classList.toggle('bg-white', !isGrid);
      gridBtn.classList.toggle('text-maroon', !isGrid);
      listBtn.classList.toggle('bg-maroon', !isGrid);
      listBtn.classList.toggle('text-white', !isGrid);
      listBtn.classList.toggle('bg-white', isGrid);
      listBtn.classList.toggle('text-maroon', isGrid);
      gridBtn.setAttribute('aria-pressed', isGrid ? 'true' : 'false');
      listBtn.setAttribute('aria-pressed', isGrid ? 'false' : 'true');
    };

    let savedView = 'grid';
    try {
      savedView = localStorage.getItem('admin_product_view') || 'grid';
    } catch (e) {
      savedView = 'grid';
    }
    if (savedView !== 'grid' && savedView !== 'list') savedView = 'grid';
    setView(savedView);

    gridBtn.addEventListener('click', () => {
      setView('grid');
      try { localStorage.setItem('admin_product_view', 'grid'); } catch (e) {}
    });
    listBtn.addEventListener('click', () => {
      setView('list');
      try { localStorage.setItem('admin_product_view', 'list'); } catch (e) {}
    });
  }
});
