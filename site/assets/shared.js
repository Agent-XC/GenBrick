async function loadDatabase() {
  const SQL = await initSqlJs({ locateFile: (file) => `vendor/sql.js/${file}` });
  const response = await fetch("data/lego.sqlite");
  const buffer = await response.arrayBuffer();
  return new SQL.Database(new Uint8Array(buffer));
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
