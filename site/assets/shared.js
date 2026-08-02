async function loadDatabase() {
  const SQL = await initSqlJs({ locateFile: (file) => `vendor/sql.js/${file}` });
  const response = await fetch("data/lego.sqlite");
  const buffer = await response.arrayBuffer();
  return new SQL.Database(new Uint8Array(buffer));
}

function getSetNumFromUrl() {
  return new URLSearchParams(window.location.search).get("set_num");
}

// Shared by box.html and candidate.html — a Set's minifigs don't depend on
// ownership (inventory_minifigs is materialized the same way for owned
// Boxes and Candidates alike), so the query and rendering are identical;
// only the target list element and its empty-state wording differ.
function renderMinifigs(db, setNum, listElementId, emptyMessage) {
  const list = document.getElementById(listElementId);
  const result = db.exec(
    `
    SELECT minifigs.name, minifigs.num_parts, inventory_minifigs.quantity
    FROM inventory_minifigs
    JOIN inventories ON inventories.id = inventory_minifigs.inventory_id
    JOIN minifigs ON minifigs.fig_num = inventory_minifigs.fig_num
    WHERE inventories.set_num = ?
    ORDER BY minifigs.name
  `,
    [setNum]
  );

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = `<li class="empty">${emptyMessage}</li>`;
    return;
  }

  for (const [figName, numParts, quantity] of result[0].values) {
    const item = document.createElement("li");
    item.className = "minifig";
    item.innerHTML = `
      <span class="minifig-name">${figName}</span>
      <span class="minifig-quantity">&times;${quantity}</span>
    `;
    list.appendChild(item);
  }
}

// Deterministic per-Set color so placeholders are visually distinct rather
// than one flat gray block repeated down the list — same input always maps
// to the same hue, with no server-side state needed.
function placeholderColor(seed) {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return `hsl(${hash % 360}, 55%, 80%)`;
}

// image_path is null for image_source 'none' (no user photo yet, and later
// render stages aren't built) — shows a colored-box placeholder rather than
// an <img> with a missing/broken src.
function boxPhotoMarkup(imagePath, altName, className = "box-photo") {
  if (imagePath) {
    return `<img class="${className}" src="${imagePath}" alt="${altName}" />`;
  }
  const background = placeholderColor(altName);
  return `<span class="${className}-placeholder" style="background-color: ${background}">No photo yet</span>`;
}

// Same null-image fallback as boxPhotoMarkup, sized for a parts-table cell
// instead of a list row or detail-page hero image — a (part_num, color_id)
// with no crosswalk match or a failed render has no part_renders row at all
// (issue #33), so imagePath is simply undefined/null here, same shape as a
// Box with no photo yet.
function partThumbnailMarkup(imagePath, partName) {
  return boxPhotoMarkup(imagePath, partName, "part-thumbnail");
}

// Same null-image fallback as boxPhotoMarkup/partThumbnailMarkup, sized for
// the Figurines list row. A minifig with no own inventory materialized or a
// crosswalk miss has no minifig_renders row at all (issue #34), so imagePath
// is simply undefined/null here, same shape as those two.
function minifigThumbnailMarkup(imagePath, figName) {
  return boxPhotoMarkup(imagePath, figName, "minifig-thumbnail");
}

// Only the procedural render's partial coverage is worth surfacing — a
// user_photo is always 100% (nothing was procedurally resolved/omitted) and
// 'none' has no image to caption at all.
function renderCaptionMarkup(imageSource, renderCoveragePct) {
  if (imageSource !== "ldraw_procedural") {
    return "";
  }
  return `<p class="render-caption">Procedural LDraw render — ${renderCoveragePct.toFixed(1)}% of parts resolved</p>`;
}

// Shared across every page that lists Boxes (Home, Discover, Similarity,
// Themes) — a cheap, always-available proxy for the official link (issue
// #15): a user can hand-construct https://www.lego.com/fr-fr/product/<set_num>
// from it even when official_url_status hasn't resolved to "ok" yet.
function setNumMarkup(setNum) {
  return `<span class="box-set-num">${setNum}</span>`;
}

// Shared across every Box-listing page (Home, Discover, Similarity, Themes)
// — lets a viewer eyeball whether a match is a small or large set without
// opening it (issue #16), the same way setNumMarkup above does for set_num.
function numPartsMarkup(numParts) {
  return `<span class="box-num-parts">${numParts} parts</span>`;
}

// Never substitutes a fan-site link for LEGO's own. "retired" (a confirmed
// 404) and "unchecked" (the checker hasn't confirmed either way) are kept
// as distinct claims rather than folded into one "Retired" message.
function officialLinkMarkup(officialUrl, officialUrlStatus) {
  if (officialUrlStatus === "ok") {
    return `<a class="box-link" href="${officialUrl}" target="_blank" rel="noopener">Official page</a>`;
  }
  if (officialUrlStatus === "retired") {
    return '<span class="box-link box-link-retired">Retired — no current official LEGO.com page</span>';
  }
  return '<span class="box-link box-link-unchecked">Official link not yet verified</span>';
}
