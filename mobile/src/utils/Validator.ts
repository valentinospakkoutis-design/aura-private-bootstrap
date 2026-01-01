export class Validator {
  // Email validation
  static isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  // Password validation (min 8 chars, 1 uppercase, 1 lowercase, 1 number)
  static isValidPassword(password: string): boolean {
    if (password.length < 8) return false;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    return hasUpperCase && hasLowerCase && hasNumber;
  }

  // API Key validation (basic length check)
  static isValidApiKey(apiKey: string, minLength: number = 32): boolean {
    return apiKey.length >= minLength && /^[A-Za-z0-9]+$/.test(apiKey);
  }

  // Amount validation (positive number)
  static isValidAmount(amount: number | string): boolean {
    const num = typeof amount === 'string' ? parseFloat(amount) : amount;
    return !isNaN(num) && num > 0;
  }

  // Phone number validation (basic international format)
  static isValidPhone(phone: string): boolean {
    const phoneRegex = /^\+?[1-9]\d{1,14}$/;
    return phoneRegex.test(phone.replace(/[\s\-$]/g, ''));
  }

  // URL validation
  static isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  // Sanitize input (remove dangerous characters)
  static sanitizeInput(input: string): string {
    return input
      .replace(/[<>]/g, '') // Remove < and >
      .replace(/javascript:/gi, '') // Remove javascript: protocol
      .trim();
  }

  // Check if string is empty or whitespace
  static isEmpty(value: string | null | undefined): boolean {
    return !value || value.trim().length === 0;
  }

  // Validate trading amount with min/max
  static isValidTradeAmount(
    amount: number,
    min: number = 0.01,
    max: number = 1000000
  ): { valid: boolean; error?: string } {
    if (isNaN(amount)) {
      return { valid: false, error: 'Invalid amount' };
    }
    if (amount < min) {
      return { valid: false, error: `Minimum amount is ${min}` };
    }
    if (amount > max) {
      return { valid: false, error: `Maximum amount is ${max}` };
    }
    return { valid: true };
  }
}

