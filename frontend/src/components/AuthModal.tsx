"use client";

import { useState } from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { getBackendBaseUrl } from "../lib/mixApi";
import { useAuth } from "../context/AuthContext";
import { useGoogleLogin } from "@react-oauth/google";
import { gaEvent } from "../lib/ga";
import { useTranslations } from "next-intl";
import { useRouter } from "../i18n/routing";
import { consumeAuthRedirect } from "../lib/authRedirect";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const t = useTranslations('AuthModal');
  const router = useRouter();

  const handleGoogleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      const token =
        (tokenResponse as any).credential ||
        (tokenResponse as any).access_token ||
        (tokenResponse as any).id_token;

      if (!token) {
        setError("No hemos recibido el token de Google.");
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const baseUrl = getBackendBaseUrl();
        const res = await fetch(`${baseUrl}/auth/google`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Authentication failed");
        }

        login(data.access_token);
        gaEvent("login", { method: "google" });
        onClose();
        const redirectTo = consumeAuthRedirect();
        router.push(redirectTo || "/mix");
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    },
    onError: () => setError("No se pudo completar el login con Google."),
  });

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const baseUrl = getBackendBaseUrl();
      const endpoint = isLogin ? "/auth/login" : "/auth/register";

      const body: any = { email, password };
      if (!isLogin) {
        body.full_name = fullName;
      }

      const res = await fetch(`${baseUrl}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Authentication failed");
      }

      const data = await res.json();

      if (data.access_token) {
        login(data.access_token);
        gaEvent(isLogin ? "login" : "sign_up", { method: "email" });
        onClose();
        const redirectTo = consumeAuthRedirect();
        router.push(redirectTo || "/mix");
      } else {
        // Should not happen if backend returns token on register
        if (!isLogin) {
             gaEvent("sign_up", { method: "email", status: "pending_verification" });
        }
        setIsLogin(true);
        setError("Registration successful. Please log in.");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <div className="relative flex w-full max-w-4xl overflow-hidden rounded-2xl bg-slate-900 shadow-2xl ring-1 ring-slate-800">

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 z-10 p-2 text-slate-400 hover:text-white"
        >
          <XMarkIcon className="h-6 w-6" />
        </button>

        {/* Left Side - Promo */}
        <div className="hidden w-1/2 flex-col justify-center bg-slate-800/50 p-12 lg:flex relative overflow-hidden">
             {/* Abstract Background Element */}
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-teal-500/10 to-purple-600/10 z-0"></div>

            <div className="relative z-10">
                <h2 className="mb-4 text-3xl font-bold text-white">
                    {t('seamlessMastering')}
                </h2>
                <p className="mb-8 text-lg text-slate-300">
                    {t('experiencePower')}
                </p>

                {/* Visual Placeholder mimicking the provided image */}
                <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-6 shadow-inner">
                    <div className="flex items-center justify-between mb-4">
                        <div className="h-2 w-24 rounded bg-teal-500/50"></div>
                        <div className="h-4 w-4 rounded-full bg-purple-500/50"></div>
                    </div>
                    <div className="h-24 w-full rounded bg-slate-800/50 mb-4 animate-pulse"></div>
                    <div className="flex gap-2 justify-center">
                         <div className="h-2 w-2 rounded-full bg-slate-600"></div>
                         <div className="h-2 w-2 rounded-full bg-slate-400"></div>
                         <div className="h-2 w-2 rounded-full bg-slate-600"></div>
                    </div>
                </div>
            </div>
        </div>

        {/* Right Side - Form */}
        <div className="flex w-full flex-col justify-center p-8 lg:w-1/2 bg-slate-950">
          <div className="mx-auto w-full max-w-md">
            <h3 className="mb-8 text-center text-2xl font-semibold text-white">
                {isLogin ? t('signIn') : t('createAccount')}
            </h3>

            {/* Social Logins (Placeholders) */}
            <div className="mb-6 space-y-3">
              <button
                type="button"
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-white py-2.5 text-sm font-medium text-slate-900 hover:bg-slate-100 transition"
                onClick={() => handleGoogleLogin()}
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    fill="#EA4335"
                  />
                </svg>
                {t('signInGoogle')}
              </button>
            </div>

            <div className="relative mb-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-700"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-slate-950 px-2 text-slate-500">{t('or')}</span>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded bg-red-500/10 p-2 text-sm text-red-400 text-center">
                  {error}
                </div>
              )}

              {!isLogin && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-300">
                    {t('fullName')}
                  </label>
                  <input
                    type="text"
                    required
                    className="w-full rounded-lg bg-slate-900 border border-slate-700 px-4 py-2.5 text-slate-200 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                    placeholder="John Doe"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>
              )}

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                  {t('email')}
                </label>
                <input
                  type="email"
                  required
                  className="w-full rounded-lg bg-slate-900 border border-slate-700 px-4 py-2.5 text-slate-200 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-300">
                  {t('password')}
                </label>
                <input
                type="password"
                required
                className="w-full rounded-lg bg-slate-900 border border-slate-700 px-4 py-2.5 text-slate-200 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                placeholder="********"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

              {isLogin && (
                <div className="flex justify-end">
                  <a href="#" className="text-sm text-teal-400 hover:text-teal-300">
                    {t('forgotPassword')}
                  </a>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-teal-500 py-2.5 text-sm font-semibold text-slate-950 shadow-lg shadow-teal-500/20 hover:bg-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50"
              >
                {loading ? t('processing') : isLogin ? t('signIn') : t('createAccount')}
              </button>
            </form>

            <div className="mt-6 text-center text-sm text-slate-400">
              {isLogin ? (
                <>
                  {t('newUser')}{" "}
                  <button
                    onClick={() => { setError(null); setIsLogin(false); }}
                    className="font-medium text-teal-400 hover:text-teal-300"
                  >
                    {t('register')}
                  </button>
                </>
              ) : (
                <>
                  {t('alreadyHaveAccount')}{" "}
                  <button
                    onClick={() => { setError(null); setIsLogin(true); }}
                    className="font-medium text-teal-400 hover:text-teal-300"
                  >
                    {t('signIn')}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
