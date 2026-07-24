function renderThemes(db) {
  const container = document.getElementById("themes-list");
  const result = db.exec(`
    SELECT themes.name, sets.set_num, sets.name, sets.year, sets.official_url, sets.official_url_status,
           owned_boxes.set_num IS NOT NULL AS is_owned, buildability.coverage_pct
    FROM (
      SELECT set_num FROM owned_boxes
      UNION
      SELECT set_num FROM buildability
    ) scope
    JOIN sets ON sets.set_num = scope.set_num
    JOIN themes ON themes.id = sets.theme_id
    LEFT JOIN owned_boxes ON owned_boxes.set_num = sets.set_num
    LEFT JOIN buildability ON buildability.set_num = sets.set_num
    ORDER BY themes.name ASC, sets.set_num ASC
  `);

  container.innerHTML = "";

  if (result.length === 0) {
    container.innerHTML = '<p class="empty">No Sets in the current universe scope.</p>';
    return;
  }

  // Grouped client-side: one query joined through the owned ∪ Candidate
  // scope (mirrors similarity.js), then bucketed by theme name in JS rather
  // than with a second SQL round-trip per theme.
  const byTheme = new Map();
  for (const [
    themeName,
    setNum,
    name,
    year,
    officialUrl,
    officialUrlStatus,
    isOwned,
    coveragePct,
  ] of result[0].values) {
    if (!byTheme.has(themeName)) {
      byTheme.set(themeName, []);
    }
    byTheme.get(themeName).push({ setNum, name, year, officialUrl, officialUrlStatus, isOwned, coveragePct });
  }

  for (const [themeName, sets] of byTheme) {
    const section = document.createElement("section");
    section.className = "theme-group";
    const setsMarkup = sets
      .map((s) => {
        // Only owned Sets link to box.html — box.html reports "not found"
        // for a Candidate, since it isn't in owned_boxes (see box.js).
        const nameMarkup = s.isOwned
          ? `<a class="box-name" href="box.html?set_num=${encodeURIComponent(s.setNum)}">${s.name}</a>`
          : `<span class="box-name">${s.name}</span>`;
        const statusMarkup = s.isOwned
          ? '<span class="box-owned-badge">Owned</span>'
          : `<span class="buildability-score">${s.coveragePct.toFixed(1)}% buildable</span>`;
        return `
          <li class="box">
            ${nameMarkup}
            ${setNumMarkup(s.setNum)}
            <span class="box-year">${s.year}</span>
            ${statusMarkup}
            ${officialLinkMarkup(s.officialUrl, s.officialUrlStatus)}
          </li>
        `;
      })
      .join("");
    section.innerHTML = `
      <h2 class="theme-name">${themeName}</h2>
      <ul class="box-list">${setsMarkup}</ul>
    `;
    container.appendChild(section);
  }
}

loadDatabase()
  .then(renderThemes)
  .catch((error) => {
    document.getElementById("themes-list").innerHTML =
      '<p class="error">Could not load the catalog database.</p>';
    console.error(error);
  });
