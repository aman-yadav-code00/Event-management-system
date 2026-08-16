/**
 * CampusEvents — Enhanced Interactions
 * 3D card tilts, smooth scroll, intersection observer animations,
 * real-time seat updates, and improved accessibility.
 */

document.addEventListener("DOMContentLoaded", function () {
  // ---- Mobile nav toggle ----
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      const isOpen = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      toggle.style.transform = isOpen ? "rotate(90deg)" : "rotate(0deg)";
    });
  }

  // ---- Navbar scroll effect ----
  const navbar = document.querySelector(".navbar");
  if (navbar) {
    let lastScroll = 0;
    window.addEventListener("scroll", function () {
      const currentScroll = window.pageYOffset;
      if (currentScroll > 10) {
        navbar.classList.add("scrolled");
      } else {
        navbar.classList.remove("scrolled");
      }
      lastScroll = currentScroll;
    }, { passive: true });
  }

  // ---- Auto-dismiss flash messages ----
  document.querySelectorAll(".flash").forEach(function (el, i) {
    setTimeout(function () {
      el.style.transition = "opacity .35s ease, transform .35s cubic-bezier(0.4, 0, 0.2, 1)";
      el.style.opacity = "0";
      el.style.transform = "translateX(20px) scale(0.95)";
      setTimeout(function () { el.remove(); }, 350);
    }, 5000 + i * 400);
  });

  // ---- 3D Card Tilt Effect ----
  const tiltCards = document.querySelectorAll(".card-3d, .event-card");
  tiltCards.forEach(function (card) {
    card.addEventListener("mousemove", function (e) {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = (y - centerY) / centerY * -3;
      const rotateY = (x - centerX) / centerX * 3;
      card.style.transform = "perspective(1000px) rotateX(" + rotateX + "deg) rotateY(" + rotateY + "deg) translateY(-4px)";
    });
    card.addEventListener("mouseleave", function () {
      card.style.transform = "";
      card.style.transition = "transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)";
      setTimeout(function () {
        card.style.transition = "";
      }, 500);
    });
  });

  // ---- Deterministic barcode pattern ----
  document.querySelectorAll("[data-barcode]").forEach(function (el) {
    var code = el.getAttribute("data-barcode") || "";
    var hash = 0;
    for (var i = 0; i < code.length; i++) {
      hash = (hash * 31 + code.charCodeAt(i)) >>> 0;
    }
    var bars = 48;
    for (var b = 0; b < bars; b++) {
      hash = (hash * 1103515245 + 12345) >>> 0;
      var h = 16 + (hash % 28);
      var bar = document.createElement("i");
      bar.style.height = h + "px";
      bar.style.opacity = (0.5 + (hash % 50) / 100).toFixed(2);
      el.appendChild(bar);
    }
  });

  // ---- Intersection Observer for fade-in animations ----
  const observerOptions = { threshold: 0.05, rootMargin: "0px 0px -30px 0px" };
  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("fade-in-visible");
        entry.target.style.opacity = "1";
        entry.target.style.transform = "translateY(0)";
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  document.querySelectorAll(".event-card, .card, .kpi, .section-head").forEach(function (el) {
    el.style.opacity = "0";
    el.style.transform = "translateY(16px)";
    el.style.transition = "opacity 0.5s ease, transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)";
    observer.observe(el);
  });

  // ---- Real-time seat counter update ----
  const seatCounters = document.querySelectorAll("[data-event-seats]");
  seatCounters.forEach(function (el) {
    var eventId = el.getAttribute("data-event-seats");
    if (!eventId) return;

    function updateSeats() {
      fetch("/api/event/" + eventId + "/seats")
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data.error) return;
          var pct = data.capacity > 0 ? (data.taken / data.capacity * 100) : 0;
          var bar = el.querySelector(".seat-bar > i");
          var text = el.querySelector(".availability");
          if (bar) bar.style.width = pct + "%";
          if (text) text.textContent = data.taken + "/" + data.capacity + " seats claimed";
          if (pct >= 80 && bar) bar.parentElement.classList.add("hot");
        })
        .catch(function () {});
    }
    updateSeats();
    setInterval(updateSeats, 15000); // Refresh every 15s
  });

  // ---- Button ripple effect ----
  document.querySelectorAll(".btn-primary, .btn-success").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      var rect = btn.getBoundingClientRect();
      var ripple = document.createElement("span");
      var size = Math.max(rect.width, rect.height);
      ripple.style.cssText = 
        "position:absolute;border-radius:50%;background:rgba(255,255,255,0.3);" +
        "width:" + size + "px;height:" + size + "px;" +
        "left:" + (e.clientX - rect.left - size/2) + "px;" +
        "top:" + (e.clientY - rect.top - size/2) + "px;" +
        "pointer-events:none;animation:ripple 0.6s ease-out;";
      btn.style.position = "relative";
      btn.style.overflow = "hidden";
      btn.appendChild(ripple);
      setTimeout(function () { ripple.remove(); }, 600);
    });
  });

  // ---- Smooth scroll for anchor links ----
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener("click", function (e) {
      var target = document.querySelector(this.getAttribute("href"));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  // ---- Form validation visual feedback ----
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var invalid = form.querySelectorAll(":invalid");
      invalid.forEach(function (field) {
        field.style.borderColor = "var(--danger)";
        field.style.boxShadow = "0 0 0 3px var(--danger-light)";
      });
    });
    form.querySelectorAll("input, textarea, select").forEach(function (field) {
      field.addEventListener("input", function () {
        if (field.checkValidity()) {
          field.style.borderColor = "";
          field.style.boxShadow = "";
        }
      });
    });
  });

  // ---- Copy ticket code to clipboard ----
  document.querySelectorAll(".ticket-code").forEach(function (code) {
    code.style.cursor = "pointer";
    code.title = "Click to copy";
    code.addEventListener("click", function () {
      navigator.clipboard.writeText(code.textContent.trim()).then(function () {
        var original = code.textContent;
        code.textContent = "Copied!";
        code.style.background = "rgba(99,102,241,0.2)";
        setTimeout(function () {
          code.textContent = original;
          code.style.background = "";
        }, 1200);
      });
    });
  });
});

// ---- Ripple keyframe injection ----
var style = document.createElement("style");
style.textContent = "@keyframes ripple { to { transform: scale(2.5); opacity: 0; } }";
document.head.appendChild(style);
