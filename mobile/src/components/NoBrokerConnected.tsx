import React from 'react';
import { EmptyState } from './EmptyState';
import { useRouter } from 'expo-router';

export const NoBrokerConnected: React.FC = () => {
  const router = useRouter();

  return (
    <EmptyState
      icon="🔌"
      title="Σύνδεσε το Broker σου"
      description="Για να ξεκινήσει το AURA να κάνει trades, πρέπει να συνδέσεις το broker σου (Binance, eToro, Interactive Brokers)."
      actionLabel="Σύνδεση Broker"
      onAction={() => router.push('/brokers')}
      secondaryActionLabel="Ξεκίνα με Paper Trading"
      onSecondaryAction={() => router.push('/paper-trading')}
    />
  );
};

