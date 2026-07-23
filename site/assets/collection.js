function renderCollection(db) {
  const tbody = document.querySelector("#brick-pool tbody");
  const result = db.exec(`
    SELECT parts.name, colors.name, colors.rgb, owned_brick_pool.quantity
    FROM owned_brick_pool
    JOIN parts ON parts.part_num = owned_brick_pool.part_num
    JOIN colors ON colors.id = owned_brick_pool.color_id
    ORDER BY parts.name, colors.name
  `);

  tbody.innerHTML = "";

  if (result.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="empty">No parts yet — own some Boxes to build a pool.</td></tr>';
    return;
  }

  for (const [partName, colorName, colorRgb, quantity] of result[0].values) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${partName}</td>
      <td><span class="color-swatch" style="background-color: #${colorRgb}"></span>${colorName}</td>
      <td>${quantity}</td>
    `;
    tbody.appendChild(row);
  }
}

loadDatabase()
  .then(renderCollection)
  .catch((error) => {
    document.querySelector("#brick-pool tbody").innerHTML =
      '<tr><td colspan="3" class="error">Could not load the catalog database.</td></tr>';
    console.error(error);
  });
