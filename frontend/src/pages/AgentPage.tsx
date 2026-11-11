import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, clearToken, createListing, deleteListing, myListings } from "../api";
import type { Listing } from "../types";

const money = new Intl.NumberFormat("fa-IR");

function field(value: number | null, suffix: string) {
  if (value === null) return "نامشخص";
  return `${money.format(value)} ${suffix}`;
}

export function AgentPage() {
  const navigate = useNavigate();
  const name = localStorage.getItem("amlak_name") || "مشاور";
  const [url, setUrl] = useState("");
  const [items, setItems] = useState<Listing[]>([]);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [openIds, setOpenIds] = useState<number[]>([]);

  function toggle(id: number) {
    setOpenIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function load() {
    const rows = await myListings();
    setItems(rows);
  }

  useEffect(() => {
    load().catch((err: unknown) => {
      setError(err instanceof ApiError ? err.message : "فهرست آگهی‌ها خوانده نشد.");
    });
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setWarnings([]);
    try {
      const created = await createListing(url.trim());
      setWarnings(created.warnings);
      setUrl("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت آگهی انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setError("");
    try {
      await deleteListing(id);
      setPendingId(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "حذف انجام نشد.");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <header className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-moss">پنل مشاور</p>
          <h1 className="text-2xl font-semibold">{name}</h1>
        </div>
        <button
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm"
          onClick={() => {
            clearToken();
            localStorage.removeItem("amlak_name");
            navigate("/");
          }}
        >
          خروج
        </button>
      </header>

      <form onSubmit={onSubmit} className="mt-8 rounded-3xl border border-line bg-paper p-5">
        <label className="block text-sm font-medium">
          لینک آگهی دیوار
          <input
            className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3 outline-none focus:border-pine"
            placeholder="https://divar.ir/v/..."
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="mt-4 rounded-2xl bg-pine px-5 py-3 text-sm text-white disabled:opacity-60"
        >
          {busy ? "در حال خواندن دیوار..." : "ثبت آگهی"}
        </button>
        {error && <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm leading-7 text-danger">{error}</p>}
        {warnings.length > 0 && (
          <ul className="mt-4 space-y-2 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-7 text-copper">
            {warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </form>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">آگهی‌های من</h2>
        {items.length === 0 ? (
          <p className="mt-4 rounded-3xl border border-dashed border-line bg-paper px-5 py-8 text-sm text-ink/60">
            هنوز آگهی‌ای ثبت نشده است.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {items.map((item) => {
              const open = openIds.includes(item.id);
              return (
                <article key={item.id} className="overflow-hidden rounded-3xl border border-line bg-paper">
                  <button
                    type="button"
                    className="flex w-full items-center gap-3 px-5 py-4 text-right"
                    aria-expanded={open}
                    onClick={() => toggle(item.id)}
                  >
                    <h3 className="min-w-0 flex-1 font-semibold leading-7">{item.title}</h3>
                    <svg
                      viewBox="0 0 20 20"
                      aria-hidden="true"
                      className={`h-5 w-5 shrink-0 text-ink/50 transition-transform ${open ? "rotate-180" : ""}`}
                    >
                      <path
                        d="M5 7.5 10 12.5 15 7.5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                  {open && (
                    <div className="border-t border-line px-5 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm text-ink/60">{item.created_at_jalali}</p>
                        <span className="rounded-full bg-sand px-3 py-1 text-sm">کد {item.unique_code}</span>
                      </div>
                      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                        <div className="rounded-2xl bg-sand px-3 py-2">متراژ: {field(item.area, "متر")}</div>
                        <div className="rounded-2xl bg-sand px-3 py-2">
                          قیمت: {item.price === null ? "نامشخص" : `${money.format(item.price)} تومان`}
                        </div>
                        <div className="rounded-2xl bg-sand px-3 py-2">خواب: {item.bedrooms ?? "نامشخص"}</div>
                      </dl>
                      <pre className="mt-4 whitespace-pre-wrap rounded-2xl bg-sand/70 px-4 py-3 text-sm leading-7">
                        {item.structured_text}
                      </pre>
                      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
                        <a className="text-pine underline" href={item.divar_url} target="_blank" rel="noreferrer">
                          لینک دیوار
                        </a>
                        <span className="text-ink/50">{item.image_count} عکس</span>
                        {!item.searchable && <span className="text-danger">خارج از جستجوی ربات</span>}
                        {pendingId === item.id ? (
                          <>
                            <button className="text-danger" onClick={() => remove(item.id)}>
                              تأیید حذف
                            </button>
                            <button onClick={() => setPendingId(null)}>انصراف</button>
                          </>
                        ) : (
                          <button className="text-danger" onClick={() => setPendingId(item.id)}>
                            حذف
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
