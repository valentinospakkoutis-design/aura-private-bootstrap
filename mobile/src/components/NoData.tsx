import React from 'react';
import { EmptyState } from './EmptyState';

interface NoDataProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export const NoData: React.FC<NoDataProps> = ({
  title = 'Κάτι Πήγε Στραβά',
  description = 'Δεν μπορέσαμε να φορτώσουμε τα δεδομένα. Δοκίμασε ξανά.',
  onRetry,
}) => {
  return (
    <EmptyState
      icon="⚠️"
      title={title}
      description={description}
      actionLabel="Δοκίμασε Ξανά"
      onAction={onRetry}
    />
  );
};

