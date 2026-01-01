import { AxiosError } from 'axios';

export interface AppError {
  message: string;
  code?: string;
  statusCode?: number;
}

export class ErrorHandler {
  static handle(error: unknown): AppError {
    // Axios error
    if (this.isAxiosError(error)) {
      return this.handleAxiosError(error);
    }

    // Generic error
    if (error instanceof Error) {
      return {
        message: error.message,
      };
    }

    // Unknown error
    return {
      message: 'Κάτι πήγε στραβά. Δοκίμασε ξανά.',
    };
  }

  private static isAxiosError(error: unknown): error is AxiosError {
    return (error as AxiosError).isAxiosError !== undefined;
  }

  private static handleAxiosError(error: AxiosError): AppError {
    const statusCode = error.response?.status;
    const data = error.response?.data as any;

    // Network error
    if (!error.response) {
      return {
        message: 'Πρόβλημα σύνδεσης. Έλεγξε το Internet σου.',
        code: 'NETWORK_ERROR',
      };
    }

    // Server errors
    switch (statusCode) {
      case 400:
        return {
          message: data?.message || 'Μη έγκυρα δεδομένα.',
          code: 'BAD_REQUEST',
          statusCode,
        };
      case 401:
        return {
          message: 'Δεν έχεις πρόσβαση. Κάνε login ξανά.',
          code: 'UNAUTHORIZED',
          statusCode,
        };
      case 403:
        return {
          message: 'Δεν έχεις δικαίωμα για αυτή την ενέργεια.',
          code: 'FORBIDDEN',
          statusCode,
        };
      case 404:
        return {
          message: 'Δεν βρέθηκε αυτό που ζητάς.',
          code: 'NOT_FOUND',
          statusCode,
        };
      case 429:
        return {
          message: 'Πολλές προσπάθειες. Δοκίμασε σε λίγο.',
          code: 'TOO_MANY_REQUESTS',
          statusCode,
        };
      case 500:
      case 502:
      case 503:
        return {
          message: 'Πρόβλημα στον server. Δοκίμασε σε λίγο.',
          code: 'SERVER_ERROR',
          statusCode,
        };
      default:
        return {
          message: data?.message || 'Κάτι πήγε στραβά.',
          code: 'UNKNOWN_ERROR',
          statusCode,
        };
    }
  }

  static getUserFriendlyMessage(error: AppError): string {
    return error.message;
  }
}

