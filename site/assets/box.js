function getSetNumFromUrl() {
  return new URLSearchParams(window.location.search).get("set_num");
}

function renderBox(db, setNum) {
  const boxResult = db.exec(
    `
    SELECT sets.name, sets.year, sets.official_url, sets.official_url_status
    FROM owned_boxes
    JOIN sets ON sets.set_num = owned_boxes.set_num
    WHERE owned_boxes.set_num = ?
  `,
    [setNum]
  );

  if (boxResult.length === 0) {
    document.getElementById("box-name").textContent = "Box not found";
    document.getElementById("box-meta").textContent = `No owned Box for set_num ${setNum}.`;
    return;
  }

  const [name, year, officialUrl, officialUrlStatus] = boxResult[0].values[0];
  document.getElementById("box-name").textContent = name;
  document.getElementById("box-meta").textContent = `${setNum} · ${year}`;
  document.getElementById("box-official-link").innerHTML = officialLinkMarkup(officialUrl, officialUrlStatus);

  renderMinifigs(db, setNum);
  renderParts(db, setNum);
}

function renderMinifigs(db, setNum) {
  const list = document.getElementById("box-minifigs");
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
    list.innerHTML = '<li class="empty">No minifigs in this Box.</li>';
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

function renderParts(db, setNum) {
  const tbody = document.querySelector("#box-parts tbody");
  const result = db.exec(
    `
    SELECT parts.name, colors.name, colors.rgb, inventory_parts.quantity
    FROM inventory_parts
    JOIN inventories ON inventories.id = inventory_parts.inventory_id
    JOIN parts ON parts.part_num = inventory_parts.part_num
    JOIN colors ON colors.id = inventory_parts.color_id
    WHERE inventories.set_num = ?
    ORDER BY parts.name, colors.name
  `,
    [setNum]
  );

  tbody.innerHTML = "";

  if (result.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="empty">No parts recorded for this Box.</td></tr>';
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

const setNum = getSetNumFromUrl();

if (!setNum) {
  document.getElementById("box-name").textContent = "No set_num given";
  document.getElementById("box-meta").textContent = "Link to this page with ?set_num=<set_num>.";
} else {
  loadDatabase()
    .then((db) => renderBox(db, setNum))
    .catch((error) => {
      document.getElementById("box-name").textContent = "Could not load the catalog database.";
      console.error(error);
    });
}
