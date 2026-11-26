import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  cancelDivarSync,
  confirmDivarLogin,
  divarColleagues,
  divarSyncStatus,
  pauseDivarSync,
  resumeDivarSync,
  saveDivarLink,
  saveDivarPostsLink,
  startDivarLogin,
  startDivarSync,
} from "../api";
import type { DivarColleague, DivarColleagues, DivarSync, DivarSyncReport } from "../types";

const PLACEHOLDER = "https://divar.ir/my-divar/my-business/wgiqQiGe/agent-management";
const POSTS_PLACEHOLDER = "https://divar.ir/my-divar/my-posts";

function adLabel(title: string, consultant: string) {
  return consultant ? `${title} — مشاور: ${consultant}` : title;
}

function changeText(label: string, previous: string, next: string) {
  if (label === "عکس‌ها") return "عکس‌ها عوض شد";
  return `${label}: قبلی ${previous}، فعلی ${next}`;
}

function ReportNames({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="mt-1 text-ink/50">موردی نبود.</p>;
  return (
    <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function SyncReportBody({ report, note }: { report: DivarSyncReport | null; note: string }) {
  if (!report) {
    return <p className="border-t border-line px-5 py-4 text-sm leading-7 text-ink/60">جزئیات این بروزرسانی ذخیره نشده است.</p>;
  }
  const deletionNote = report.deletions_applied
    ? ""
    : report.list_ready
      ? "چون خواندن بعضی آگهی‌ها ناتمام ماند، آگهی قبلی از بات حذف نشد."
      : "لیست آگهی‌ها خوانده نشد، بنابراین آگهی‌ای از بات حذف نشد.";
  return (
    <div className="space-y-5 border-t border-line px-5 py-4 text-sm leading-7">
      <p>وضعیت: {note}</p>
      <section>
        <h3 className="font-medium">لیست مشاوران</h3>
        <p className="mt-2">مشاور جدید: {report.colleagues_added.length}</p>
        <ReportNames items={report.colleagues_added} />
        <p className="mt-3">مشاور حذف‌شده: {report.colleagues_removed.length}</p>
        <ReportNames items={report.colleagues_removed} />
        <p className="mt-3">تغییر شماره تماس: {report.colleague_phones.length}</p>
        {report.colleague_phones.length === 0 ? (
          <p className="mt-1 text-ink/50">موردی نبود.</p>
        ) : (
          <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
            {report.colleague_phones.map((item, index) => (
              <li key={`${item.name}-${index}`}>
                {item.name}: قبلی <span dir="ltr">{item.old_phone}</span>، فعلی <span dir="ltr">{item.new_phone}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3">تغییر نام: {report.colleague_renames.length}</p>
        {report.colleague_renames.length === 0 ? (
          <p className="mt-1 text-ink/50">موردی نبود.</p>
        ) : (
          <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
            {report.colleague_renames.map((item, index) => (
              <li key={`${item.old_name}-${index}`}>
                قبلی {item.old_name}، فعلی {item.new_name}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="font-medium">لیست آگهی‌ها</h3>
        <p className="mt-2">آگهی جدید: {report.ads_added.length}</p>
        <ReportNames items={report.ads_added.map((item) => adLabel(item.title, item.consultant))} />
        <p className="mt-3">حذف‌شده از بات: {report.deletions_applied ? report.ads_removed.length : "—"}</p>
        {deletionNote ? (
          <p className="mt-1 text-ink/70">{deletionNote}</p>
        ) : (
          <ReportNames items={report.ads_removed.map((item) => adLabel(item.title, item.consultant))} />
        )}
        <p className="mt-3">بدون تغییر: {report.unchanged}</p>
      </section>
      <section>
        <h3 className="font-medium">تغییر مشاور آگهی: {report.consultant_changes.length}</h3>
        {report.consultant_changes.length === 0 ? (
          <p className="mt-1 text-ink/50">موردی نبود.</p>
        ) : (
          <ul className="mt-1 max-h-48 space-y-1 overflow-y-auto">
            {report.consultant_changes.map((item, index) => (
              <li key={`${item.title}-${index}`}>
                {item.title}: قبلی {item.old_name}، فعلی {item.new_name}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="font-medium">تغییر مشخصات آگهی: {report.spec_changes.length}</h3>
        {report.spec_changes.length === 0 ? (
          <p className="mt-1 text-ink/50">موردی نبود.</p>
        ) : (
          <ul className="mt-1 max-h-64 space-y-3 overflow-y-auto">
            {report.spec_changes.map((item, index) => (
              <li key={`${item.title}-${index}`}>
                <p>{adLabel(item.title, item.consultant)}</p>
                <ul className="mt-1 space-y-1 text-ink/80">
                  {item.changes.map((change, changeIndex) => (
                    <li key={`${change.label}-${changeIndex}`}>{changeText(change.label, change.old, change.new)}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="font-medium">خطا: {report.errors.length}</h3>
        {report.errors.length === 0 ? (
          <p className="mt-1 text-ink/50">موردی نبود.</p>
        ) : (
          <ul className="mt-1 max-h-48 space-y-1 overflow-y-auto">
            {report.errors.map((item, index) => (
              <li key={`${item.title}-${index}`}>
                {item.title}: {item.reason}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function LockedLink({ label }: { label: string }) {
  return (
    <div className="flex min-h-[50px] items-center rounded-2xl border border-line bg-sand px-4 py-3 text-sm text-ink/70">
      {label}
    </div>
  );
}

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
  const [lastSyncAt, setLastSyncAt] = useState("");
  const [lastSyncNote, setLastSyncNote] = useState("");
  const [lastSyncReport, setLastSyncReport] = useState<DivarSyncReport | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const pollRef = useRef<number | null>(null);
  const progressOpenRef = useRef(false);
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
        setLastSyncAt(state.last_sync_at || "");
        setLastSyncNote(state.last_sync_note || "");
        setLastSyncReport(state.last_sync_report ?? null);
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "لیست همکاران خوانده نشد."));
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, []);

  async function onSave(event?: FormEvent) {
    event?.preventDefault();
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

  async function onSavePosts(event?: FormEvent) {
    event?.preventDefault();
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

  function applyState(state: DivarColleagues) {
    setSavedUrl(state.url);
    setUrl(state.url);
    setSavedPostsUrl(state.posts_url);
    setPostsUrl(state.posts_url);
    setItems(state.items);
    setLastSyncAt(state.last_sync_at || "");
    setLastSyncNote(state.last_sync_note || "");
    setLastSyncReport(state.last_sync_report ?? null);
  }

  function openProgress() {
    progressOpenRef.current = true;
    setProgressOpen(true);
  }

  async function onCloseProgress() {
    progressOpenRef.current = false;
    if (pollRef.current) window.clearTimeout(pollRef.current);
    const active = Boolean(sync?.running);
    setProgressOpen(false);
    setSync((current) => (current ? { ...current, running: false, paused: false } : current));
    if (!active) return;
    try {
      const status = await cancelDivarSync();
      if (!progressOpenRef.current) {
        setSync({ ...status, running: false, paused: false });
        applyState(await divarColleagues());
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "بستن بروزرسانی انجام نشد.");
    }
  }

  async function watchSync() {
    const status = await divarSyncStatus();
    if (!progressOpenRef.current) return;
    setSync(status);
    if (status.needs_login) {
      progressOpenRef.current = false;
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

  async function onPause() {
    setError("");
    try {
      setSync(await pauseDivarSync());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "توقف بروزرسانی انجام نشد.");
    }
  }

  async function onResume() {
    setError("");
    try {
      setSync(await resumeDivarSync());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ادامه بروزرسانی انجام نشد.");
    }
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
      openProgress();
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
      openProgress();
      await watchSync();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ورود به دیوار انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6">
      <form onSubmit={onSave} className="rounded-3xl border border-line bg-paper p-5">
        <p className="mb-2 text-sm font-medium">مشاور</p>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          {locked ? (
            <LockedLink label="لینک لیست مشاوران" />
          ) : (
            <input
              className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine"
              dir="ltr"
              placeholder={PLACEHOLDER}
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              required
            />
          )}
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
            <button
              type="button"
              disabled={busy}
              className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60"
              onClick={() => void onSave()}
            >
              ثبت
            </button>
          )}
        </div>
      </form>
      {!locked && (
        <p className="mt-3 text-sm leading-7 text-ink/60">
          لینک صفحهٔ مدیریت همکاران دیوار را ثبت کنید. نمونه: {PLACEHOLDER}
        </p>
      )}

      <form onSubmit={onSavePosts} className="mt-4 rounded-3xl border border-line bg-paper p-5">
        <p className="mb-2 text-sm font-medium">آگهی</p>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          {postsLocked ? (
            <LockedLink label="لینک آگهی‌های فعال" />
          ) : (
            <input
              className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine"
              dir="ltr"
              placeholder={POSTS_PLACEHOLDER}
              value={postsUrl}
              onChange={(event) => setPostsUrl(event.target.value)}
              required
            />
          )}
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
            <button
              type="button"
              disabled={busy}
              className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60"
              onClick={() => void onSavePosts()}
            >
              ثبت
            </button>
          )}
        </div>
      </form>
      {!postsLocked && (
        <p className="mt-3 text-sm leading-7 text-ink/60">لینک آگهی‌های من در دیوار را ثبت کنید. فقط آگهی‌های فعال فرستاده می‌شوند.</p>
      )}

      {(savedUrl || savedPostsUrl) && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy || (progressOpen && Boolean(sync?.running))}
            className="rounded-2xl bg-pine px-5 py-3 text-sm text-white disabled:opacity-60"
            onClick={onRefresh}
          >
            بروزرسانی
          </button>
          {lastSyncAt && (
            <p className="text-sm leading-7 text-ink/70">
              {lastSyncAt} ({lastSyncNote})
            </p>
          )}
        </div>
      )}

      {lastSyncAt && (
        <div className="mt-4 overflow-hidden rounded-3xl border border-line bg-paper">
          <button
            type="button"
            className="flex w-full items-center justify-between px-5 py-4 text-right font-medium"
            aria-expanded={reportOpen}
            onClick={() => setReportOpen((open) => !open)}
          >
            <span>گزارش آخرین بروزرسانی</span>
            <span className="text-sm text-ink/50">{reportOpen ? "بستن" : "باز کردن"}</span>
          </button>
          {reportOpen && <SyncReportBody report={lastSyncReport} note={lastSyncNote} />}
        </div>
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
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold">بروزرسانی دیوار</h2>
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-full text-xl leading-none text-ink/70 hover:bg-sand"
                aria-label="بستن"
                onClick={() => void onCloseProgress()}
              >
                ×
              </button>
            </div>
            {sync.phase === "colleagues" && (
              <p className="mt-3 text-sm leading-7">{sync.colleagues_ready ? "لیست مشاوران بررسی شد" : "در حال بررسی لیست مشاوران"}</p>
            )}
            {sync.phase === "counting" && <p className="mt-3 text-sm leading-7">در حال خواندن آگهی‌های فعال</p>}
            {sync.phase === "sending" && (
              <div className="mt-3 text-sm leading-7">
                <p>
                  {sync.current_index} از {sync.total}
                </p>
                {sync.current_title && <p className="mt-2">{sync.current_title}</p>}
                {sync.current_author && <p className="text-ink/70">مشاور: {sync.current_author}</p>}
              </div>
            )}
            {sync.phase === "done" && !sync.message.includes("لینک آگهی") && sync.total > 0 && (
              <p className="mt-3 text-sm leading-7">
                {sync.completed} از {sync.total}
              </p>
            )}
            {sync.phase === "done" && !sync.message.includes("لینک آگهی") && (
              <p className="mt-2 text-sm leading-7">{sync.removed} آگهی که دیگر در لیست فعال دیوار نبود از بات حذف شد.</p>
            )}
            {sync.phase === "done" && sync.message.includes("لینک آگهی") && (
              <p className="mt-2 text-sm leading-7 text-copper">{sync.message}</p>
            )}
            {sync.paused && <p className="mt-3 text-sm leading-7 text-copper">پردازش متوقف شد</p>}
            {sync.phase === "failed" && <p className="mt-2 text-sm leading-7 text-danger">{sync.message}</p>}
            {sync.errors.length > 0 && (
              <ul className="mt-3 max-h-40 space-y-2 overflow-auto text-sm leading-7 text-danger">
                {sync.errors.slice(0, 12).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            <div className="mt-4 flex gap-2">
              {sync.running && !sync.paused && (
                <button type="button" className="rounded-2xl border border-line px-5 py-3" onClick={() => void onPause()}>
                  توقف
                </button>
              )}
              {sync.running && sync.paused && (
                <button type="button" className="rounded-2xl bg-pine px-5 py-3 text-white" onClick={() => void onResume()}>
                  ادامه
                </button>
              )}
              {!sync.running && (
                <button type="button" className="rounded-2xl border border-line px-5 py-3" onClick={() => void onCloseProgress()}>
                  بستن
                </button>
              )}
            </div>
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
