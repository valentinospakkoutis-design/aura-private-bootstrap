import React from 'react';
import { EmptyState } from './EmptyState';
import { useRouter } from 'expo-router';

export const NoTrades: React.FC = () => {
  const router = useRouter();

  return (
    <EmptyState
      icon="📊"
      title="Κανένα Trade Ακόμα"
      description="Δεν έχεις κάνει ακόμα καμία συναλλαγή. Σύνδεσε το broker σου και άφησε το AURA να ξεκινήσει."
      actionLabel="Σύνδεση Broker"
      onAction={() => router.push('/brokers')}
      secondaryActionLabel="Δοκιμή με Paper Trading"
      onSecondaryAction={() => router.push('/paper-trading')}
    />
  );
};

