import { redirect } from 'next/navigation';

/**
 * /checkout base — redirects to hotels page.
 * Active checkout flow uses /checkout/[sessionId] instead.
 */
export default function CheckoutIndex() {
  redirect('/hotels');
}
