// What the page does not need. The marked tokens, the disclosure regions and the strip are
// HTML; this adds the three things a static page cannot state: the strip condenses once the
// reader has scrolled past the question, the mechanism chip turns the token marking off for
// a reader who wants to read the two statements without it, and every disclosure opens
// before the page is printed, so that paper holds what the screen would have held after a
// reader opened all of them.
(function () {
  "use strict";

  var strip = document.querySelector(".strip");
  if (strip) {
    var condense = function () {
      strip.classList.toggle("strip--condensed", window.scrollY > 48);
    };
    window.addEventListener("scroll", condense, { passive: true });
    condense();
  }

  var chip = document.querySelector(".chip--mechanism");
  var statements = document.getElementById("statements");
  if (chip && statements) {
    chip.setAttribute("aria-pressed", "true");
    chip.addEventListener("click", function () {
      var on = statements.getAttribute("data-marking") === "on";
      statements.setAttribute("data-marking", on ? "off" : "on");
      chip.setAttribute("aria-pressed", on ? "false" : "true");
    });
  }

  // The print stylesheet reaches a closed disclosure through `details::details-content`,
  // which a browser that has not implemented it ignores. This is the same instruction to
  // that browser, and it puts back what it changed, so a reader whose printer dialogue
  // they cancelled finds the page as they left it.
  var closed = [];
  var openAll = function () {
    closed = [].slice.call(document.querySelectorAll("details:not([open])"));
    closed.forEach(function (details) {
      details.setAttribute("open", "");
    });
  };
  var restore = function () {
    closed.forEach(function (details) {
      details.removeAttribute("open");
    });
    closed = [];
  };
  window.addEventListener("beforeprint", openAll);
  window.addEventListener("afterprint", restore);
})();
