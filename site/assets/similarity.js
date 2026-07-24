function renderSimilarity(db) {
  const list = document.getElementById("similarity-list");
  const result = db.exec(`
    SELECT sets.set_num, sets.name, similarity_topk.rank, other.set_num, other.name, similarity_topk.score
    FROM (
      SELECT set_num FROM owned_boxes
      UNION
      -- inventories, not buildability: Similarity only has a part-count
      -- floor and a score floor of its own (issue #15) — it must not
      -- inherit Buildability's separate coverage_pct floor just because
      -- that table happens to also list Candidates. inventories is
      -- materialized for exactly owned ∪ (num-parts-floor-cleared)
      -- Candidates, which is Similarity's actual intended scope.
      SELECT set_num FROM inventories
    ) scope
    JOIN sets ON sets.set_num = scope.set_num
    LEFT JOIN similarity_topk ON similarity_topk.set_num = scope.set_num
    LEFT JOIN sets AS other ON other.set_num = similarity_topk.other_set_num
    ORDER BY sets.name ASC, similarity_topk.rank ASC
  `);

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = '<li class="empty">No Sets in the current universe scope.</li>';
    return;
  }

  // Grouped client-side: each anchor Set's row groups its (already
  // rank-ordered) top-10 matches from similarity_topk, rather than one
  // matches row per anchor/match pair.
  const bySetNum = new Map();
  for (const [setNum, name, , otherSetNum, otherName, score] of result[0].values) {
    if (!bySetNum.has(setNum)) {
      bySetNum.set(setNum, { name, matches: [] });
    }
    if (otherSetNum !== null) {
      bySetNum.get(setNum).matches.push({ otherSetNum, otherName, score });
    }
  }

  for (const [, { name, matches }] of bySetNum) {
    const item = document.createElement("li");
    item.className = "similarity-set";
    const matchesMarkup = matches.length
      ? matches
          .map(
            (m) => `
              <li>
                <a href="box.html?set_num=${encodeURIComponent(m.otherSetNum)}">${m.otherName}</a>
                <span class="similarity-score">${m.score.toFixed(1)}%</span>
              </li>
            `
          )
          .join("")
      : '<li class="empty">No similar Sets yet.</li>';
    item.innerHTML = `
      <span class="box-name">${name}</span>
      <ol class="similarity-matches">${matchesMarkup}</ol>
    `;
    list.appendChild(item);
  }
}

loadDatabase()
  .then(renderSimilarity)
  .catch((error) => {
    document.getElementById("similarity-list").innerHTML =
      '<li class="error">Could not load the catalog database.</li>';
    console.error(error);
  });
