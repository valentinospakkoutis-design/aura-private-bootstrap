import { useEffect, useRef } from 'react';

interface PerformanceMetrics {
  componentName: string;
  mountTime: number;
  renderCount: number;
}

export function usePerformance(componentName: string) {
  const mountTime = useRef<number>(Date.now());
  const renderCount = useRef<number>(0);

  useEffect(() => {
    renderCount.current += 1;

    if (__DEV__) {
      const loadTime = Date.now() - mountTime.current;
      console.log(`[Performance] ${componentName}:`, {
        mountTime: `${loadTime}ms`,
        renderCount: renderCount.current,
      });
    }
  });

  useEffect(() => {
    return () => {
      if (__DEV__) {
        const totalTime = Date.now() - mountTime.current;
        console.log(`[Performance] ${componentName} unmounted after ${totalTime}ms, ${renderCount.current} renders`);
      }
    };
  }, [componentName]);

  return {
    renderCount: renderCount.current,
  };
}

