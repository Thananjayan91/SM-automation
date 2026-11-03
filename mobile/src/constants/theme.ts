export const Colors = {
  primary: '#4f46e5',
  primaryLight: '#eef2ff',
  primaryDark: '#3730a3',
  background: '#f8fafc',
  surface: '#ffffff',
  text: '#0f172a',
  textMuted: '#64748b',
  border: '#e2e8f0',
  success: '#10b981',
  successLight: '#ecfdf5',
  warning: '#f59e0b',
  warningLight: '#fffbeb',
  danger: '#ef4444',
  dangerLight: '#fef2f2',
  info: '#3b82f6',
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const Typography = {
  header: {
    fontSize: 22,
    fontWeight: '700' as const,
    color: Colors.text,
  },
  subHeader: {
    fontSize: 16,
    fontWeight: '600' as const,
    color: Colors.text,
  },
  body: {
    fontSize: 14,
    color: Colors.text,
  },
  caption: {
    fontSize: 12,
    color: Colors.textMuted,
  },
};

