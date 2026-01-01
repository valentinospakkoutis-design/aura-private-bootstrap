export class NumberFormatter {
  // Format currency (USD)
  static toCurrency(amount: number, currency: string = 'USD'): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  }

  // Format percentage
  static toPercentage(value: number, decimals: number = 2): string {
    return `${(value * 100).toFixed(decimals)}%`;
  }

  // Format large numbers with K, M, B suffixes
  static toCompact(num: number): string {
    if (num >= 1_000_000_000) {
      return `${(num / 1_000_000_000).toFixed(1)}B`;
    }
    if (num >= 1_000_000) {
      return `${(num / 1_000_000).toFixed(1)}M`;
    }
    if (num >= 1_000) {
      return `${(num / 1_000).toFixed(1)}K`;
    }
    return num.toFixed(0);
  }

  // Format with thousand separators
  static toLocaleString(num: number, decimals: number = 2): string {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  // Format crypto amount (8 decimals)
  static toCrypto(amount: number): string {
    return amount.toFixed(8).replace(/\.?0+$/, '');
  }

  // Add + or - prefix for profit/loss
  static toProfitLoss(amount: number): string {
    const prefix = amount >= 0 ? '+' : '';
    return `${prefix}${this.toCurrency(amount)}`;
  }

  // Format percentage with + or - prefix
  static toProfitLossPercentage(value: number, decimals: number = 2): string {
    const prefix = value >= 0 ? '+' : '';
    return `${prefix}${(value * 100).toFixed(decimals)}%`;
  }

  // Format number with sign and currency
  static toProfitLossCurrency(amount: number, currency: string = 'USD'): string {
    const prefix = amount >= 0 ? '+' : '';
    return `${prefix}${this.toCurrency(Math.abs(amount), currency)}`;
  }

  // Clamp number between min and max
  static clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }

  // Round to specific decimal places
  static round(value: number, decimals: number = 2): number {
    return Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals);
  }

  // Check if number is valid
  static isValid(value: any): boolean {
    return typeof value === 'number' && !isNaN(value) && isFinite(value);
  }
}

