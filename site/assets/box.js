function renderBox(db, setNum) {
  const boxResult = db.exec(
    `
    SELECT sets.name, sets.year, sets.official_url, sets.official_url_status, sets.manual_url,
           set_renders.image_path, set_renders.image_source, set_renders.render_coverage_pct
    FROM owned_boxes
    JOIN sets ON sets.set_num = owned_boxes.set_num
    LEFT JOIN set_renders ON set_renders.set_num = owned_boxes.set_num
    WHERE owned_boxes.set_num = ?
  `,
    [setNum]
  );

  if (boxResult.length === 0) {
    document.getElementById("box-name").textContent = "Box not found";
    document.getElementById("box-meta").textContent = `No owned Box for set_num ${setNum}.`;
    return;
  }

  const [name, year, officialUrl, officialUrlStatus, manualUrl, imagePath, imageSource, renderCoveragePct] =
    boxResult[0].values[0];
  document.getElementById("box-name").textContent = name;
  document.getElementById("box-meta").textContent = `${setNum} · ${year}`;
  document.getElementById("box-photo").innerHTML = boxPhotoMarkup(imagePath, name, "box-detail-photo");
  document.getElementById("box-photo-caption").innerHTML = renderCaptionMarkup(imageSource, renderCoveragePct);
  document.getElementById("box-official-link").innerHTML = officialLinkMarkup(officialUrl, officialUrlStatus);
  document.getElementById("box-manual-link").innerHTML =
    `<a class="box-link" href="${manualUrl}" target="_blank" rel="noopener">Building instructions</a>`;

  renderMinifigs(db, setNum, "box-minifigs", "No minifigs in this Box.");
  renderParts(db, setNum);
}

function renderParts(db, setNum) {
  const tbody = document.querySelector("#box-parts tbody");
  // GROUP BY part_num/color_id/is_spare, not just part_num/color_id: a
  // (part_num, color_id) can have both a spare and a non-spare
  // inventory_parts row (e.g. Bonsai Tree's Frog/Bright Pink) — summing
  // across is_spare would silently fold a spare into the main build
  // quantity, so each is kept as its own row and the spare one is labeled
  // explicitly instead (issue #16).
  const result = db.exec(
    `
    SELECT parts.name, colors.name, colors.rgb, inventory_parts.is_spare, SUM(inventory_parts.quantity) AS quantity
    FROM inventory_parts
    JOIN inventories ON inventories.id = inventory_parts.inventory_id
    JOIN parts ON parts.part_num = inventory_parts.part_num
    JOIN colors ON colors.id = inventory_parts.color_id
    WHERE inventories.set_num = ?
    GROUP BY inventory_parts.part_num, inventory_parts.color_id, inventory_parts.is_spare
    ORDER BY parts.name, colors.name, inventory_parts.is_spare
  `,
    [setNum]
  );

  tbody.innerHTML = "";

  if (result.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="empty">No parts recorded for this Box.</td></tr>';
    return;
  }

  for (const [partName, colorName, colorRgb, isSpare, quantity] of result[0].values) {
    const row = document.createElement("tr");
    const quantityMarkup = isSpare ? `&times;${quantity} spare` : `${quantity}`;
    row.innerHTML = `
      <td>${partName}</td>
      <td><span class="color-swatch" style="background-color: #${colorRgb}"></span>${colorName}</td>
      <td>${quantityMarkup}</td>
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
