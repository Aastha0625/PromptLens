export function formatNumber(val) {
  if (val == null) return "0";
  return new Intl.NumberFormat('en-US').format(val);
}

export function formatCost(val) {
  // If the cost is strictly null, the pricing is unknown.
  if (val == null) return "-";
  
  // Format as $0.0000 to show small fractions of a cent
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 4,
    maximumFractionDigits: 4
  }).format(val);
}

export function formatDate(isoString) {
  if (!isoString) return "";
  // The API returns UTC strings without a Z timezone indicator. 
  // We append 'Z' to explicitly tell JS it's UTC so it converts to local time correctly.
  const dateObj = new Date(isoString.endsWith('Z') ? isoString : isoString + 'Z');
  return dateObj.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function formatLatency(ms) {
  if (ms == null) return "-";
  return `${Math.round(ms)} ms`;
}
