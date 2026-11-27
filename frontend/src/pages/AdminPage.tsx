import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, clearToken, createAgent, listAgents, systemHealth, updateAgent } from "../api";
import type { Agent } from "../types";
import { HouseIcon, LogoMark, LogoutIcon, UserIcon } from "../icons";
import { DivarColleaguesSection } from "./DivarColleaguesSection";

const emptyEdit = { id: 0, name: "", phone: "" };

export function AdminPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"agents" | "divar">("divar");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [edit, setEdit] = useState(emptyEdit);
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

  return (
    <main className="app-scene relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <svg className="scene-house absolute -right-6 top-16 h-40 w-52" viewBox="0 0 200 150" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 78 100 22l82 56v58H18V78z" />
          <path d="M78 136V96h28v40" />
          <path d="M42 92h22v18H42zM136 92h22v18h-22z" />
        </svg>
        <svg className="scene-house absolute bottom-8 left-6 h-36 w-48" viewBox="0 0 200 150" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M24 84 100 28l76 56v52H24V84z" />
          <path d="M86 136V100h24v36" />
        </svg>
      </div>
      <div className="relative mx-auto min-h-screen max-w-5xl px-4 py-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <LogoMark className="h-14 w-14 shrink-0" />
          <div>
            <h1 className="brand-word text-2xl font-medium text-[#1f8a45]">IranHouseVIP</h1>
            <p className="mt-1 text-sm text-ink/55">مدیریت هوشمند املاک، سریع‌تر، آسان‌تر</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-sm text-ink/75">
            <UserIcon className="h-5 w-5 text-[#1f8a45]" />
            محیط ادمین
          </span>
          <button
            className="flex items-center gap-2 rounded-full border border-[#d5e6d6] bg-white px-4 py-2 text-sm text-[#1f8a45] shadow-sm"
            onClick={() => {
              clearToken();
              navigate("/");
            }}
          >
            <LogoutIcon className="h-4 w-4" />
            خروج
          </button>
        </div>
      </header>

      {!archiveReady && (
        <p className="mt-6 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-7 text-copper">
          کانال آرشیو تلگرام هنوز تنظیم نشده است. تا وقتی شناسه کانال خصوصی در env نباشد، عکس‌ها فقط با آدرس دیوار نگه داشته می‌شوند.
        </p>
      )}

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          className={`flex items-center gap-2 rounded-full px-5 py-2.5 text-sm ${tab === "divar" ? "bg-[#1f8a45] text-white shadow-sm" : "border border-[#d5e6d6] bg-white text-[#1f8a45]"}`}
          onClick={() => setTab("divar")}
        >
          <HouseIcon className="h-4 w-4" />
          همکاران پنل دیوار
        </button>
        <button
          className={`flex items-center gap-2 rounded-full px-5 py-2.5 text-sm ${tab === "agents" ? "bg-[#1f8a45] text-white shadow-sm" : "border border-[#d5e6d6] bg-white text-[#1f8a45]"}`}
          onClick={() => setTab("agents")}
        >
          <UserIcon className="h-4 w-4" />
          مشاوران خارج از پنل دیوار
        </button>
      </div>
      {error && <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm leading-7 text-danger">{error}</p>}

      {tab === "divar" ? (
        <DivarColleaguesSection />
      ) : (
        <>
          <form onSubmit={onCreate} className="mt-6 grid gap-3 rounded-[28px] bg-white p-5 shadow-[0_10px_30px_rgba(40,90,50,0.06)] sm:grid-cols-[1fr_1fr_auto]">
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
            <button disabled={busy} className="rounded-full bg-[#1f8a45] px-5 py-3 text-white disabled:opacity-60">
              افزودن
            </button>
          </form>

          <div className="mt-5 overflow-hidden rounded-[28px] bg-white shadow-[0_10px_30px_rgba(40,90,50,0.06)]">
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
            <form onSubmit={saveEdit} className="mt-4 grid gap-3 rounded-[28px] bg-white p-5 shadow-[0_10px_30px_rgba(40,90,50,0.06)] sm:grid-cols-[1fr_1fr_auto_auto]">
              <input className="rounded-2xl border border-line px-4 py-3" value={edit.name} onChange={(event) => setEdit({ ...edit, name: event.target.value })} required />
              <input className="rounded-2xl border border-line px-4 py-3" value={edit.phone} onChange={(event) => setEdit({ ...edit, phone: event.target.value })} required />
              <button className="rounded-full bg-[#1f8a45] px-4 py-3 text-white">ذخیره</button>
              <button type="button" className="rounded-2xl border border-line px-4 py-3" onClick={() => setEdit(emptyEdit)}>
                بستن
              </button>
            </form>
          )}
        </>
      )}
      </div>
    </main>
  );
}
