export class DateFormatter {
  // Format date to Greek locale
  static toGreekDate(date: string | Date): string {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleDateString('el-GR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }

  // Format time to Greek locale
  static toGreekTime(date: string | Date): string {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleTimeString('el-GR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // Format date and time
  static toGreekDateTime(date: string | Date): string {
    return `${this.toGreekDate(date)} ${this.toGreekTime(date)}`;
  }

  // Relative time (e.g., "2 hours ago")
  static toRelativeTime(date: string | Date): string {
    const d = typeof date === 'string' ? new Date(date) : date;
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return 'Μόλις τώρα';
    if (diffMins < 60) return `Πριν ${diffMins} λεπτά`;
    if (diffHours < 24) return `Πριν ${diffHours} ώρες`;
    if (diffDays < 7) return `Πριν ${diffDays} μέρες`;
    return this.toGreekDate(date);
  }

  // Check if date is today
  static isToday(date: string | Date): boolean {
    const d = typeof date === 'string' ? new Date(date) : date;
    const today = new Date();
    return (
      d.getDate() === today.getDate() &&
      d.getMonth() === today.getMonth() &&
      d.getFullYear() === today.getFullYear()
    );
  }

  // Format duration (e.g., "2h 30m")
  static formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
  }
}

