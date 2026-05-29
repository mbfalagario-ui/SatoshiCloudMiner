// Hashrate Cloud Miner design tokens — Electric & Neon dark theme
export const colors = {
  bg: '#0B0E14',
  surface: '#151A22',
  surfaceElevated: '#1F2633',
  border: '#2A3143',
  borderSoft: 'rgba(255,255,255,0.06)',
  text: '#FFFFFF',
  textSecondary: '#A0A5B5',
  textTertiary: '#686D7B',
  textDisabled: '#454955',
  primary: '#00FFA3',
  primaryGlow: 'rgba(0,255,163,0.30)',
  primaryDim: 'rgba(0,255,163,0.10)',
  secondary: '#00D1FF',
  secondaryGlow: 'rgba(0,209,255,0.30)',
  secondaryDim: 'rgba(0,209,255,0.10)',
  danger: '#FF3366',
  dangerDim: 'rgba(255,51,102,0.12)',
  warning: '#FFB800',
  warningDim: 'rgba(255,184,0,0.12)',
  overlay: 'rgba(0,0,0,0.6)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  container: 20,
};

export const radius = {
  sm: 8,
  md: 16,
  lg: 24,
  full: 9999,
};

export const fonts = {
  // System fonts ensure crisp render without bundling extra font files.
  heading: undefined,
  body: undefined,
  // RN doesn't have a true monospace family name, use platform-appropriate fallback
  mono: 'Menlo',
};

export const shadows = {
  glow: {
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 16,
    elevation: 10,
  },
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.35,
    shadowRadius: 16,
    elevation: 6,
  },
};

export const media = {
  appIcon:
    'https://static.prod-images.emergentagent.com/jobs/9b98805d-6f48-4c52-a95c-37410ab52781/images/1ebdaf66e28908ee4864bb3c2cd10c4ffd15605893cece517d1d05873c009bc8.png',
  miningHardware:
    'https://static.prod-images.emergentagent.com/jobs/9b98805d-6f48-4c52-a95c-37410ab52781/images/f4bf258b4d106da8fcdf0aa30bfc55bf18c396cf860b3bb32f08de3362d67572.png',
  cryptoCoin:
    'https://static.prod-images.emergentagent.com/jobs/9b98805d-6f48-4c52-a95c-37410ab52781/images/89ee1f0413f7c7d6a1634b1004644f9ffabf68d2d17546d1fbf48358d1dd5789.png',
  dashboardBg:
    'https://static.prod-images.emergentagent.com/jobs/9b98805d-6f48-4c52-a95c-37410ab52781/images/e1bdbcc3ca21d337dcc662f55d9d5dc3d4cb29a6d9c1ff22e40dd80173ff8e80.png',
  serverRack:
    'https://images.unsplash.com/photo-1680992044138-ce4864c2b962?crop=entropy&cs=srgb&fm=jpg&q=85',
};

export function fmtUsd(v: number): string {
  if (v === undefined || v === null || isNaN(v)) return '$0.00';
  return '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtBtc(v: number): string {
  if (v === undefined || v === null || isNaN(v)) return '0.00000000';
  return v.toFixed(8);
}

export function fmtHash(v: number): string {
  if (!v) return '0.00 TH/s';
  return `${v.toFixed(2)} TH/s`;
}
