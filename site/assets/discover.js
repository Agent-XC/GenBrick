function renderDiscover(db) {
  const list = document.getElementById("discover-list");
  const result = db.exec(`
    SELECT sets.set_num, sets.name, sets.year, sets.num_parts, sets.official_url, sets.official_url_status, buildability.coverage_pct
    FROM buildability
    JOIN sets ON sets.set_num = buildability.set_num
    ORDER BY buildability.coverage_pct DESC, sets.name ASC
  `);

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = '<li class="empty">No Candidate sets in the current universe scope.</li>';
    return;
  }

  for (const [setNum, name, year, numParts, officialUrl, officialUrlStatus, coveragePct] of result[0].values) {
    const item = document.createElement("li");
    item.className = "box";
    // Every row here is a Candidate (this query's whole scope is
    // `buildability`), so — unlike numPartsMarkup's plain-text use on the
    // other Box-listing pages — the parts count links through to
    // candidate.html's Part/Color/Quantity/Owned-pool drill-down (issue
    // #16 backlog: "Buildability drill-down page").
    item.innerHTML = `
      <span class="box-name">${name}</span>
      ${setNumMarkup(setNum)}
      <span class="box-year">${year}</span>
      <a class="box-num-parts" href="candidate.html?set_num=${encodeURIComponent(setNum)}">${numParts} parts</a>
      <span class="buildability-score">${coveragePct.toFixed(1)}% buildable</span>
      ${officialLinkMarkup(officialUrl, officialUrlStatus)}
    `;
    list.appendChild(item);
  }
}

loadDatabase()
  .then(renderDiscover)
  .catch((error) => {
    document.getElementById("discover-list").innerHTML =
      '<li class="error">Could not load the catalog database.</li>';
    console.error(error);
  });
