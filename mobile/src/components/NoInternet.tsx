import React from 'react';
import { EmptyState } from './EmptyState';

interface NoInternetProps {
  onRetry?: () => void;
}

export const NoInternet: React.FC<NoInternetProps> = ({ onRetry }) => {
  return (
    <EmptyState
      icon="📡"
      title="Χωρίς Σύνδεση"
      description="Δεν υπάρχει σύνδεση στο Internet. Έλεγξε τη σύνδεσή σου και δοκίμασε ξανά."
      actionLabel="Δοκίμασε Ξανά"
      onAction={onRetry}
    />
  );
};

