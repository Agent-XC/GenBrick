function renderFigurines(db) {
  const list = document.getElementById("figurines");
  const result = db.exec(`
    SELECT minifigs.name, minifigs.num_parts, owned_minifigs.quantity
    FROM owned_minifigs
    JOIN minifigs ON minifigs.fig_num = owned_minifigs.fig_num
    ORDER BY minifigs.name
  `);

  list.innerHTML = "";

  if (result.length === 0) {
    list.innerHTML = '<li class="empty">No figurines yet — own some Boxes to build a collection.</li>';
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

loadDatabase()
  .then(renderFigurines)
  .catch((error) => {
    document.getElementById("figurines").innerHTML =
      '<li class="error">Could not load the catalog database.</li>';
    console.error(error);
  });
