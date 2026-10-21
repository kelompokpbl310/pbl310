document.addEventListener("DOMContentLoaded", () => {
  const $ = (s, r = document) => r.querySelector(s),
    $$ = (s, r = document) => [...r.querySelectorAll(s)];
  $("[data-menu-btn]")?.addEventListener("click", () =>
    $("[data-menu]").classList.toggle("hidden"),
  );
  $$("[data-carousel]").forEach((c) => {
    const sl = $$("[data-slide]", c),
      dt = $$("[data-dot]", c);
    let i = 0;
    const show = (n) => {
      i = (n + sl.length) % sl.length;
      sl.forEach((s, k) => s.classList.toggle("hidden", k !== i));
      dt.forEach((d, k) => {
        d.classList.toggle("w-8", k === i);
        d.classList.toggle("w-2.5", k !== i);
        d.classList.toggle("opacity-40", k !== i);
      });
    };
    $("[data-prev]", c)?.addEventListener("click", () => show(i - 1));
    $("[data-next]", c)?.addEventListener("click", () => show(i + 1));
    dt.forEach((d, k) => d.addEventListener("click", () => show(k)));
    let tx = null;
    c.addEventListener(
      "touchstart",
      (e) => {
        tx = e.touches[0].clientX;
      },
      { passive: true },
    );
    c.addEventListener(
      "touchend",
      (e) => {
        if (tx === null) return;
        const dx = e.changedTouches[0].clientX - tx;
        tx = null;
        if (Math.abs(dx) < 40) return;
        show(i + (dx < 0 ? 1 : -1));
      },
      { passive: true },
    );
  });
  $$("[data-promo]").forEach((b) => {
    const track = $("[data-promo-track]", b);
    if (!track) return;
    const sl = Array.from(track.querySelectorAll("[data-promo-slide]"));
    let dotsWrap = $("[data-promo-dots]", b);
    if (!sl.length || !dotsWrap) return;
    // Cache the slide count and generate dots dynamically.
    const n = sl.length;
    const head = sl[0];
    // Build dots inside the dots container.
    dotsWrap.innerHTML = sl
      .map(
        (_, k) =>
          `<button type="button" data-promo-dot="${k}" class="promo-dot h-2 rounded-full transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-maroon ${k === 0 ? "w-8 bg-maroon" : "w-2.5 bg-maroon/40"}" aria-label="Tampilkan slide ${k + 1}" ${k === 0 ? 'aria-current="true"' : ""}></button>`,
      )
      .join("");
    const dt = $$("[data-promo-dot]", b);
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Make non-active slides inert for screen readers / keyboards.
    const setInert = () => {
      sl.forEach((s, k) => {
        const on = k === i;
        s.setAttribute("aria-hidden", on ? "false" : "true");
        if (on) s.removeAttribute("inert");
        else s.setAttribute("inert", "");
      });
    };

    let i = 0;
    const update = () => {
      const offset = i * -100;
      track.style.transform = `translateX(${offset}%)`;
      track.style.transitionDuration = reduced ? "0ms" : "500ms";
      track.classList.toggle("motion-reduce:transition-none", reduced);
      dt.forEach((d, k) => {
        const on = k === i;
        d.classList.toggle("w-8", on);
        d.classList.toggle("bg-maroon", on);
        d.classList.toggle("w-2.5", !on);
        d.classList.toggle("bg-maroon/40", !on);
        if (on) d.setAttribute("aria-current", "true");
        else d.removeAttribute("aria-current");
      });
      setInert();
    };

    // Looping: direction-aware navigation by index wrap (no rewind rewind).
    const go = (target) => {
      const len = sl.length;
      let next = ((target % len) + len) % len;
      if (next === i) return;
      i = next;
      update();
      // Restart auto-rotate timer.
      stop();
      start();
    };

    const play = () => go(i + 1);
    let timer = null;
    const start = () => {
      if (reduced) return;
      if (!timer) timer = setInterval(play, 5000);
    };
    const stop = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };

    // Arrow buttons.
    $("[data-promo-prev]", b)?.addEventListener("click", () => go(i - 1));
    $("[data-promo-next]", b)?.addEventListener("click", () => go(i + 1));

    // Keyboard support when banner has focus.
    b.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        go(i - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        go(i + 1);
      }
    });

    // Dots click.
    dt.forEach((d, k) =>
      d.addEventListener("click", () => {
        go(k);
      }),
    );

    // Hover / focus pause.
    b.addEventListener("mouseenter", stop);
    b.addEventListener("mouseleave", () => start());
    b.addEventListener("focusin", stop);
    b.addEventListener("focusout", (e) => {
      if (!b.contains(e.relatedTarget)) start();
    });

    // Pause while tab hidden.
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop();
      else start();
    });

    // Touch swipe that doesn't hijack vertical scroll.
    let sx = null,
      sy = null;
    b.addEventListener(
      "touchstart",
      (e) => {
        sx = e.touches[0].clientX;
        sy = e.touches[0].clientY;
      },
      { passive: true },
    );
    b.addEventListener(
      "touchmove",
      (e) => {
        if (sx === null) return;
        const dx = e.touches[0].clientX - sx;
        const dy = e.touches[0].clientY - sy;
        if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
          e.preventDefault();
        }
      },
      { passive: false },
    );
    b.addEventListener(
      "touchend",
      (e) => {
        if (sx === null) return;
        const dx = e.changedTouches[0].clientX - sx;
        sx = null;
        sy = null;
        if (Math.abs(dx) < 40) return;
        go(i + (dx < 0 ? 1 : -1));
      },
      { passive: true },
    );

    // First image eager load, others lazy (already set in markup).
    update();
    start();
  });
  $$("[data-tab]").forEach((b) =>
    b.addEventListener("click", () => {
      $$("[data-tab]").forEach((t) => {
        const on = t === b;
        t.classList.toggle("border-maroon", on);
        t.classList.toggle("text-maroon", on);
        t.classList.toggle("border-transparent", !on);
        t.classList.toggle("text-stone-500", !on);
      });
      $$("[data-panel]").forEach((p) =>
        p.classList.toggle("hidden", p.dataset.panel !== b.dataset.tab),
      );
    }),
  );
  const q = $("[data-qty]");
  $("[data-qty-minus]")?.addEventListener("click", () => {
    if (q.value > 1) q.value--;
  });
  $("[data-qty-plus]")?.addEventListener("click", () => q.value++);
  $$("[data-chip]").forEach((c) =>
    c.addEventListener("click", () => c.classList.toggle("is-active")),
  );
  $("[data-coupon-toggle]")?.addEventListener("click", () => {
    const b = $("[data-coupon-box]");
    b.classList.toggle("hidden");
    b.classList.toggle("flex");
  });
  $("#checkout-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    $("[data-order-success]").classList.remove("hidden");
  });

  // Interactive goat cut map (only initialised on pages with #goat + #highlight)
  (() => {
    const goat = document.getElementById("goat"),
      canvas = document.getElementById("highlight");
    if (!goat || !canvas || !goat.dataset.cutMap) return;
    const ctx = canvas.getContext("2d");
    const meta = {1:{name:'Leher',text:'Cocok untuk gulai, sop, atau masakan yang dimasak perlahan.'},2:{name:'Bahu',text:'Cocok untuk semur, gulai, atau masakan lambat.'},3:{name:'Rangka Iga',text:'Potongan bertulang untuk kaldu, sop, dan gulai.'},4:{name:'Loin',text:'Bagian pinggang yang cocok untuk sate atau panggang.'},5:{name:'Sirloin',text:'Bagian punggung belakang yang cocok untuk sate atau bakar.'},6:{name:'Paha Belakang',text:'Cocok untuk semur atau sate.'},7:{name:'Sengkel Belakang',text:'Cocok untuk masakan berkuah yang dimasak lama.'},8:{name:'Dada',text:'Cocok untuk sop atau gulai.'},9:{name:'Samping',text:'Cocok untuk masakan berkuah atau cincang.'},10:{name:'Sengkel Depan',text:'Cocok untuk kaldu dan masakan lambat.'}};
    const buttons = [...document.querySelectorAll('#cut-buttons .cut-btn')];
    const infoTitle = document.getElementById('infoTitle');
    const infoText = document.getElementById('infoText');
    const tooltip = document.getElementById('cut-tooltip');
    const tipTitle = document.getElementById('cut-tip-title');
    const tipText = document.getElementById('cut-tip-text');
    let pixels = null, current = 0, selected = 0;
    const map = new Image();
    map.onload = () => {
      const off = document.createElement('canvas');
      off.width = map.width; off.height = map.height;
      const c = off.getContext('2d', {willReadFrequently: true});
      c.drawImage(map, 0, 0);
      pixels = c.getImageData(0, 0, off.width, off.height).data;
      if (selected) { current = 0; paint(selected); }
    };
    map.src = goat.dataset.cutMap;
    function paint(id) {
      if (id === current) return;
      current = id;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      buttons.forEach(b => {
        const active = Number(b.dataset.id) === id;
        b.classList.toggle('bg-maroon', active);
        b.classList.toggle('text-white', active);
        b.setAttribute('aria-pressed', String(active));
      });
      if (!id || !pixels) return;
      const frame = ctx.createImageData(canvas.width, canvas.height);
      const d = frame.data;
      for (let j = 0; j < pixels.length; j += 4) {
        if (pixels[j] === id && pixels[j + 3]) {
          d[j] = 255; d[j + 1] = 211; d[j + 2] = 70; d[j + 3] = 125;
        }
      }
      ctx.putImageData(frame, 0, 0);
      infoTitle.textContent = meta[id].name;
      infoText.textContent = meta[id].text;
    }
    function hit(e) {
      if (!pixels) return 0;
      const r = goat.getBoundingClientRect();
      const x = Math.floor((e.clientX - r.left) * canvas.width / r.width);
      const y = Math.floor((e.clientY - r.top) * canvas.height / r.height);
      if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return 0;
      const i = (y * canvas.width + x) * 4;
      return pixels[i + 3] ? pixels[i] : 0;
    }
    function hideTip() { if (tooltip) tooltip.classList.add('hidden'); }
    function showTip(id, x, y) {
      if (!tooltip || !tipTitle || !tipText) return;
      tipTitle.textContent = meta[id].name;
      tipText.textContent = meta[id].text;
      tooltip.classList.remove('hidden');
      const pad = 12, w = tooltip.offsetWidth, h = tooltip.offsetHeight;
      tooltip.style.left = Math.max(pad, Math.min(innerWidth - w - pad, x + 16)) + 'px';
      tooltip.style.top = Math.max(pad, Math.min(innerHeight - h - pad, y + 16)) + 'px';
    }
    goat.addEventListener('pointermove', e => {
      const id = hit(e);
      goat.style.cursor = id ? 'pointer' : 'default';
      if (!id) { hideTip(); paint(selected); return; }
      paint(id);
      if (e.pointerType === 'mouse' || e.pointerType === 'pen') showTip(id, e.clientX, e.clientY);
    });
    goat.addEventListener('pointerleave', () => { hideTip(); paint(selected); });
    goat.addEventListener('click', e => {
      const id = hit(e);
      if (!id) return;
      selected = id;
      paint(id);
      hideTip();
    });
    buttons.forEach(b => {
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', () => {
        selected = Number(b.dataset.id);
        paint(selected);
        hideTip();
      });
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') { selected = 0; paint(0); hideTip(); }
    });
  })();

  // Profile dropdown toggle
  const profileBtn = document.getElementById('profile-btn');
  const profileMenu = document.getElementById('profile-menu');

  if (profileBtn && profileMenu) {
    profileBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      profileMenu.classList.toggle('hidden');
      profileBtn.setAttribute('aria-expanded', !profileMenu.classList.contains('hidden'));
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
      if (!profileBtn.contains(e.target) && !profileMenu.contains(e.target)) {
        profileMenu.classList.add('hidden');
        profileBtn.setAttribute('aria-expanded', 'false');
      }
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        profileMenu.classList.add('hidden');
        profileBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // Avatar preview on file select
  $("[data-avatar-input]")?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const preview = $("#avatar-preview");
      if (preview) {
        preview.innerHTML = `<img src="${ev.target.result}" alt="Preview" class="h-full w-full object-cover" />`;
      }
    };
    reader.readAsDataURL(file);
  });

  // Password strength meter
  const pwInput = $("#new_password");
  const pwBar = $("#password-strength-fill");
  const pwText = $("#password-strength-text");
  if (pwInput && pwBar && pwText) {
    pwInput.addEventListener('input', () => {
      const val = pwInput.value;
      let score = 0;
      if (val.length >= 8) score++;
      if (/[A-Z]/.test(val)) score++;
      if (/[a-z]/.test(val)) score++;
      if (/[0-9]/.test(val)) score++;
      if (/[^A-Za-z0-9]/.test(val)) score++;
      const pct = (score / 5) * 100;
      pwBar.style.width = pct + '%';
      pwBar.style.backgroundColor = score <= 2 ? '#f87171' : score <= 3 ? '#fbbf24' : '#34d399';
      const labels = ['Sangat lemah', 'Lemah', 'Sedang', 'Kuat', 'Sangat kuat'];
      pwText.textContent = labels[score - 1] || 'Minimal 8 karakter';
    });
  }

  // Flash message auto-dismiss
  $$("[data-flash]").forEach((el) => {
    const delay = Number(el.dataset.flash) || 5000;
    setTimeout(() => {
      el.style.transition = "opacity 300ms ease, transform 300ms ease";
      el.style.opacity = "0";
      el.style.transform = "translateY(-8px)";
      setTimeout(() => el.remove(), 300);
    }, delay);
  });

  // Product filter tabs
  $$(".filter-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      // Update active tab
      $$(".filter-tab").forEach((t) => {
        const on = t === btn;
        t.classList.toggle("bg-maroon", on);
        t.classList.toggle("text-white", on);
        t.classList.toggle("border-maroon", on);
        t.classList.toggle("bg-maroon/30", !on);
        t.classList.toggle("text-maroon", !on);
        t.setAttribute("aria-selected", on);
      });
      // Filter cards
      $$(".product-card").forEach((card) => {
        const cat = card.dataset.category;
        const show = filter === "all" || cat.toLowerCase() === filter.toLowerCase();
        card.classList.toggle("hidden", !show);
      });
    });
  });
});
