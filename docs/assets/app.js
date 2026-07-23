async function loadDatabase() {
  const SQL = await initSqlJs({ locateFile: (file) => `vendor/sql.js/${file}` });
  const response = await fetch("data/lego.sqlite");
  const buffer = await response.arrayBuffer();
  return new SQL.Database(new Uint8Array(buffer));
}

function renderOwnedBoxes(db) {
  const list = document.getElementById("owned-boxes");
  const result = db.exec(`
    SELECT sets.set_num, sets.name, sets.year, sets.official_url
    FROM owned_boxes
    JOIN sets ON sets.set_num = owned_boxes.set_num
    ORDER BY owned_boxes.date_acquired DESC
  `);

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = '<li class="empty">No boxes yet — add some to data/owned_sets.txt.</li>';
    return;
  }

  for (const [setNum, name, year, officialUrl] of result[0].values) {
    const item = document.createElement("li");
    item.className = "box";
    item.innerHTML = `
      <span class="box-name">${name}</span>
      <span class="box-year">${year}</span>
      <a class="box-link" href="${officialUrl}" target="_blank" rel="noopener">Official page</a>
    `;
    list.appendChild(item);
  }
}

loadDatabase()
  .then(renderOwnedBoxes)
  .catch((error) => {
    document.getElementById("owned-boxes").innerHTML =
      '<li class="error">Could not load the catalog database.</li>';
    console.error(error);
  });
