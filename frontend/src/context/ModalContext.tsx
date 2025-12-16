"use client";

import React, { createContext, useContext, useState, ReactNode } from 'react';
import dynamic from 'next/dynamic';

const AuthModal = dynamic(() => import('../components/AuthModal').then((mod) => mod.AuthModal), {
  ssr: false,
});

interface ModalContextType {
  openAuthModal: () => void;
  closeAuthModal: () => void;
  isAuthModalOpen: boolean;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export function ModalProvider({ children }: { children: ReactNode }) {
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const openAuthModal = () => setIsAuthModalOpen(true);
  const closeAuthModal = () => setIsAuthModalOpen(false);

  return (
    <ModalContext.Provider value={{ openAuthModal, closeAuthModal, isAuthModalOpen }}>
      {children}
      <AuthModal isOpen={isAuthModalOpen} onClose={closeAuthModal} />
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
