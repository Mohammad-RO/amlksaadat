import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, clearToken, createAgent, listAgents, loadReport, systemHealth, updateAgent } from "../api";
import type { Agent, Report } from "../types";

const emptyEdit = { id: 0, name: "", phone: "" };

export function AdminPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"agents" | "reports">("agents");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [edit, setEdit] = useState(emptyEdit);
  const [report, setReport] = useState<Report | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [archiveReady, setArchiveReady] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setAgents(await listAgents());
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(err instanceof ApiError ? err.message : "فهرست مشاوران خوانده نشد."));
    systemHealth()
      .then((health) => setArchiveReady(health.archive_configured))
      .catch(() => setArchiveReady(false));
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createAgent(name.trim(), phone.trim());
      setName("");
      setPhone("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت مشاور انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await updateAgent(edit.id, { name: edit.name.trim(), phone: edit.phone.trim() });
      setEdit(emptyEdit);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ویرایش انجام نشد.");
    }
  }

  async function toggle(agent: Agent) {
    setError("");
    try {
      await updateAgent(agent.id, { is_active: !agent.is_active });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تغییر وضعیت انجام نشد.");
    }
  }

  async function onReport(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      setReport(await loadReport(dateFrom.trim(), dateTo.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "گزارش خوانده نشد.");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <header className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-moss">محیط ادمین</p>
          <h1 className="text-2xl font-semibold">مشاوران و گزارش فایل‌ها</h1>
        </div>
        <button
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm"
          onClick={() => {
            clearToken();
            navigate("/");
          }}
        >
          خروج
        </button>
      </header>

      {!archiveReady && (
        <p className="mt-6 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-7 text-copper">
          کانال آرشیو تلگرام هنوز تنظیم نشده است. تا وقتی شناسه کانال خصوصی در env نباشد، عکس‌ها فقط با آدرس دیوار نگه داشته می‌شوند.
        </p>
      )}

      <div className="mt-6 grid grid-cols-2 rounded-full bg-paper p-1 text-sm sm:max-w-xs">
        <button className={`rounded-full px-3 py-2 ${tab === "agents" ? "bg-pine text-white" : ""}`} onClick={() => setTab("agents")}>
          مشاوران
        </button>
        <button className={`rounded-full px-3 py-2 ${tab === "reports" ? "bg-pine text-white" : ""}`} onClick={() => setTab("reports")}>
          گزارش
        </button>
      </div>
      {error && <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm leading-7 text-danger">{error}</p>}

      {tab === "agents" ? (
        <>
          <form onSubmit={onCreate} className="mt-6 grid gap-3 rounded-3xl border border-line bg-paper p-5 sm:grid-cols-[1fr_1fr_auto]">
            <input
              className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine"
              placeholder="نام مشاور"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
            <input
              className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine"
              placeholder="شماره موبایل"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              required
            />
            <button disabled={busy} className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60">
              افزودن
            </button>
          </form>

          <div className="mt-5 overflow-hidden rounded-3xl border border-line bg-paper">
            <table className="w-full text-sm">
              <thead className="bg-sand text-ink/70">
                <tr>
                  <th className="px-4 py-3 text-right font-medium">نام</th>
                  <th className="px-4 py-3 text-right font-medium">شماره</th>
                  <th className="px-4 py-3 text-right font-medium">فایل</th>
                  <th className="px-4 py-3 text-right font-medium">وضعیت</th>
                  <th className="px-4 py-3 text-right font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.id} className="border-t border-line">
                    <td className="px-4 py-3">{agent.name}</td>
                    <td className="px-4 py-3" dir="ltr">{agent.phone}</td>
                    <td className="px-4 py-3">{agent.listings_count}</td>
                    <td className="px-4 py-3">{agent.is_active ? "فعال" : "غیرفعال"}</td>
                    <td className="px-4 py-3">
                      <button className="text-pine" onClick={() => setEdit({ id: agent.id, name: agent.name, phone: agent.phone })}>
                        ویرایش
                      </button>
                      <button className="mr-3 text-copper" onClick={() => toggle(agent)}>
                        {agent.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}
                      </button>
                    </td>
                  </tr>
                ))}
                {agents.length === 0 && (
                  <tr>
                    <td className="px-4 py-8 text-ink/50" colSpan={5}>
                      هنوز مشاوری ثبت نشده است.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {edit.id > 0 && (
            <form onSubmit={saveEdit} className="mt-4 grid gap-3 rounded-3xl border border-line bg-paper p-5 sm:grid-cols-[1fr_1fr_auto_auto]">
              <input className="rounded-2xl border border-line px-4 py-3" value={edit.name} onChange={(event) => setEdit({ ...edit, name: event.target.value })} required />
              <input className="rounded-2xl border border-line px-4 py-3" value={edit.phone} onChange={(event) => setEdit({ ...edit, phone: event.target.value })} required />
              <button className="rounded-2xl bg-pine px-4 py-3 text-white">ذخیره</button>
              <button type="button" className="rounded-2xl border border-line px-4 py-3" onClick={() => setEdit(emptyEdit)}>
                بستن
              </button>
            </form>
          )}
        </>
      ) : (
        <section className="mt-6">
          <form onSubmit={onReport} className="grid gap-3 rounded-3xl border border-line bg-paper p-5 sm:grid-cols-[1fr_1fr_auto]">
            <input
              className="rounded-2xl border border-line px-4 py-3"
              placeholder="از تاریخ، مثلاً 1404/08/01"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
            <input
              className="rounded-2xl border border-line px-4 py-3"
              placeholder="تا تاریخ، مثلاً 1404/08/30"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
            <button className="rounded-2xl bg-pine px-5 py-3 text-white">نمایش</button>
          </form>
          <p className="mt-3 text-sm text-ink/60">اگر تاریخ خالی بماند، همه آگهی‌های ثبت‌شده شمرده می‌شود. تاریخ شمسی هم پذیرفته می‌شود.</p>
          {report && (
            <div className="mt-4 overflow-hidden rounded-3xl border border-line bg-paper">
              <table className="w-full text-sm">
                <thead className="bg-sand text-ink/70">
                  <tr>
                    <th className="px-4 py-3 text-right font-medium">مشاور</th>
                    <th className="px-4 py-3 text-right font-medium">شماره</th>
                    <th className="px-4 py-3 text-right font-medium">تعداد فایل</th>
                  </tr>
                </thead>
                <tbody>
                  {report.items.map((item) => (
                    <tr key={item.agent_id} className="border-t border-line">
                      <td className="px-4 py-3">{item.name}</td>
                      <td className="px-4 py-3" dir="ltr">{item.phone}</td>
                      <td className="px-4 py-3">{item.listings_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
