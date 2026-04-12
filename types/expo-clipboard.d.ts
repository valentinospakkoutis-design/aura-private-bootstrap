declare module 'expo-clipboard' {
  export function setStringAsync(text: string): Promise<boolean>;
  export function getStringAsync(options?: Record<string, unknown>): Promise<string>;
}
