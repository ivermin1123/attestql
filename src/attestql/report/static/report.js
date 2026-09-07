// What the page does not need. The marked tokens, the disclosure regions and the strip are
// HTML; this adds the two things a static page cannot state: the strip condenses once the
// reader has scrolled past the question, and the mechanism chip turns the token marking
// off, for a reader who wants to read the two statements without it.
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
})();
