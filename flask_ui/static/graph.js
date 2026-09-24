(function () {
  const nodes = document.querySelectorAll(".node[data-node]");
  const panels = document.querySelectorAll(".insp");
  if (!nodes.length) return;

  function show(id) {
    nodes.forEach((n) => n.classList.toggle("selected", n.dataset.node === id));
    panels.forEach((p) => p.classList.toggle("on", p.dataset.node === id));
  }

  nodes.forEach((n) => n.addEventListener("click", () => show(n.dataset.node)));

  const current = document.querySelector(".node.running, .node.failed, .node.selected");
  if (current) show(current.dataset.node);
})();
