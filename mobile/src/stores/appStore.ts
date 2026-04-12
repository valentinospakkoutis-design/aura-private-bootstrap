import { create } from 'zustand';

export interface User {
  id: string;
  name: string;
  email: string;
  phone?: string;
  avatar?: string;
  voiceCloned: boolean;
  riskProfile: 'conservative' | 'moderate' | 'aggressive';
}

export interface Broker {
  id: string;
  name: string;
  connected: boolean;
  apiKey?: string;
}

export interface Prediction {
  id: string;
  asset: string;
  symbol?: string;
  category?: string;
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  price: number;
  targetPrice?: number;
  timestamp: string;
  reasoning?: string;
  mtf_confluence?: boolean | null;
  trend_1h?: 'bullish' | 'bearish' | 'neutral' | null;
  trend_4h?: 'bullish' | 'bearish' | 'neutral' | null;
  trend_1d?: 'bullish' | 'bearish' | 'neutral' | null;
  rsi_1h?: number | null;
  ensemble?: {
    xgboost?: number | null;
    random_forest?: number | null;
    lstm?: number | null;
    method?: '3-model' | '2-model' | string;
  } | null;
  onchain?: {
    score?: number | null;
    sentiment?: 'bullish' | 'bearish' | 'neutral' | string;
    funding_rate?: number | null;
    long_short_ratio?: number | null;
    fear_greed?: number | null;
  } | null;
}

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastState {
  message: string;
  type: ToastType;
}

export interface ModalState {
  visible: boolean;
  title: string;
  message: string;
  onConfirm?: () => void;
}

interface AppState {
  user: User | null;
  setUser: (user: User | null) => void;

  brokers: Broker[];
  setBrokers: (brokers: Broker[]) => void;
  addBroker: (broker: Broker) => void;
  removeBroker: (brokerId: string) => void;

  predictions: Prediction[];
  setPredictions: (predictions: Prediction[]) => void;

  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;

  toast: ToastState | null;
  showToast: (message: string, type: ToastType) => void;
  hideToast: () => void;

  modal: ModalState | null;
  showModal: (title: string, message: string, onConfirm?: () => void) => void;
  hideModal: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),

  brokers: [],
  setBrokers: (brokers) => set({ brokers }),
  addBroker: (broker) => set((state) => ({ brokers: [...state.brokers, broker] })),
  removeBroker: (brokerId) =>
    set((state) => ({ brokers: state.brokers.filter((broker) => broker.id !== brokerId) })),

  predictions: [],
  setPredictions: (predictions) => set({ predictions }),

  isLoading: false,
  setIsLoading: (isLoading) => set({ isLoading }),
  error: null,
  setError: (error) => set({ error }),

  toast: null,
  showToast: (message, type) => set({ toast: { message, type } }),
  hideToast: () => set({ toast: null }),

  modal: null,
  showModal: (title, message, onConfirm) =>
    set({ modal: { visible: true, title, message, onConfirm } }),
  hideModal: () => set({ modal: null }),
}));
