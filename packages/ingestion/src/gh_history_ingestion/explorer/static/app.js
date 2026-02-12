const state = {
  db: null,
  table: null,
  page: 1,
  pageSize: 100,
  sortCol: "",
  sortDir: "asc",
  filter: "",
};

const qs = (id) => document.getElementById(id);

function showError(message) {
  const box = qs("errorBox");
  box.textContent = message;
  box.classList.remove("hidden");
}

function clearError() {
  qs("errorBox").classList.add("hidden");
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

async function loadDatabases() {
  clearError();
  const dbList = qs("dbList");
  dbList.innerHTML = "";
  try {
    const data = await api("/api/databases");
    qs("dbRoot").textContent = data.root || "";
    if (!data.items.length) {
      dbList.innerHTML = '<li class="muted">No sqlite files found</li>';
      return;
    }

    const groups = new Map();
    for (const item of data.items) {
      const key = `${item.owner}/${item.repo}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }

    for (const [group, items] of groups.entries()) {
      const header = document.createElement("li");
      header.textContent = group;
      header.className = "muted";
      dbList.appendChild(header);

      for (const item of items) {
        const li = document.createElement("li");
        li.textContent = `↳ ${item.file}`;
        li.title = item.relative_path;
        li.dataset.db = item.id;
        li.onclick = () => selectDb(item.id, li, item.relative_path);
        dbList.appendChild(li);
      }
    }
  } catch (err) {
    showError(err.message);
  }
}

async function selectDb(db, li, label) {
  document.querySelectorAll("#dbList li").forEach((el) => el.classList.remove("active"));
  li.classList.add("active");

  state.db = db;
  state.table = null;
  state.page = 1;
  qs("selectedDb").textContent = label;
  qs("tableList").innerHTML = "";
  qs("schemaTable").innerHTML = "";
  qs("rowsTable").innerHTML = "";
  qs("sqlTable").innerHTML = "";

  try {
    const data = await api(`/api/tables?db=${encodeURIComponent(db)}`);
    const list = qs("tableList");
    list.innerHTML = "";
    if (!data.items.length) {
      list.innerHTML = '<li class="muted">No tables found</li>';
      return;
    }

    for (const item of data.items) {
      const rowCount = item.row_count == null ? "count unavailable" : item.row_count;
      const liTable = document.createElement("li");
      liTable.textContent = `${item.table} (${rowCount})`;
      liTable.onclick = () => selectTable(item.table, liTable);
      list.appendChild(liTable);
    }
  } catch (err) {
    showError(err.message);
  }
}

async function selectTable(table, li) {
  document.querySelectorAll("#tableList li").forEach((el) => el.classList.remove("active"));
  li.classList.add("active");

  state.table = table;
  state.page = 1;
  state.sortCol = "";
  state.filter = "";
  qs("filterInput").value = "";

  await loadSchema();
  await loadRows();
}

function renderTable(tableId, columns, rows) {
  const table = qs(tableId);
  table.innerHTML = "";
  if (!columns.length) return;

  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col;
    htr.appendChild(th);
  }
  thead.appendChild(htr);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const col of columns) {
      const td = document.createElement("td");
      const value = row[col];
      td.textContent = value == null ? "" : String(value);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

async function loadSchema() {
  if (!state.db || !state.table) return;
  try {
    const data = await api(`/api/schema?db=${encodeURIComponent(state.db)}&table=${encodeURIComponent(state.table)}`);
    const rows = data.columns.map((c) => ({
      name: c.name,
      type: c.type,
      notnull: c.notnull,
      pk: c.pk,
      default: c.default,
    }));
    renderTable("schemaTable", ["name", "type", "notnull", "pk", "default"], rows);

    const sortCol = qs("sortCol");
    sortCol.innerHTML = '<option value="">(none)</option>';
    for (const c of data.columns) {
      const option = document.createElement("option");
      option.value = c.name;
      option.textContent = c.name;
      sortCol.appendChild(option);
    }
  } catch (err) {
    showError(err.message);
  }
}

async function loadRows() {
  if (!state.db || !state.table) return;
  try {
    const params = new URLSearchParams({
      db: state.db,
      table: state.table,
      page: String(state.page),
      page_size: String(state.pageSize),
      sort_dir: state.sortDir,
      filter: state.filter,
    });
    if (state.sortCol) params.set("sort_col", state.sortCol);

    const data = await api(`/api/rows?${params.toString()}`);
    renderTable("rowsTable", data.columns, data.rows);
    qs("pageInfo").textContent = `Page ${data.page}/${data.total_pages}`;
    qs("rowsMeta").textContent = `${data.total_rows} rows total`;
  } catch (err) {
    showError(err.message);
  }
}

async function runSql() {
  if (!state.db) {
    showError("Select a database first");
    return;
  }
  clearError();
  try {
    const data = await api("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        db: state.db,
        sql: qs("sqlInput").value,
        row_limit: Number(qs("sqlLimit").value || 200),
      }),
    });
    renderTable("sqlTable", data.columns, data.rows);
    qs("sqlMeta").textContent = `${data.returned_rows} rows${data.truncated ? " (truncated)" : ""}`;
  } catch (err) {
    showError(err.message);
  }
}

function setupEvents() {
  qs("refreshDbs").onclick = loadDatabases;
  qs("applyRows").onclick = () => {
    state.filter = qs("filterInput").value.trim();
    state.sortCol = qs("sortCol").value;
    state.sortDir = qs("sortDir").value;
    state.page = 1;
    loadRows();
  };
  qs("prevPage").onclick = () => {
    if (state.page > 1) {
      state.page -= 1;
      loadRows();
    }
  };
  qs("nextPage").onclick = () => {
    state.page += 1;
    loadRows();
  };
  qs("runSql").onclick = runSql;
}

setupEvents();
loadDatabases();
