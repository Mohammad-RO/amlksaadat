import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, loginAdmin, loginAgent } from "../api";

export function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"agent" | "admin">("agent");
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
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
      <section className="hidden flex-col justify-between bg-pine px-12 py-10 text-sand lg:flex">
        <p className="text-sm tracking-[0.18em] text-sand/70">سعادت‌آباد</p>
        <div>
          <h1 className="max-w-md text-4xl font-semibold leading-relaxed">ثبت فایل دیوار، پیشنهاد خانه در تلگرام</h1>
          <p className="mt-6 max-w-md leading-8 text-sand/80">
            مشاور لینک آگهی را ثبت می‌کند. خریدار در ربات، متراژ و قیمت و خواب را می‌گوید و فقط خانه‌های نزدیک به همان
            بازه را می‌بیند.
          </p>
        </div>
        <ol className="grid max-w-lg grid-cols-3 gap-4 text-sm">
          <li className="border-t border-sand/30 pt-3">ورود با شماره مجاز</li>
          <li className="border-t border-sand/30 pt-3">استخراج آگهی دیوار</li>
          <li className="border-t border-sand/30 pt-3">تطبیق با بازه ۱۵ درصد</li>
        </ol>
      </section>

      <section className="flex items-center justify-center px-5 py-12">
        <form onSubmit={onSubmit} className="w-full max-w-md rounded-3xl border border-line bg-paper p-7 shadow-sm">
          <p className="text-sm text-moss">املاک سعادت‌آباد</p>
          <h2 className="mt-2 text-2xl font-semibold">ورود به سامانه</h2>
          <div className="mt-6 grid grid-cols-2 rounded-full bg-sand p-1 text-sm">
            <button
              type="button"
              className={`rounded-full px-3 py-2 ${mode === "agent" ? "bg-pine text-white" : "text-ink/70"}`}
              onClick={() => setMode("agent")}
            >
              مشاور
            </button>
            <button
              type="button"
              className={`rounded-full px-3 py-2 ${mode === "admin" ? "bg-pine text-white" : "text-ink/70"}`}
              onClick={() => setMode("admin")}
            >
              ادمین
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
