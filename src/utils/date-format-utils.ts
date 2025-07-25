// src/utils/date-format-utils.ts

/**
 * Format a date/time string using custom format tokens
 * @param format - Format string with tokens like YYYY, MM, DD, HH, mm, ss
 * @returns Formatted string with example values
 */
export function formatDateTime(format: string): string {
  const replacements: Record<string, string> = {
    'YYYY': '2025',
    'YY': '25', 
    'MMMM': 'July',
    'MMM': 'Jul',
    'MM': '07',
    'dddd': 'Sunday',
    'ddd': 'Sun',
    'DD': '20',
    'D': '20',
    'HH': '14',
    'hh': '02',
    'h': '2',
    'mm': '32',
    'ss': '15',
    'A': 'PM',
    'a': 'pm'
  }
  
  let result = format
  
  // Sort by length (longest first) to avoid partial replacements
  const sortedKeys = Object.keys(replacements).sort((a, b) => b.length - a.length)
  
  for (const key of sortedKeys) {
    result = result.replace(new RegExp(key, 'g'), replacements[key])
  }
  
  return result
}