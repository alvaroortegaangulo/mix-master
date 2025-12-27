import {getRequestConfig} from 'next-intl/server';
import {routing} from './routing';

export default getRequestConfig(async ({requestLocale}) => {
  const defaultLocale = routing.defaultLocale;
  // This typically corresponds to the `[locale]` segment
  let locale = await requestLocale;

  // Ensure that a valid locale is used
  if (!locale || !routing.locales.includes(locale as any)) {
    locale = defaultLocale;
  }

  const messages = (await import(`../messages/${locale}.json`)).default;
  const defaultMessages =
    locale === defaultLocale
      ? messages
      : (await import(`../messages/${defaultLocale}.json`)).default;

  const getMessageByPath = (source: Record<string, unknown>, path: string) => {
    return path.split('.').reduce<unknown>((current, key) => {
      if (current && typeof current === 'object' && key in (current as Record<string, unknown>)) {
        return (current as Record<string, unknown>)[key];
      }
      return undefined;
    }, source);
  };

  return {
    locale,
    messages,
    onError(error) {
      if (error.code === 'MISSING_MESSAGE') {
        return;
      }
      console.error(error);
    },
    getMessageFallback({namespace, key}) {
      const fullKey = namespace ? `${namespace}.${key}` : key;
      const fallback = getMessageByPath(defaultMessages, fullKey);

      if (typeof fallback === 'string' || typeof fallback === 'number') {
        return String(fallback);
      }

      return fullKey;
    }
  };
});
