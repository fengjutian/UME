import { useState, useEffect } from 'react';
import { Provider } from '@/constants/messages';

interface UseAuthReturn {
  umeApiKey: string;
  openaiApiKey: string;
  provider: Provider;
  user: string;
  setAuth: (ume: string, openai: string, provider: Provider) => void;
  setUser: (user: string) => void;
  clearAuth: () => void;
  clearUser: () => void;
}

export const useAuth = (): UseAuthReturn => {
  const [umeApiKey, setUMEApiKey] = useState<string>('');
  const [openaiApiKey, setOpenaiApiKey] = useState<string>('');
  const [provider, setProvider] = useState<Provider>('openai');
  const [user, setUser] = useState<string>('');

  useEffect(() => {
    const ume = localStorage.getItem('umeApiKey');
    const openai = localStorage.getItem('openaiApiKey');
    const savedProvider = localStorage.getItem('provider') as Provider;
    const savedUser = localStorage.getItem('user');

    if (ume && openai && savedProvider) {
      setAuth(ume, openai, savedProvider);
    }
    if (savedUser) {
      setUser(savedUser);
    }
  }, []);

  const setAuth = (ume: string, openai: string, provider: Provider) => {
    setUMEApiKey(ume);
    setOpenaiApiKey(openai);
    setProvider(provider);
    localStorage.setItem('umeApiKey', ume);
    localStorage.setItem('openaiApiKey', openai);
    localStorage.setItem('provider', provider);
  };

  const clearAuth = () => {
    localStorage.removeItem('umeApiKey');
    localStorage.removeItem('openaiApiKey');
    localStorage.removeItem('provider');
    setUMEApiKey('');
    setOpenaiApiKey('');
    setProvider('openai');
  };

  const updateUser = (user: string) => {
    setUser(user);
    localStorage.setItem('user', user);
  };

  const clearUser = () => {
    localStorage.removeItem('user');
    setUser('');
  };

  return {
    umeApiKey,
    openaiApiKey,
    provider,
    user,
    setAuth,
    setUser: updateUser,
    clearAuth,
    clearUser,
  };
}; 