"use strict";

const searchText = (text) => text.normalize("NFKD")
  .replace(/\p{Mark}/gu, "")
  .toLowerCase()
  .replace(/[^\p{Letter}\p{Number}]+/gu, " ")
  .trim();

const paperQuery = document.querySelector("#paper-query");
if (paperQuery) {
  const type = document.querySelector("#paper-type");
  const year = document.querySelector("#paper-year");
  const count = document.querySelector("#paper-count");
  const empty = document.querySelector("#no-papers");
  const clear = document.querySelector("#clear-filters");
  const work = [...document.querySelectorAll("[data-paper]")].map((element) => ({
    element,
    text: searchText([
      ...[...element.querySelectorAll(".paper-title, .paper-authors, .paper-venue, .venue-label")].map((part) => part.textContent),
      element.dataset.topic,
    ].join(" ")),
  }));

  function filterPublications() {
    const query = searchText(paperQuery.value);
    const words = query ? query.split(" ") : [];
    let visible = 0;
    for (const { element, text } of work) {
      const show = (!type.value || type.value === element.dataset.type)
        && (!year.value || year.value === element.dataset.year)
        && words.every((word) => text.includes(word));
      element.hidden = !show;
      visible += Number(show);
    }
    count.textContent = visible === 1 ? "1 publication" : visible + " publications";
    empty.hidden = visible !== 0;
    empty.textContent = type.value === "Work in progress / under review" && !paperQuery.value && !year.value
      ? "No working papers or submissions are listed yet."
      : "No publications match these filters.";
    clear.hidden = !(paperQuery.value || type.value || year.value);
  }

  paperQuery.addEventListener("input", filterPublications);
  type.addEventListener("change", filterPublications);
  year.addEventListener("change", filterPublications);
  clear.addEventListener("click", () => {
    paperQuery.value = "";
    type.value = "";
    year.value = "";
    filterPublications();
    paperQuery.focus();
  });
  filterPublications();
}

const dialog = document.querySelector("#cite-dialog");
const citationValue = document.querySelector("#citation-value");
const copyStatus = document.querySelector("#copy-status");
for (const button of document.querySelectorAll("[data-cite]")) {
  button.addEventListener("click", () => {
    const citation = button.closest("[data-paper]").querySelector(".bibtex-data");
    citationValue.value = citation.content.textContent.trim();
    copyStatus.textContent = "";
    dialog.showModal();
  });
}
document.querySelector("#copy-citation").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(citationValue.value);
    copyStatus.textContent = "Copied.";
  } catch {
    citationValue.select();
    const copied = document.execCommand("copy");
    copyStatus.textContent = copied ? "Copied." : "Press Ctrl+C or ⌘C to copy.";
  }
});
