// Lekh website: a theme switch and copy buttons. Nothing else.
(function () {
  var root = document.documentElement;
  var toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var dark = root.getAttribute('data-theme') === 'dark' ||
        (!root.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
      var next = dark ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('lekh-theme', next); } catch (e) {}
    });
  }
  document.querySelectorAll('.code:not(.output)').forEach(function (block) {
    var pre = block.querySelector('pre');
    if (!pre || !navigator.clipboard) return;
    var button = document.createElement('button');
    button.className = 'copy';
    button.type = 'button';
    button.textContent = 'Copy';
    button.addEventListener('click', function () {
      navigator.clipboard.writeText(pre.innerText).then(function () {
        button.textContent = 'Copied';
        setTimeout(function () { button.textContent = 'Copy'; }, 1500);
      });
    });
    block.appendChild(button);
  });
})();
