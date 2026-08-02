function renderFigurines(db) {
  const list = document.getElementById("figurines");
  // fig_num is selected (not just joined on) so this row carries the same
  // identifier its thumbnail render is keyed by (issue #34), mirroring
  // box.js's renderParts selecting part_num/color_id alongside the columns
  // it displays.
  const result = db.exec(`
    SELECT owned_minifigs.fig_num, minifigs.name, minifigs.num_parts, owned_minifigs.quantity,
           minifig_renders.image_path
    FROM owned_minifigs
    JOIN minifigs ON minifigs.fig_num = owned_minifigs.fig_num
    LEFT JOIN minifig_renders ON minifig_renders.fig_num = owned_minifigs.fig_num
    ORDER BY minifigs.name
  `);

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = '<li class="empty">No figurines yet — own some Boxes to build a collection.</li>';
    return;
  }

  for (const [, figName, numParts, quantity, imagePath] of result[0].values) {
    const item = document.createElement("li");
    item.className = "minifig";
    item.innerHTML = `
      ${minifigThumbnailMarkup(imagePath, figName)}
      <span class="minifig-name">${figName}</span>
      <span class="minifig-quantity">&times;${quantity}</span>
    `;
    list.appendChild(item);
  }
}

loadDatabase()
  .then(renderFigurines)
  .catch((error) => {
    document.getElementById("figurines").innerHTML =
      '<li class="error">Could not load the catalog database.</li>';
    console.error(error);
  });
