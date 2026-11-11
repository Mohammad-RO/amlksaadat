import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { clearToken, currentSession, token } from "./api";
import type { Role } from "./types";

export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const [state, setState] = useState<"checking" | "ok" | "no">("checking");

  useEffect(() => {
    if (!token()) {
      setState("no");
      return;
    }
    currentSession()
      .then((session) => {
        if (session.role !== role) {
          setState("no");
          return;
        }
        localStorage.setItem("amlak_name", session.name);
        setState("ok");
      })
      .catch(() => {
        clearToken();
        setState("no");
      });
  }, [role]);

  if (state === "checking") {
    return <p className="px-6 py-10 text-sm text-ink/60">در حال بررسی ورود...</p>;
  }
  if (state === "no") return <Navigate to="/" replace />;
  return children;
}
