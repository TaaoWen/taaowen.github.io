"use strict";

(() => {
  const data = JSON.parse(document.querySelector("#network-data").textContent);
  const canvas = document.querySelector("#collaboration-graph");
  const ctx = canvas.getContext("2d");
  const viewport = document.querySelector("#graph-viewport");
  const query = document.querySelector("#collaborator-query");
  const select = document.querySelector("#relationship-type");
  const groups = new Map(data.groups.map((group) => [group.id, group]));
  const groupPositions = new Map(data.groups.map((group, index) => {
    const angle = index * Math.PI * 2 / data.groups.length - Math.PI / 2;
    return [group.id, { x: 190 * Math.cos(angle), y: 105 * Math.sin(angle) }];
  }));
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const personDetails = document.querySelector("#person-details");
  const count = document.querySelector("#collaborator-count");
  const empty = document.querySelector("#no-collaborators");
  const personButtons = [...document.querySelectorAll("[data-person]")];
  const allNodes = new Map(data.nodes.map((node) => [node.id, node]));
  const root = allNodes.get(data.root);
  root.fx = 0;
  root.fy = 0;

  let selected = root;
  let hovered;
  let width = 0;
  let height = 0;
  let ratio = 1;
  let nodes = [];
  let edges = [];
  let transform = d3.zoomIdentity;
  const surface = d3.select(canvas);
  const simulation = d3.forceSimulation()
    .force("links", d3.forceLink().id((node) => node.id)
      .distance((edge) => edge.source === root || edge.target === root ? 87 : 51)
      .strength((edge) => edge.source === root || edge.target === root ? .24 : .30))
    .force("charge", d3.forceManyBody().strength(-103))
    .force("collision", d3.forceCollide((node) => radius(node) + 7))
    .force("x", d3.forceX((node) => groupPositions.get(node.group)?.x || 0).strength(.09))
    .force("y", d3.forceY((node) => groupPositions.get(node.group)?.y || 0).strength(.09))
    .on("tick", draw)
    .stop();
  const zoom = d3.zoom().scaleExtent([.24, 3.8]).on("zoom", (event) => {
    transform = event.transform;
    draw();
  });
  const drag = d3.drag().clickDistance(4).subject((event) => hit(event.x, event.y))
    .on("start", (event) => {
      const node = event.subject;
      if (node !== root) {
        node.fx = node.x;
        node.fy = node.y;
        simulation.alphaTarget(.16).restart();
      }
    })
    .on("drag", (event) => {
      const node = event.subject;
      if (node !== root) {
        node.fx += event.dx / transform.k;
        node.fy += event.dy / transform.k;
      }
    })
    .on("end", (event) => {
      const node = event.subject;
      if (node !== root) {
        simulation.alphaTarget(0);
        node.fx = null;
        node.fy = null;
      }
    });

  // A drag on a person moves that node. A drag on empty space pans the viewport.
  surface.call(drag).call(zoom);
  const buttons = {
    "zoom-out": () => surface.call(zoom.scaleBy, 0.8),
    "zoom-in": () => surface.call(zoom.scaleBy, 1.25),
    "zoom-reset": fit,
  };
  for (const [id, action] of Object.entries(buttons)) {
    document.getElementById(id).addEventListener("click", action);
  }
  surface.on("click.network", (event) => {
    const node = hit(...d3.pointer(event, canvas));
    if (node) choose(node, false);
  });
  surface.on("pointermove.network", (event) => {
    const current = hit(...d3.pointer(event, canvas));
    if (current !== hovered) {
      hovered = current;
      canvas.style.cursor = hovered ? "pointer" : "";
      draw();
    }
  });
  surface.on("pointerleave.network", () => {
    hovered = undefined;
    canvas.style.cursor = "";
    draw();
  });

  personButtons.forEach((button) => {
    button.addEventListener("click", () => choose(allNodes.get(button.dataset.person), true));
  });
  query.addEventListener("input", applyFilters);
  select.addEventListener("change", applyFilters);
  new ResizeObserver(resize).observe(viewport);

  function radius(node) {
    return node === root ? 13 : Math.min(13, 4.2 + Math.sqrt(node.papers.length + node.projects.length) * 1.75);
  }

  function hit(screenX, screenY) {
    const [x, y] = transform.invert([screenX, screenY]);
    return nodes.findLast((node) => Math.hypot(node.x - x, node.y - y) <= radius(node) + 4 / transform.k);
  }

  function edgeLine(edge, colour, dashed, highlighted, offset = 0) {
    const { source, target } = edge;
    const length = Math.hypot(target.x - source.x, target.y - source.y) || 1;
    const xShift = offset * (target.y - source.y) / length;
    const yShift = offset * (source.x - target.x) / length;
    ctx.beginPath();
    ctx.moveTo(source.x + xShift, source.y + yShift);
    ctx.lineTo(target.x + xShift, target.y + yShift);
    ctx.lineWidth = (highlighted ? 1.8 : 1) / transform.k;
    ctx.strokeStyle = colour;
    ctx.globalAlpha = highlighted ? .76 : (selected === root ? .39 : .16);
    ctx.setLineDash(dashed ? [4 / transform.k, 4 / transform.k] : []);
    ctx.stroke();
  }

  function draw() {
    if (!width) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);
    for (const edge of edges) {
      const highlight = selected !== root && (edge.source === selected || edge.target === selected);
      if (edge.coauthor) edgeLine(edge, "#287587", false, highlight, edge.project ? -1.8 : 0);
      if (edge.project) edgeLine(edge, "#9c6630", true, highlight, edge.coauthor ? 1.8 : 0);
    }
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    for (const node of nodes) {
      const active = node === selected || node === hovered;
      const r = radius(node);
      if (active) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 3.5 / transform.k, 0, Math.PI * 2);
        ctx.fillStyle = node.papers.length || node === root ? "#c5e0e3" : "#f2dbc3";
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = node === root ? "#144c5a" : groups.get(node.group)?.colour || "#7b8790";
      ctx.fill();
      ctx.lineWidth = (node.projects.length && node.papers.length && node !== root ? 2 : 1) / transform.k;
      ctx.strokeStyle = node.projects.length && node.papers.length && node !== root ? "#9c6630" : "#f5fbfb";
      ctx.stroke();
    }
    const positions = [];
    const preferred = new Set([root, selected, hovered].filter((node) => nodes.includes(node)));
    const candidates = [...preferred, ...nodes.filter((node) => !preferred.has(node))];
    for (const node of candidates) {
      const featured = preferred.has(node);
      if (!featured && nodes.length > 12 && (node.papers.length < 3 || query.value.trim())) continue;
      const size = (node === root || node === selected ? 11.7 : 10.5) / transform.k;
      ctx.font = (node === root || node === selected ? "650 " : "540 ") + size + "px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      const y = node.y - radius(node) - 5 / transform.k;
      const halfWidth = ctx.measureText(node.name).width / 2 + 4 / transform.k;
      const bounds = { left: node.x - halfWidth, right: node.x + halfWidth, top: y - size, bottom: y };
      const overlaps = positions.some((label) => label.left < bounds.right && label.right > bounds.left
        && label.top < bounds.bottom && label.bottom > bounds.top);
      if (!featured && overlaps) continue;
      positions.push(bounds);
      ctx.lineWidth = 2.9 / transform.k;
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#f4f8f9";
      ctx.strokeText(node.name, node.x, y);
      ctx.fillStyle = "#203841";
      ctx.fillText(node.name, node.x, y);
    }
  }

  function fit() {
    if (!width) return;
    const maxX = d3.max(nodes, (node) => Math.abs(node.x) + radius(node)) || 20;
    const maxY = d3.max(nodes, (node) => Math.abs(node.y) + radius(node)) || 20;
    const scale = Math.max(.24, Math.min(1.45, (width / 2 - 55) / maxX, (height / 2 - 54) / maxY));
    surface.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(scale));
  }

  function resize() {
    const bounds = viewport.getBoundingClientRect();
    width = bounds.width;
    height = bounds.height;
    ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    fit();
  }

  function applyFilters() {
    const term = searchText(query.value);
    const relation = select.value;
    const relationshipVisible = (edge, type) => relation === "all" || relation === type;
    const available = data.links.map((edge) => ({
      ...edge,
      coauthor: relationshipVisible(edge, "coauthor") ? edge.coauthor : 0,
      project: relationshipVisible(edge, "project") ? edge.project : 0,
    })).filter((edge) => edge.coauthor || edge.project);
    const related = new Set(available.flatMap((edge) => [edge.source, edge.target]));
    nodes = data.nodes.filter((node) => node === root || (related.has(node.id)
      && searchText([node.name, ...node.affiliations].join(" ")).includes(term)));
    const ids = new Set(nodes.map((node) => node.id));
    edges = available.filter((edge) => ids.has(edge.source) && ids.has(edge.target));
    simulation.stop();
    // Reset the old links before switching to a new node set.
    simulation.force("links").links([]);
    simulation.nodes(nodes);
    simulation.force("links").links(edges);
    simulation.alpha(.85).tick(100);
    if (!reduceMotion && nodes.length > 1) simulation.alpha(.11).restart();
    hovered = undefined;
    if (!ids.has(selected.id)) choose(root, false);
    for (const button of personButtons) {
      button.closest("li").hidden = !ids.has(button.dataset.person);
    }
    count.textContent = "(" + (nodes.length - 1) + ")";
    empty.hidden = nodes.length > 1;
    fit();
  }

  function addText(tag, text, parent, className) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    parent.append(element);
    return element;
  }

  function choose(node, reveal) {
    selected = node;
    for (const button of personButtons) {
      button.setAttribute("aria-pressed", String(button.dataset.person === node.id));
    }
    personDetails.replaceChildren();
    const name = addText("h2", node.name, personDetails);
    name.id = "person-name";
    if (node.affiliations.length) {
      const note = addText("p", node.affiliations.join(" · "), personDetails, "person-affiliation");
      note.title = node.affiliation_source;
    }
    if (node.url) {
      const link = addText("a", "Profile →", personDetails, "inline-link");
      link.href = node.url;
      link.target = "_blank";
      link.rel = "noopener";
    }
    if (node === root) {
      addText("p", "Select a collaborator to see shared publications and research projects.", personDetails);
    } else {
      addText("h3", "Co-authored publications (" + node.papers.length + ")", personDetails);
      if (node.papers.length) {
        const papers = addText("ul", "", personDetails);
        for (const id of node.papers) {
          const paper = data.papers[id];
          const row = addText("li", "", papers);
          const link = addText("a", paper.title + (paper.year ? " (" + paper.year + ")" : ""), row);
          link.href = "../publication/#" + id;
        }
      }
      if (node.projects.length) {
        addText("h3", "Research projects (" + node.projects.length + ")", personDetails);
        const projects = addText("ul", "", personDetails);
        for (const index of node.projects) {
          const project = data.projects[index];
          const row = addText("li", "", projects);
          const link = addText("a", project.name, row);
          link.href = "../projects/#" + project.id;
          addText("small", project.programme + " · " + project.year, row, "project-context");
        }
      }
    }
    if (reveal) {
      const p = transform.apply([node.x, node.y]);
      if (p[0] < 23 || p[0] > width - 23 || p[1] < 23 || p[1] > height - 23) fit();
    }
    draw();
  }

  applyFilters();
  resize();
  const target = new URLSearchParams(window.location.search).get("person");
  const fromProject = data.nodes.find((node) => node.name === target);
  if (fromProject) choose(fromProject, false);
})();
