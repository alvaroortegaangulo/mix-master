"use client";

import React, { useState } from "react";
import { useAuth } from "../../../context/AuthContext";
import { useRouter } from "next/navigation";
import { Link } from "../../../i18n/routing";
import { getBackendBaseUrl } from "../../../lib/mixApi";
import { useTranslations } from "next-intl";

export default function ProfilePage() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();
  const t = useTranslations('Profile');
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Password change state
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changePasswordError, setChangePasswordError] = useState<string | null>(null);
  const [changePasswordSuccess, setChangePasswordSuccess] = useState<string | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    router.push("/");
    return null;
  }

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setChangePasswordError(null);
    setChangePasswordSuccess(null);

    if (newPassword !== confirmPassword) {
      setChangePasswordError(t('changePassword.matchError'));
      return;
    }

    if (newPassword.length < 8) {
      setChangePasswordError(t('changePassword.lengthError'));
      return;
    }

    setIsChangingPassword(true);

    try {
      const token = localStorage.getItem("access_token");
      const baseUrl = getBackendBaseUrl();
      const res = await fetch(`${baseUrl}/auth/change-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setChangePasswordSuccess(t('changePassword.success'));
        setOldPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        setChangePasswordError(data.detail || t('changePassword.genericError'));
      }
    } catch (err) {
      console.error(err);
      setChangePasswordError(t('changePassword.genericError'));
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (
      !window.confirm(
        t('deleteAccount.confirm')
      )
    ) {
      return;
    }

    setIsDeleting(true);
    setError(null);

    try {
      const token = localStorage.getItem("access_token");
      const baseUrl = getBackendBaseUrl();
      const res = await fetch(`${baseUrl}/auth/me`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        logout();
        router.push("/");
      } else {
        setError(t('deleteAccount.error'));
      }
    } catch (err) {
      console.error(err);
      setError(t('deleteAccount.error'));
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <main className="mx-auto mt-10 w-full max-w-2xl px-4 pb-20">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">{t('title')}</h1>
          <button
            onClick={handleLogout}
            className="rounded-md border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
          >
            {t('signOut')}
          </button>
        </div>

        <div className="space-y-8">
          {/* User Info Section */}
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-400">
                  {t('userInfo.fullName')}
                </label>
                <div className="mt-1 text-lg font-medium text-slate-200">
                  {user.full_name || "N/A"}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400">
                  {t('userInfo.email')}
                </label>
                <div className="mt-1 text-lg font-medium text-slate-200">
                  {user.email}
                </div>
              </div>
            </div>
          </div>

          {/* Change Password Section */}
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
            <h2 className="text-xl font-semibold text-slate-200 mb-6">{t('changePassword.title')}</h2>

            {changePasswordSuccess && (
              <div className="mb-4 rounded bg-green-900/30 border border-green-800 p-3 text-sm text-green-200">
                {changePasswordSuccess}
              </div>
            )}

            {changePasswordError && (
              <div className="mb-4 rounded bg-red-900/30 border border-red-800 p-3 text-sm text-red-200">
                {changePasswordError}
              </div>
            )}

            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">
                  {t('changePassword.oldPassword')}
                </label>
                <input
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  required
                  className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-slate-200 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">
                  {t('changePassword.newPassword')}
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-slate-200 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">
                  {t('changePassword.confirmPassword')}
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-slate-200 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isChangingPassword}
                  className="rounded-md bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-500 disabled:opacity-50 transition-colors"
                >
                  {isChangingPassword ? t('changePassword.updating') : t('changePassword.update')}
                </button>
              </div>
            </form>
          </div>

          {/* Delete Account Section */}
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
            <h2 className="text-xl font-semibold text-red-400 mb-4">{t('deleteAccount.title')}</h2>
            <p className="mb-4 text-sm text-slate-400">
              {t('deleteAccount.warning')}
            </p>

            {error && (
              <div className="mb-4 rounded bg-red-900/50 p-3 text-sm text-red-200">
                {error}
              </div>
            )}

            <button
              onClick={handleDeleteAccount}
              disabled={isDeleting}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {isDeleting ? t('deleteAccount.deleting') : t('deleteAccount.button')}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
