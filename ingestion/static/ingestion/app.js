const e = React.createElement;

function App() {
  const [data, setData] = React.useState(null);
  const [sourceType, setSourceType] = React.useState("sap");
  const [file, setFile] = React.useState(null);
  const [filter, setFilter] = React.useState("all");
  const [selected, setSelected] = React.useState(null);
  const [message, setMessage] = React.useState("");

  const load = React.useCallback(() => {
    fetch("/api/dashboard/")
      .then((response) => {
        if (!response.ok) throw new Error("Could not load dashboard data");
        return response;
      })
      .then((response) => response.json())
      .then((payload) => {
        setData(payload);
        if (!selected && payload.activities.length) setSelected(payload.activities[0]);
      })
      .catch((error) => setMessage(error.message));
  }, [selected]);

  React.useEffect(() => load(), [load]);

  function upload(event) {
    event.preventDefault();
    if (!file) return;
    const body = new FormData();
    body.append("source_type", sourceType);
    body.append("file", file);
    fetch("/api/upload/", { method: "POST", body })
      .then((response) => response.json())
      .then((payload) => {
        setMessage(payload.message || payload.error);
        setFile(null);
        load();
      })
      .catch(() => setMessage("Upload failed"));
  }

  function review(action) {
    if (!selected) return;
    fetch(`/api/activities/${selected.id}/review/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, actor: "demo analyst" }),
    })
      .then((response) => response.json())
      .then((payload) => {
        if (payload.error) setMessage(payload.error);
        setSelected(payload.error ? selected : payload);
        load();
      })
      .catch(() => setMessage("Review action failed"));
  }

  if (!data) return e("main", { className: "loading" }, "Loading review queue...");
  const activities = data.activities.filter((activity) => filter === "all" || activity.review_status === filter);

  return e("div", { className: "app" },
    e("aside", { className: "sidebar" },
      e("div", { className: "brand" }, e("span", null, "Breathe ESG"), e("strong", null, data.tenant.name)),
      e("form", { className: "upload", onSubmit: upload },
        e("label", null, "Source"),
        e("select", { value: sourceType, onChange: (event) => setSourceType(event.target.value) },
          data.sources.map((source) => e("option", { key: source.value, value: source.value }, source.label))
        ),
        e("label", null, "Upload extract"),
        e("input", { type: "file", onChange: (event) => setFile(event.target.files[0]) }),
        e("button", { type: "submit" }, "Import file")
      ),
      message && e("p", { className: "message" }, message),
      e("div", { className: "batches" },
        e("h2", null, "Recent batches"),
        data.batches.slice(0, 5).map((batch) => e("div", { className: "batch", key: batch.id },
          e("strong", null, batch.filename),
          e("span", null, `${batch.source}: ${batch.accepted_rows} accepted, ${batch.warning_rows} warnings, ${batch.failed_rows} failed`)
        ))
      )
    ),
    e("main", { className: "workspace" },
      e("section", { className: "metrics" },
        metric("Rows", data.totals.rows),
        metric("Pending", data.totals.pending),
        metric("Warnings", data.totals.warnings),
        metric("Failed", data.totals.failed),
        metric("Approved", data.totals.approved),
        metric("tCO2e", (data.totals.co2e_kg / 1000).toFixed(2))
      ),
      e("section", { className: "review" },
        e("div", { className: "queue" },
          e("div", { className: "queueHeader" },
            e("h1", null, "Analyst review"),
            e("select", { value: filter, onChange: (event) => setFilter(event.target.value) },
              ["all", "pending", "approved", "rejected", "locked"].map((value) => e("option", { key: value, value }, value))
            )
          ),
          e("div", { className: "table" },
            activities.map((activity) => e("button", {
              className: selected && selected.id === activity.id ? "row active" : "row",
              key: activity.id,
              onClick: () => setSelected(activity),
            },
              e("span", null, activity.source_reference),
              e("span", null, activity.facility),
              e("span", null, activity.scope),
              e("span", null, `${activity.co2e_kg.toFixed(1)} kg`),
              e("span", { className: activity.suspicious_reasons.length ? "warn" : "ok" }, activity.suspicious_reasons.length ? "Review" : activity.review_status)
            ))
          )
        ),
        selected && e("div", { className: "detail" },
          e("div", { className: "detailTop" },
            e("div", null,
              e("p", { className: "eyebrow" }, selected.source),
              e("h2", null, selected.description || selected.activity_type)
            ),
            e("span", { className: `status ${selected.review_status}` }, selected.review_status)
          ),
          e("dl", null,
            detail("Facility", selected.facility),
            detail("Scope", selected.scope),
            detail("Activity date", selected.activity_date),
            detail("Original quantity", `${selected.quantity} ${selected.unit}`),
            detail("Normalized", `${selected.normalized_quantity} ${selected.normalized_unit}`),
            detail("Estimated emissions", `${selected.co2e_kg.toFixed(2)} kg CO2e`)
          ),
          e("div", { className: "flags" },
            e("h3", null, "Flags"),
            selected.suspicious_reasons.length
              ? selected.suspicious_reasons.map((flag) => e("p", { key: flag }, flag))
              : e("p", null, "No automated flags")
          ),
          e("div", { className: "actions" },
            e("button", { onClick: () => review("approve") }, "Approve"),
            e("button", { onClick: () => review("reject") }, "Reject"),
            e("button", { onClick: () => review("lock") }, "Lock for audit")
          ),
          e("pre", null, JSON.stringify(selected.raw, null, 2))
        )
      )
    )
  );
}

function metric(label, value) {
  return e("div", { className: "metric" }, e("span", null, label), e("strong", null, value));
}

function detail(label, value) {
  return [e("dt", { key: `${label}-dt` }, label), e("dd", { key: `${label}-dd` }, value || "-")];
}

ReactDOM.createRoot(document.getElementById("root")).render(e(App));
