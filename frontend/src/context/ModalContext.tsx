"use client";

import React, { createContext, useContext, useState, ReactNode } from 'react';
import dynamic from 'next/dynamic';
import { setAuthRedirect } from '../lib/authRedirect';
import { GoogleOAuthProvider } from "@react-oauth/google";

const AuthModal = dynamic(() => import('../components/AuthModal').then((mod) => mod.AuthModal), {
  ssr: false,
});

interface ModalContextType {
  openAuthModal: (redirectTo?: string) => void;
  closeAuthModal: () => void;
  isAuthModalOpen: boolean;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export function ModalProvider({ children }: { children: ReactNode }) {
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "YOUR_GOOGLE_CLIENT_ID_HERE";

  const openAuthModal = (redirectTo?: string) => {
    setAuthRedirect(redirectTo);
    setIsAuthModalOpen(true);
  };
  const closeAuthModal = () => setIsAuthModalOpen(false);

  return (
    <ModalContext.Provider value={{ openAuthModal, closeAuthModal, isAuthModalOpen }}>
      {children}
      {isAuthModalOpen ? (
        <GoogleOAuthProvider clientId={googleClientId}>
          <AuthModal isOpen={isAuthModalOpen} onClose={closeAuthModal} />
        </GoogleOAuthProvider>
      ) : null}
    </ModalContext.Provider>
  );
}

export function useModal() {
  const context = useContext(ModalContext);
  if (context === undefined) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
}
