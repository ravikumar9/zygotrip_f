/**
 * Meal plan label mapping — normalizes supplier terminology to OTA-friendly labels.
 *
 * Supplier values (EP/CP/MAP/AP or room_only/breakfast/half_board/full_board)
 * must NEVER be shown to users. Always use this mapping.
 */

export const MEAL_PLAN_LABELS: Record<string, string> = {
  // Supplier codes (short)
  EP: 'Room Only',
  CP: 'Breakfast Included',
  MAP: 'Breakfast & Lunch/Dinner Included',
  AP: 'All Meals Included',

  // Backend enum values (snake_case)
  room_only: 'Room Only',
  breakfast: 'Breakfast Included',
  half_board: 'Breakfast & Lunch/Dinner Included',
  full_board: 'All Meals Included',

  // Alternate snake_case variants seen in some API responses
  breakfast_included: 'Breakfast Included',
  half_board_included: 'Breakfast & Lunch/Dinner Included',
  full_board_included: 'All Meals Included',

  // Room model codes (apps/rooms/models.py)
  'R': 'Room Only',
  'R+B': 'Breakfast Included',
  'R+B+L/D': 'Breakfast & Lunch/Dinner Included',
  'R+A': 'All Meals Included',

  // Lowercase variants
  ep: 'Room Only',
  cp: 'Breakfast Included',
  map: 'Breakfast & Lunch/Dinner Included',
  ap: 'All Meals Included',
};

/**
 * Get user-friendly meal plan label.
 * Falls back to titlecased input if not found in mapping.
 */
export function getMealPlanLabel(code: string | null | undefined): string {
  if (!code) return 'Room Only';
  return MEAL_PLAN_LABELS[code] ?? code.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Meal plan icons for UI display
 */
export const MEAL_PLAN_ICONS: Record<string, string> = {
  room_only: '🛏️',
  EP: '🛏️',
  'R': '🛏️',
  breakfast: '🍳',
  CP: '🍳',
  'R+B': '🍳',
  half_board: '🍽️',
  MAP: '🍽️',
  'R+B+L/D': '🍽️',
  full_board: '🍴',
  AP: '🍴',
  'R+A': '🍴',
};

/** Short code + color for badge display */
export const MEAL_PLAN_META: Record<string, { short: string; label: string; color: string }> = {
  'R':       { short: 'EP',  label: 'Room Only',                         color: 'text-neutral-700' },
  'R+B':     { short: 'CP',  label: 'Breakfast Included',                color: 'text-green-700' },
  'R+B+L/D': { short: 'MAP', label: 'Breakfast & Lunch/Dinner Included', color: 'text-blue-700' },
  'R+A':     { short: 'AP',  label: 'All Meals Included',                color: 'text-purple-700' },
};

export function getMealPlanIcon(code: string | null | undefined): string {
  if (!code) return '🛏️';
  return MEAL_PLAN_ICONS[code] ?? '🍽️';
}
