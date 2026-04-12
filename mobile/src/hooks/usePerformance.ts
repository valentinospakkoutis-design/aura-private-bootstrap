import { useEffect, useRef } from 'react';

export function usePerformance(_componentName: string) {
  const renderCount = useRef<number>(0);

  useEffect(() => {
    renderCount.current += 1;
  });

  return {
    renderCount: renderCount.current,
  };
}
