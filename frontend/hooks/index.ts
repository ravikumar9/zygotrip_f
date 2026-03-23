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
export { useWalletBalance, useWalletTransactions, useOwnerWallet } from './useWallet';

// Currency
export { useCurrency } from '../contexts/CurrencyContext';
export { useFormatPrice } from './useFormatPrice';

// Utilities
export { useDebounce } from './useDebounce';
export { useInfiniteScroll } from './useInfiniteScroll';
