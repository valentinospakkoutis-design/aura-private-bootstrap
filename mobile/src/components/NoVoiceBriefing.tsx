import React from 'react';
import { EmptyState } from './EmptyState';
import { useRouter } from 'expo-router';

export const NoVoiceBriefing: React.FC = () => {
  const router = useRouter();

  return (
    <EmptyState
      icon="🎙️"
      title="Δεν Έχεις Ηχογραφήσει Ακόμα"
      description="Ηχογράφησε τη φωνή σου για 30 δευτερόλεπτα και το AURA θα σου δίνει καθημερινά briefings με τη δική σου φωνή!"
      actionLabel="Ηχογράφηση Φωνής"
      onAction={() => router.push('/voice-briefing')}
      secondaryActionLabel="Μάθε Περισσότερα"
      onSecondaryAction={() => {}}
    />
  );
};

