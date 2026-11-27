import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, loginAdmin, loginAgent } from "../api";

export function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"agent" | "admin">("admin");
  const [phone, setPhone] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "agent") {
        await loginAgent(phone);
        navigate("/panel");
      } else {
        await loginAdmin(username, password);
        navigate("/admin");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ورود انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main dir="ltr" className="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
      <section className="relative hidden overflow-hidden bg-pine text-sand lg:flex">
        <div className="pointer-events-none absolute -left-20 top-8 h-64 w-64 rounded-full bg-white/5" />
        <div className="pointer-events-none absolute -bottom-24 right-[-3rem] h-80 w-80 rounded-full bg-black/10" />
        <div className="relative flex w-full flex-col items-center justify-center px-10">
          <svg className="h-52 w-72" viewBox="0 0 320 220" fill="none" aria-hidden="true">
            <path d="M16 168h288" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.5" />
            <path d="M46 168V122h28v46" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" />
            <path d="M52 122 60 110l8 12" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M236 168V108h36v60" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" />
            <path d="M244 108 254 94l10 14" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M92 168V78l68-46 68 46v90" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
            <path d="M148 168v-42h24v42" stroke="currentColor" strokeWidth="1.75" />
            <path d="M112 104h18v16h-18zM190 104h18v16h-18z" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="160" cy="34" r="3" fill="currentColor" fillOpacity="0.8" />
          </svg>
          <p className="brand-word mt-8 text-3xl font-medium">IranHouseVIP</p>
          <span className="mt-5 h-px w-14 bg-sand/60" />
        </div>
      </section>

      <section dir="rtl" className="flex items-center justify-center px-5 py-12">
        <form onSubmit={onSubmit} className="w-full max-w-md rounded-3xl border border-line bg-paper p-7 shadow-sm">
          <h2 className="text-center text-2xl font-semibold">ورود به سامانه</h2>
          <div className="mt-6 flex rounded-full bg-sand p-1 text-sm">
            <button
              type="button"
              className={`flex-1 rounded-full px-3 py-2 ${mode === "admin" ? "bg-pine text-white" : "text-ink/70"}`}
              onClick={() => setMode("admin")}
            >
              ادمین
            </button>
            <button
              type="button"
              className={`flex-1 rounded-full px-2 py-2 leading-5 ${mode === "agent" ? "bg-pine text-white" : "text-ink/70"}`}
              onClick={() => setMode("agent")}
            >
              مشاور خارج از پنل دیوار
            </button>
          </div>

          {mode === "agent" ? (
            <label className="mt-6 block text-sm">
              شماره موبایل
              <input
                className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none focus:border-pine"
                inputMode="tel"
                placeholder="0912xxxxxxx"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
              />
            </label>
          ) : (
            <div className="mt-6 space-y-4">
              <label className="block text-sm">
                نام کاربری
                <input
                  className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3 outline-none focus:border-pine"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                />
              </label>
              <label className="block text-sm">
                رمز عبور
                <input
                  type="password"
                  className="mt-2 w-full rounded-2xl border border-line bg-white px-4 py-3 outline-none focus:border-pine"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </label>
            </div>
          )}

          {error && <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm leading-7 text-danger">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="mt-6 w-full rounded-2xl bg-copper px-4 py-3 font-medium text-white disabled:opacity-60"
          >
            {busy ? "در حال بررسی..." : "ورود"}
          </button>
          {mode === "agent" && (
            <p className="mt-4 text-sm leading-7 text-ink/60">رمز عبور لازم نیست. فقط شماره‌ای که ادمین فعال کرده باشد وارد می‌شود.</p>
          )}
        </form>
      </section>
    </main>
  );
}
