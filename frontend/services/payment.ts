/**
 * Payment Service — Production gateway integration.
 * Connects to Django Payment API v1 endpoints.
 */
import api from './api';

export interface PaymentGateway {
  name: string;
  display_name: string;
  available: boolean;
  wallet_balance?: string;
  sufficient_balance?: boolean;
}

export interface PaymentInitiateRequest {
  booking_uuid: string;
  gateway: 'wallet' | 'cashfree' | 'stripe' | 'paytm_upi';
  idempotency_key?: string;
}

export interface PaymentInitiateResponse {
  transaction_id: string;
  gateway: string;
  amount: string;
  booking_uuid: string;
  status: string;
  // Cashfree-specific
  payment_session_id?: string;
  cf_order_id?: string;
  order_id?: string;
  environment?: string;
  // Stripe-specific
  payment_url?: string;
  session_id?: string;
  // Paytm-specific
  txn_token?: string;
  mid?: string;
  callback_url?: string;
  // Wallet
  instant?: boolean;
  idempotent?: boolean;
}

export interface PaymentStatusResponse {
  transaction_id: string;
  gateway: string;
  amount: string;
  status: string;
  booking_uuid: string;
  booking_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface AvailableGatewaysResponse {
  booking_uuid: string;
  amount: string;
  gateways: PaymentGateway[];
}

function generateIdempotencyKey(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 14)}`;
}

export const paymentService = {
  /**
   * Get available payment gateways for a booking.
   */
  async getAvailableGateways(bookingUuid: string): Promise<AvailableGatewaysResponse> {
    const res = await api.get<{ success: boolean; data: AvailableGatewaysResponse }>(
      `/payment/gateways/${bookingUuid}/`
    );
    return res.data.data;
  },

  /**
   * Initiate a payment. Returns gateway-specific data for frontend completion.
   */
  async initiatePayment(
    bookingUuid: string,
    gateway: PaymentInitiateRequest['gateway'],
  ): Promise<PaymentInitiateResponse> {
    const res = await api.post<{ success: boolean; data: PaymentInitiateResponse }>(
      '/payment/initiate/',
      {
        booking_uuid: bookingUuid,
        gateway,
        idempotency_key: generateIdempotencyKey(),
      },
    );
    return res.data.data;
  },

  /**
   * Check payment status. Optionally verify with gateway.
   */
  async getPaymentStatus(transactionId: string, verify = false): Promise<PaymentStatusResponse> {
    const params = verify ? '?verify=true' : '';
    const res = await api.get<{ success: boolean; data: PaymentStatusResponse }>(
      `/payment/status/${transactionId}/${params}`
    );
    return res.data.data;
  },

  /**
   * Poll payment status until terminal state or max attempts.
   */
  async pollPaymentStatus(
    transactionId: string,
    onUpdate: (status: PaymentStatusResponse) => void,
    maxAttempts = 30,
    intervalMs = 3000,
  ): Promise<PaymentStatusResponse> {
    let attempts = 0;
    return new Promise((resolve, reject) => {
      const poll = async () => {
        attempts++;
        try {
          const status = await this.getPaymentStatus(transactionId, attempts % 5 === 0);
          onUpdate(status);

          if (['success', 'failed', 'cancelled', 'refunded'].includes(status.status)) {
            resolve(status);
            return;
          }

          if (attempts >= maxAttempts) {
            resolve(status); // Return last known status
            return;
          }

          setTimeout(poll, intervalMs);
        } catch (err) {
          if (attempts >= maxAttempts) {
            reject(err);
          } else {
            setTimeout(poll, intervalMs);
          }
        }
      };
      poll();
    });
  },
};
