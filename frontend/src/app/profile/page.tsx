"use client";

import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getBackendBaseUrl } from "../../lib/mixApi";

export default function ProfilePage() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const handleDeleteAccount = async () => {
    if (
      !window.confirm(
        "Are you sure you want to delete your account? This action cannot be undone."
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
        setError("Failed to delete account. Please try again.");
      }
    } catch (err) {
      console.error(err);
      setError("An error occurred while deleting the account.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800/80">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-4 px-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold">
              A
            </div>
            <span className="text-lg font-semibold tracking-tight text-slate-100">
              Audio Alchemy
            </span>
          </Link>
        </div>
      </header>

      <main className="mx-auto mt-10 w-full max-w-2xl px-4">
        <h1 className="mb-8 text-3xl font-bold">User Profile</h1>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-400">
                Full Name
              </label>
              <div className="mt-1 text-lg font-medium text-slate-200">
                {user.full_name || "N/A"}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-400">
                Email Address
              </label>
              <div className="mt-1 text-lg font-medium text-slate-200">
                {user.email}
              </div>
            </div>

            <div className="pt-6 border-t border-slate-800">
              <h2 className="text-xl font-semibold text-red-400 mb-4">Danger Zone</h2>
              <p className="mb-4 text-sm text-slate-400">
                Once you delete your account, there is no going back. Please be
                certain.
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
                {isDeleting ? "Deleting..." : "Delete Account"}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
