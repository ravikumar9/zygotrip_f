/**
 * Checkout Service — Production checkout flow API client.
 *
 * Endpoints:
 *   POST /checkout/start/           → Create session
 *   GET  /checkout/{id}/            → Get session
 *   POST /checkout/{id}/guest-details/ → Submit guest info
 *   GET  /checkout/{id}/payment-options/ → Payment gateways
 *   POST /checkout/{id}/pay/        → Initiate payment
 *   POST /checkout/{id}/callback/   → Payment callback
 */
import api from './api';
import type {
  CheckoutSession,
  CheckoutPaymentOptions,
  CheckoutPaymentResult,
  CheckoutStartRequest,
  CheckoutGuestDetails,
  CheckoutPayRequest,
} from '@/types/checkout';

function unwrap<T>(data: unknown): T {
  if (data && typeof data === 'object' && 'success' in data) {
    const d = data as { success: boolean; data: T; error?: { message: string } };
    if (!d.success) throw new Error(String(d.error?.message ?? 'API error'));
    return d.data;
  }
  return data as T;
}

function generateIdempotencyKey(): string {
  return `chk-${Date.now()}-${Math.random().toString(36).substring(2, 14)}`;
}

export const checkoutService = {
  /** Create a checkout session (hold inventory + snapshot price) */
  async startCheckout(payload: CheckoutStartRequest): Promise<CheckoutSession> {
    const { data } = await api.post('/checkout/start/', payload);
    return unwrap<CheckoutSession>(data);
  },

  /** Get current session state */
  async getSession(sessionId: string): Promise<CheckoutSession> {
    const { data } = await api.get(`/checkout/${sessionId}/`);
    return unwrap<CheckoutSession>(data);
  },

  /** Submit guest details */
  async submitGuestDetails(
    sessionId: string,
    guest: CheckoutGuestDetails,
  ): Promise<CheckoutSession> {
    const { data } = await api.post(`/checkout/${sessionId}/guest-details/`, guest);
    return unwrap<CheckoutSession>(data);
  },

  /** Get available payment options */
  async getPaymentOptions(sessionId: string): Promise<CheckoutPaymentOptions> {
    const { data } = await api.get(`/checkout/${sessionId}/payment-options/`);
    return unwrap<CheckoutPaymentOptions>(data);
  },

  /** Initiate payment */
  async pay(
    sessionId: string,
    gateway: string,
    idempotencyKey?: string,
  ): Promise<CheckoutPaymentResult> {
    const { data } = await api.post(`/checkout/${sessionId}/pay/`, {
      gateway,
      idempotency_key: idempotencyKey || generateIdempotencyKey(),
    });
    return unwrap<CheckoutPaymentResult>(data);
  },

  /** Initiate payment (payload variant) */
  async initiatePayment(
    sessionId: string,
    payload: CheckoutPayRequest,
  ): Promise<CheckoutPaymentResult> {
    return this.pay(
      sessionId,
      payload.gateway,
      payload.idempotency_key,
    );
  },

  /** Payment callback (after external gateway redirect) */
  async paymentCallback(
    sessionId: string,
    attemptId: string,
    status: 'success' | 'failed',
    gatewayResponse?: Record<string, unknown>,
    failureReason?: string,
  ): Promise<CheckoutPaymentResult> {
    const { data } = await api.post(`/checkout/${sessionId}/callback/`, {
      attempt_id: attemptId,
      status,
      gateway_response: gatewayResponse || {},
      failure_reason: failureReason || '',
    });
    return unwrap<CheckoutPaymentResult>(data);
  },
};
