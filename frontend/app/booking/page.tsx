import { redirect } from 'next/navigation';

/**
 * Legacy /booking route — redirects to hotels page.
 * The active booking flow uses /booking/[context_uuid] instead.
 */
export default function BookingPage() {
  redirect('/hotels');
}
