import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  confirmDivarLogin,
  divarColleagues,
  divarSyncStatus,
  saveDivarLink,
  saveDivarPostsLink,
  startDivarLogin,
  startDivarSync,
} from "../api";
import type { DivarColleague, DivarSync } from "../types";

const PLACEHOLDER = "https://divar.ir/my-divar/my-business/wgiqQiGe/agent-management";
const POSTS_PLACEHOLDER = "https://divar.ir/my-divar/my-posts";

export function DivarColleaguesSection() {
  const [url, setUrl] = useState("");
  const [savedUrl, setSavedUrl] = useState("");
  const [postsUrl, setPostsUrl] = useState("");
  const [savedPostsUrl, setSavedPostsUrl] = useState("");
  const [postsEditing, setPostsEditing] = useState(false);
  const [items, setItems] = useState<DivarColleague[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginStep, setLoginStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [editing, setEditing] = useState(false);
  const [listOpen, setListOpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [sync, setSync] = useState<DivarSync | null>(null);
  const pollRef = useRef<number | null>(null);
  const locked = Boolean(savedUrl) && !editing;
  const postsLocked = Boolean(savedPostsUrl) && !postsEditing;

  useEffect(() => {
    divarColleagues()
      .then((state) => {
        setSavedUrl(state.url);
        setUrl(state.url);
        setSavedPostsUrl(state.posts_url);
        setPostsUrl(state.posts_url);
        setItems(state.items);
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "لیست همکاران خوانده نشد."));
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, []);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNote("");
    try {
      const state = await saveDivarLink(url.trim());
      setSavedUrl(state.url);
      setUrl(state.url);
      setItems(state.items);
      setEditing(false);
      setNote("لینک ثبت شد.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت لینک انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function onSavePosts(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNote("");
    try {
      const state = await saveDivarPostsLink(postsUrl.trim());
      setSavedPostsUrl(state.posts_url);
      setPostsUrl(state.posts_url);
      setPostsEditing(false);
      setNote("لینک آگهی‌ها ثبت شد.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت لینک آگهی‌ها انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  function applyState(state: { url: string; posts_url: string; items: DivarColleague[] }) {
    setSavedUrl(state.url);
    setUrl(state.url);
    setSavedPostsUrl(state.posts_url);
    setPostsUrl(state.posts_url);
    setItems(state.items);
  }

  async function watchSync() {
    const status = await divarSyncStatus();
    setSync(status);
    if (status.needs_login) {
      setProgressOpen(false);
      setLoginStep("phone");
      setCode("");
      setLoginOpen(true);
      return;
    }
    if (status.running) {
      pollRef.current = window.setTimeout(() => {
        watchSync().catch((err: unknown) => setError(err instanceof ApiError ? err.message : "وضعیت بروزرسانی خوانده نشد."));
      }, 1000);
      return;
    }
    const state = await divarColleagues();
    applyState(state);
  }

  async function onRefresh() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const status = await startDivarSync();
      setSync(status);
      if (status.needs_login) {
        setLoginStep("phone");
        setCode("");
        setLoginOpen(true);
        return;
      }
      if (!status.running && status.phase === "idle") {
        setError(status.message || "بروزرسانی شروع نشد.");
        return;
      }
      setProgressOpen(true);
      await watchSync();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "بروزرسانی انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function onSendCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await startDivarLogin(phone.trim());
      setLoginStep("code");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ارسال کد انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await confirmDivarLogin(code.trim());
      setLoginOpen(false);
      const status = await startDivarSync();
      setSync(status);
      if (status.needs_login) {
        setLoginOpen(true);
        return;
      }
      setProgressOpen(true);
      await watchSync();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ورود به دیوار انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6">
      <form onSubmit={onSave} className="grid gap-3 rounded-3xl border border-line bg-paper p-5 sm:grid-cols-[1fr_auto]">
        <input
          className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine disabled:bg-sand disabled:text-ink/70"
          dir="ltr"
          placeholder={PLACEHOLDER}
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          readOnly={locked}
          required
        />
        {locked ? (
          <button
            type="button"
            className="rounded-2xl border border-line px-5 py-3"
            onClick={() => {
              setEditing(true);
              setNote("");
            }}
          >
            ویرایش
          </button>
        ) : (
          <button disabled={busy} className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60">
            ثبت
          </button>
        )}
      </form>
      {!locked && (
        <p className="mt-3 text-sm leading-7 text-ink/60">
          لینک صفحهٔ مدیریت همکاران دیوار را ثبت کنید. نمونه: {PLACEHOLDER}
        </p>
      )}

      <form onSubmit={onSavePosts} className="mt-4 grid gap-3 rounded-3xl border border-line bg-paper p-5 sm:grid-cols-[1fr_auto]">
        <input
          className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine disabled:bg-sand disabled:text-ink/70"
          dir="ltr"
          placeholder={POSTS_PLACEHOLDER}
          value={postsUrl}
          onChange={(event) => setPostsUrl(event.target.value)}
          readOnly={postsLocked}
          required
        />
        {postsLocked ? (
          <button
            type="button"
            className="rounded-2xl border border-line px-5 py-3"
            onClick={() => {
              setPostsEditing(true);
              setNote("");
            }}
          >
            ویرایش
          </button>
        ) : (
          <button disabled={busy} className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60">
            ثبت
          </button>
        )}
      </form>
      {!postsLocked && (
        <p className="mt-3 text-sm leading-7 text-ink/60">لینک آگهی‌های من در دیوار را ثبت کنید. فقط آگهی‌های فعال فرستاده می‌شوند.</p>
      )}

      {(savedUrl || savedPostsUrl) && (
        <button
          type="button"
          disabled={busy || Boolean(sync?.running)}
          className="mt-4 rounded-2xl bg-pine px-5 py-3 text-sm text-white disabled:opacity-60"
          onClick={onRefresh}
        >
          بروزرسانی
        </button>
      )}

      {note && <p className="mt-4 rounded-2xl bg-sand px-4 py-3 text-sm leading-7">{note}</p>}
      {error && <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm leading-7 text-danger">{error}</p>}

      <div className="mt-5 overflow-hidden rounded-3xl border border-line bg-paper">
        <button
          type="button"
          className="flex w-full items-center justify-between px-5 py-4 text-right font-medium"
          aria-expanded={listOpen}
          onClick={() => setListOpen((open) => !open)}
        >
          <span>لیست مشاوران</span>
          <span className="text-sm text-ink/50">{listOpen ? "بستن" : "باز کردن"}</span>
        </button>
        {listOpen && (
          <table className="w-full border-t border-line text-sm">
            <thead className="bg-sand text-ink/70">
              <tr>
                <th className="px-4 py-3 text-right font-medium">نام</th>
                <th className="px-4 py-3 text-right font-medium">شماره</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t border-line">
                  <td className="px-4 py-3">{item.name}</td>
                  <td className="px-4 py-3" dir="ltr">
                    {item.phone}
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-8 text-ink/50" colSpan={2}>
                    هنوز همکاری از دیوار در این لیست نیست.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {progressOpen && sync && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-ink/40 px-4">
          <div className="w-full max-w-md rounded-3xl bg-paper p-6">
            <h2 className="text-lg font-semibold">بروزرسانی دیوار</h2>
            {sync.phase === "colleagues" && <p className="mt-3 text-sm leading-7">در حال بررسی لیست مشاوران</p>}
            {sync.colleagues_ready && <p className="mt-3 text-sm leading-7">بررسی لیست مشاوران</p>}
            {sync.phase === "counting" && <p className="mt-2 text-sm leading-7">در حال شمارش آگهی‌های فعال</p>}
            {(sync.phase === "sending" || sync.phase === "done") && !sync.message.includes("لینک آگهی") && (
              <p className="mt-2 text-sm leading-7">
                {sync.completed} از {sync.total}
              </p>
            )}
            {sync.phase === "done" && !sync.message.includes("لینک آگهی") && (
              <p className="mt-2 text-sm leading-7">{sync.removed} آگهی که دیگر در لیست فعال دیوار نبود از بات حذف شد.</p>
            )}
            {sync.phase === "done" && sync.message.includes("لینک آگهی") && (
              <p className="mt-2 text-sm leading-7 text-copper">{sync.message}</p>
            )}
            {sync.phase === "failed" && <p className="mt-2 text-sm leading-7 text-danger">{sync.message}</p>}
            {sync.errors.length > 0 && (
              <ul className="mt-3 max-h-40 space-y-2 overflow-auto text-sm leading-7 text-danger">
                {sync.errors.slice(0, 12).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            {!sync.running && (
              <button type="button" className="mt-4 rounded-2xl border border-line px-5 py-3" onClick={() => setProgressOpen(false)}>
                بستن
              </button>
            )}
          </div>
        </div>
      )}

      {loginOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-ink/40 px-4">
          <div className="w-full max-w-md rounded-3xl bg-paper p-6">
            <h2 className="text-lg font-semibold">ورود به دیوار</h2>
            <p className="mt-2 text-sm leading-7 text-ink/70">
              برای خواندن لیست همکاران باید با همان شماره‌ای وارد شوید که پنل کسب‌وکار دیوار را می‌بیند.
            </p>
            {loginStep === "phone" ? (
              <form onSubmit={onSendCode} className="mt-4 grid gap-3">
                <input
                  className="rounded-2xl border border-line px-4 py-3"
                  dir="ltr"
                  inputMode="tel"
                  placeholder="شماره موبایل"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  required
                />
                <div className="flex gap-2">
                  <button disabled={busy} className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60">
                    ارسال کد
                  </button>
                  <button type="button" className="rounded-2xl border border-line px-5 py-3" onClick={() => setLoginOpen(false)}>
                    بستن
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={onConfirmCode} className="mt-4 grid gap-3">
                <input
                  className="rounded-2xl border border-line px-4 py-3"
                  dir="ltr"
                  inputMode="numeric"
                  placeholder="کد پیامک"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  required
                />
                <div className="flex gap-2">
                  <button disabled={busy} className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60">
                    تأیید
                  </button>
                  <button type="button" className="rounded-2xl border border-line px-5 py-3" onClick={() => setLoginStep("phone")}>
                    تغییر شماره
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
