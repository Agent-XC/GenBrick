async function loadDatabase() {
  const SQL = await initSqlJs({ locateFile: (file) => `vendor/sql.js/${file}` });
  const response = await fetch("data/lego.sqlite");
  const buffer = await response.arrayBuffer();
  return new SQL.Database(new Uint8Array(buffer));
}

// image_path is null for image_source 'none' (no user photo yet, and later
// render stages aren't built) — shows an explicit placeholder rather than an
// <img> with a missing/broken src.
function boxPhotoMarkup(imagePath, altName, className = "box-photo") {
  if (imagePath) {
    return `<img class="${className}" src="${imagePath}" alt="${altName}" />`;
  }
  return `<span class="${className}-placeholder">No photo yet</span>`;
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
