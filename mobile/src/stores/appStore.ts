import { create } from 'zustand';

interface User {
  id: string;
  name: string;
  email: string;
  phone?: string;
  avatar?: string;
  voiceCloned: boolean;
  riskProfile: 'conservative' | 'moderate' | 'aggressive';
}

interface Broker {
  id: string;
  name: string;
  connected: boolean;
  apiKey?: string;
}

interface Prediction {
  id: string;
  asset: string;
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  price: number;
  timestamp: string;
}

interface AppState {
  // User
  user: User | null;
  setUser: (user: User | null) => void;

  // Brokers
  brokers: Broker[];
  setBrokers: (brokers: Broker[]) => void;
  addBroker: (broker: Broker) => void;
  removeBroker: (brokerId: string) => void;

  // Predictions
  predictions: Prediction[];
  setPredictions: (predictions: Prediction[]) => void;

  // UI State
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;

  // Toast
  toast: { message: string; type: 'success' | 'error' | 'warning' | 'info' } | null;
  showToast: (message: string, type: 'success' | 'error' | 'warning' | 'info') => void;
  hideToast: () => void;

  // Modal
  modal: { visible: boolean; title: string; message: string; onConfirm?: () => void } | null;
  showModal: (title: string, message: string, onConfirm?: () => void) => void;
  hideModal: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  // User
  user: null,
  setUser: (user) => set({ user }),

  // Brokers
  brokers: [],
  setBrokers: (brokers) => set({ brokers }),
  addBroker: (broker) => set((state) => ({ brokers: [...state.brokers, broker] })),
  removeBroker: (brokerId) =>
    set((state) => ({ brokers: state.brokers.filter((b) => b.id !== brokerId) })),

  // Predictions
  predictions: [],
  setPredictions: (predictions) => set({ predictions }),

  // UI State
  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),
  error: null,
  setError: (error) => set({ error }),

  // Toast
  toast: null,
  showToast: (message, type) => set({ toast: { message, type } }),
  hideToast: () => set({ toast: null }),

  // Modal
  modal: null,
  showModal: (title, message, onConfirm) =>
    set({ modal: { visible: true, title, message, onConfirm } }),
  hideModal: () => set({ modal: null }),
}));

