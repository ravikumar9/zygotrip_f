import { redirect } from 'next/navigation';

/**
 * /account/register → customer (traveller) registration only.
 * Vendor registration (property, cab, bus, tour) lives at /list-property.
 */
export default function RegisterLandingPage() {
  redirect('/account/register/customer');
}
