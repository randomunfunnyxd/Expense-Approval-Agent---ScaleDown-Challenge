async function fetchJSON(url) {
  const res = await fetch(url);
  return res.json();
}

function renderDecision(payload) {
  const el = document.getElementById("decision");
  if (!payload || !payload.status) {
    el.textContent = "";
    return;
  }
  const reasonText = payload.reasons && payload.reasons.length
    ? `Reasons: ${payload.reasons.join(" | ")}`
    : "No blocking issues found.";
  const flagText = payload.flags && payload.flags.length
    ? `Flags: ${payload.flags.join(" | ")}`
    : "";
  el.innerHTML = `<strong>${payload.status.toUpperCase()}</strong><br>${reasonText}<br>${flagText}`;
}

function statusClass(status) {
  if (status === "approved") return "status-approved";
  if (status === "denied") return "status-denied";
  return "status-consider";
}

async function refreshDashboard() {
  const summary = await fetchJSON("/api/summary");
  const expenses = await fetchJSON("/api/expenses");

  renderBudgetPanel(lastDecision);
  renderStatusChart(summary.by_status || {});
  renderCategoryChart(summary.by_category || {});
  renderMonthlyChart(summary.monthly_totals || {});
  renderExpenseTable(expenses.items || []);
}

function renderBudgetPanel(decision) {
  const el = document.getElementById("budget");
  if (!decision) {
    el.innerHTML = "Submit an expense to see budget updates.";
    return;
  }
  el.innerHTML = `
    <div><strong>Monthly Spend:</strong> $${decision.monthly_spend.toFixed(2)}</div>
    <div><strong>Monthly Budget:</strong> $${decision.monthly_budget.toFixed(2)}</div>
    <div><strong>Remaining:</strong> $${decision.remaining_budget.toFixed(2)}</div>
  `;
}

let statusChart;
function renderStatusChart(data) {
  const ctx = document.getElementById("status-chart");
  const labels = Object.keys(data);
  const values = Object.values(data);
  if (statusChart) statusChart.destroy();
  statusChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: ["#1e7b34", "#b3261e", "#a06600"],
      }],
    },
    options: { responsive: true }
  });
}

let categoryChart;
function renderCategoryChart(data) {
  const ctx = document.getElementById("category-chart");
  const labels = Object.keys(data);
  const values = Object.values(data);
  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: "#ff7a59",
      }],
    },
    options: { responsive: true }
  });
}

let monthlyChart;
function renderMonthlyChart(data) {
  const ctx = document.getElementById("monthly-chart");
  const labels = Object.keys(data).sort();
  const values = labels.map((l) => data[l]);
  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: "#1c1a17",
        backgroundColor: "rgba(255, 122, 89, 0.2)",
        fill: true,
        tension: 0.3,
      }],
    },
    options: { responsive: true }
  });
}

function renderExpenseTable(items) {
  const el = document.getElementById("expenses-table");
  const header = `
    <div class="table-row table-header">
      <div>Merchant</div>
      <div>Category</div>
      <div>Total</div>
      <div>Date</div>
      <div>Status</div>
    </div>
  `;
  const rows = items.slice(0, 8).map((item) => `
    <div class="table-row">
      <div>${item.merchant || "-"}</div>
      <div>${item.category || "-"}</div>
      <div>$${Number(item.total || 0).toFixed(2)}</div>
      <div>${item.date || "-"}</div>
      <div class="${statusClass(item.status)}">${item.status || "-"}</div>
    </div>
  `).join("");
  el.innerHTML = header + rows;
}

let lastDecision = null;
const form = document.getElementById("expense-form");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(form);
  const res = await fetch("/api/submit", {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  lastDecision = data;
  renderDecision(data);
  await refreshDashboard();
  form.reset();
});

refreshDashboard();
