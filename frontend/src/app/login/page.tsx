"use client";
import { useEffect, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

declare global {
  interface Window { google?: { accounts: { id: { initialize: (opts: Record<string, unknown>) => void; renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void } } } }
}

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const handleCredentialResponse = useCallback(async (resp: { credential: string }) => {
    try {
      await api.loginWithGoogle(resp.credential);
      router.push("/inbox");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Sign-in failed.";
      setError(msg.includes("403")
        ? "Your email domain isn't on the allow-list. Contact an admin."
        : "Sign-in failed. Try again.");
    }
  }, [router]);

  useEffect(() => {
    // Optional Google-side domain hint (only applied if a single domain
    // is configured). When multiple domains are allowed, leave it off so
    // Google shows the user's full account picker and the backend
    // validates the email domain.
    const hdHint = process.env.NEXT_PUBLIC_GOOGLE_HOSTED_DOMAIN || undefined;
    const interval = setInterval(() => {
      if (window.google) {
        const initOpts: Record<string, unknown> = {
          client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
          callback: handleCredentialResponse,
        };
        if (hdHint) initOpts.hd = hdHint;
        window.google.accounts.id.initialize(initOpts);
        window.google.accounts.id.renderButton(
          document.getElementById("gsi-button")!,
          { theme: "outline", size: "large", text: "signin_with", width: 280 }
        );
        clearInterval(interval);
      }
    }, 100);
    return () => clearInterval(interval);
  }, [handleCredentialResponse]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50">
      <div className="bg-white rounded-2xl shadow-sm border p-10 max-w-md w-full text-center">
        <h1 className="text-2xl font-semibold tracking-tight">NB Research Tool</h1>
        <p className="text-slate-600 mt-2 mb-8">
          Internal use only — sign in with your @nbmediaproductions.com account.
        </p>
        <div className="flex justify-center"><div id="gsi-button" /></div>
        {error && (
          <p className="text-red-600 text-sm mt-6">{error}</p>
        )}
      </div>
    </div>
  );
}
