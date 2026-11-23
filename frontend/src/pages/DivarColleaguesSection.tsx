import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  confirmDivarLogin,
  divarColleagues,
  refreshDivarColleagues,
  saveDivarLink,
  startDivarLogin,
} from "../api";
import type { DivarColleague } from "../types";

const PLACEHOLDER = "https://divar.ir/my-divar/my-business/wgiqQiGe/agent-management";

export function DivarColleaguesSection() {
  const [url, setUrl] = useState("");
  const [savedUrl, setSavedUrl] = useState("");
  const [items, setItems] = useState<DivarColleague[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginStep, setLoginStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");

  useEffect(() => {
    divarColleagues()
      .then((state) => {
        setSavedUrl(state.url);
        setUrl(state.url);
        setItems(state.items);
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "لیست همکاران خوانده نشد."));
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
      setNote("لینک ثبت شد.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت لینک انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  function describe(added: number, removed: number, updated: number) {
    if (added + removed + updated === 0) return "لیست تغییری نداشت.";
    return `${added} نفر اضافه، ${removed} نفر حذف و ${updated} نفر ویرایش شد.`;
  }

  async function runRefresh() {
    const result = await refreshDivarColleagues();
    if (result.needs_login) {
      setLoginStep("phone");
      setCode("");
      setLoginOpen(true);
      return;
    }
    setItems(result.items);
    setNote(describe(result.added, result.removed, result.updated));
  }

  async function onRefresh() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      await runRefresh();
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
      await runRefresh();
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
          className="rounded-2xl border border-line px-4 py-3 outline-none focus:border-pine"
          dir="ltr"
          placeholder={PLACEHOLDER}
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          required
        />
        <button disabled={busy} className="rounded-2xl bg-pine px-5 py-3 text-white disabled:opacity-60">
          ثبت
        </button>
      </form>
      <p className="mt-3 text-sm leading-7 text-ink/60">
        لینک صفحهٔ مدیریت همکاران دیوار را ثبت کنید. نمونه: {PLACEHOLDER}
      </p>

      {savedUrl && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-line bg-paper px-5 py-4">
          <p className="min-w-0 break-all text-sm" dir="ltr">
            {savedUrl}
          </p>
          <button
            type="button"
            disabled={busy}
            className="rounded-2xl bg-pine px-5 py-3 text-sm text-white disabled:opacity-60"
            onClick={onRefresh}
          >
            بروزرسانی
          </button>
        </div>
      )}

      {note && <p className="mt-4 rounded-2xl bg-sand px-4 py-3 text-sm leading-7">{note}</p>}
      {error && <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm leading-7 text-danger">{error}</p>}

      <div className="mt-5 overflow-hidden rounded-3xl border border-line bg-paper">
        <table className="w-full text-sm">
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
      </div>

      {loginOpen && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-ink/40 px-4">
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
