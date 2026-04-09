import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Platform } from 'react-native';
import { translations } from '../localization/translations';

type Language = 'el' | 'en';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, params?: Record<string, string>) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'el',
  setLanguage: () => {},
  t: (key) => key,
});

const STORAGE_KEY = 'app_language';

async function loadLanguage(): Promise<Language> {
  try {
    if (Platform.OS === 'web') {
      const val = localStorage.getItem(STORAGE_KEY);
      if (val === 'el' || val === 'en') return val;
    } else {
      const SecureStore = require('expo-secure-store');
      const val = await SecureStore.getItemAsync(STORAGE_KEY);
      if (val === 'el' || val === 'en') return val;
    }
  } catch {}
  return 'el';
}

async function saveLanguage(lang: Language) {
  try {
    if (Platform.OS === 'web') {
      localStorage.setItem(STORAGE_KEY, lang);
    } else {
      const SecureStore = require('expo-secure-store');
      await SecureStore.setItemAsync(STORAGE_KEY, lang);
    }
  } catch {}
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>('el');

  useEffect(() => {
    loadLanguage().then(setLanguageState);
  }, []);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    saveLanguage(lang);
  };

  const t = (key: string, params?: Record<string, string>): string => {
    let text = translations[language]?.[key] || translations['en']?.[key] || key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.replace(`{${k}}`, v);
      }
    }
    return text;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useLanguage = () => useContext(LanguageContext);
