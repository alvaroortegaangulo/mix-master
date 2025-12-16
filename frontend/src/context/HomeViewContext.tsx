"use client";

import { createContext, useContext } from "react";

interface HomeViewContextType {
  handleTryIt: () => void;
}

export const HomeViewContext = createContext<HomeViewContextType | null>(null);

export function useHomeView() {
  const context = useContext(HomeViewContext);
  if (!context) {
    throw new Error("useHomeView must be used within a HomeViewProvider");
  }
  return context;
}
