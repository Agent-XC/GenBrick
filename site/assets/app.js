function renderOwnedBoxes(db) {
  const list = document.getElementById("owned-boxes");
  const result = db.exec(`
    SELECT sets.set_num, sets.name, sets.year, sets.official_url, sets.official_url_status, set_renders.image_path
    FROM owned_boxes
    JOIN sets ON sets.set_num = owned_boxes.set_num
    LEFT JOIN set_renders ON set_renders.set_num = owned_boxes.set_num
    ORDER BY owned_boxes.date_acquired DESC
  `);

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = '<li class="empty">No boxes yet — add some to data/owned_sets.txt.</li>';
    return;
  }

  for (const [setNum, name, year, officialUrl, officialUrlStatus, imagePath] of result[0].values) {
    const item = document.createElement("li");
    item.className = "box";
    item.innerHTML = `
      ${boxPhotoMarkup(imagePath, name)}
      <a class="box-name" href="box.html?set_num=${encodeURIComponent(setNum)}">${name}</a>
      <span class="box-year">${year}</span>
      ${officialLinkMarkup(officialUrl, officialUrlStatus)}
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
