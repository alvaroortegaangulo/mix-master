const AUTH_REDIRECT_KEY = "auth_redirect_path";

export const setAuthRedirect = (path?: string) => {
  if (typeof window === "undefined") return;
  if (path) {
    sessionStorage.setItem(AUTH_REDIRECT_KEY, path);
  } else {
    sessionStorage.removeItem(AUTH_REDIRECT_KEY);
  }
};

export const consumeAuthRedirect = () => {
  if (typeof window === "undefined") return null;
  const value = sessionStorage.getItem(AUTH_REDIRECT_KEY);
  if (value) {
    sessionStorage.removeItem(AUTH_REDIRECT_KEY);
  }
  return value;
};
