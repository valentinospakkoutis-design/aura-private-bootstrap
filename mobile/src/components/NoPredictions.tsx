import React from 'react';
import { EmptyState } from './EmptyState';
import { useRouter } from 'expo-router';

export const NoPredictions: React.FC = () => {
  const router = useRouter();

  return (
    <EmptyState
      icon="🤖"
      title="Το AI Σκέφτεται..."
      description="Το AURA αναλύει τώρα τις αγορές και θα σου δώσει προβλέψεις σύντομα. Συνήθως χρειάζεται λίγα λεπτά."
      actionLabel="Ανανέωση"
      onAction={() => {}}
      secondaryActionLabel="Ρυθμίσεις AI"
      onSecondaryAction={() => router.push('/settings')}
    />
  );
};

