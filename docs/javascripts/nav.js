document$.subscribe(function () {
  document.querySelectorAll('.md-nav__item--nested > label.md-nav__link').forEach(function (label) {
    if (label.textContent.trim() === 'Getting Started') {
      var checkbox = document.getElementById(label.getAttribute('for'));
      if (checkbox) checkbox.checked = true;
    }
  });
});
