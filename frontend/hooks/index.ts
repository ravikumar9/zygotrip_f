/**
 * Aggregated hook exports — re-exports from dedicated hook files.
 * Import from specific files for better tree-shaking, or from here for convenience.
 */

// Hotels
export { useHotels, useHotelSearch } from './useHotels';
export { useHotelDetail, useAvailability } from './useHotelDetail';

// Bookings
export {
  useMyBookings,
  useBookingDetail,
  useBookingContext,
  useCreateBookingContext,
  useCreateBooking,
  useCancelBooking,
} from './useBooking';

// Wallet
export { useWalletBalance, useWalletTransactions, useTopUp, useOwnerWallet } from './useWallet';
