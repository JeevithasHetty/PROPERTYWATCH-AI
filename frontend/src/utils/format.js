// India formatting helpers
export const INDIA_CENTER = [20.5937, 78.9629];
export const INDIA_ZOOM = 5;

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
export const formatINR = (value) =>
  value === null || value === undefined || value === '' || Number.isNaN(Number(value)) ? 'N/A' : inr.format(Number(value));

export const originLabel = (origin) =>
  origin === 'SATELLITE_LIVE' ? 'Real satellite data'
    : origin === 'DEMO_SYNTHETIC' ? 'DEMO synthetic image'
      : origin === 'USER_UPLOAD' ? 'User-uploaded photo' : 'Unknown source';
