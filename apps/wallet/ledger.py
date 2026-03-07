"""
System 6 — Double-Entry Financial Ledger.

Implements a proper accounting system with:
  - Chart of Accounts (Account model with 5 account types)
  - Journal Entries (header + line items that MUST balance)
  - Recording helpers for OTA transactions
  - Trial Balance query

Design:
  Every financial event creates a JournalEntry with 2+ LedgerEntries.
  The sum of all debits MUST equal the sum of all credits per JournalEntry.
  Accounts follow standard accounting types: Asset, Liability, Equity, Revenue, Expense.
"""
import uuid
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel


# ============================================================================
# CHART OF ACCOUNTS
# ============================================================================

class Account(TimeStampedModel):
    """
    Chart of Accounts.

    Standard account types:
      - Asset:    Cash, bank, receivables, float (debit-normal)
      - Liability: Payables, customer deposits (credit-normal)
      - Equity:   Retained earnings, capital (credit-normal)
      - Revenue:  Commission, service fees (credit-normal)
      - Expense:  Gateway fees, refund costs (debit-normal)
    """
    TYPE_ASSET = 'asset'
    TYPE_LIABILITY = 'liability'
    TYPE_EQUITY = 'equity'
    TYPE_REVENUE = 'revenue'
    TYPE_EXPENSE = 'expense'

    TYPE_CHOICES = [
        (TYPE_ASSET, 'Asset'),
        (TYPE_LIABILITY, 'Liability'),
        (TYPE_EQUITY, 'Equity'),
        (TYPE_REVENUE, 'Revenue'),
        (TYPE_EXPENSE, 'Expense'),
    ]

    # Pre-defined system account codes
    CASH_RECEIVED = 'CASH_RECV'          # Asset: money from gateways
    CUSTOMER_DEPOSITS = 'CUST_DEP'       # Liability: customer pre-paid balance
    OWNER_PAYABLE = 'OWNER_PAY'          # Liability: amounts owed to owners
    COMMISSION_REVENUE = 'COMM_REV'      # Revenue: platform commission earned
    SERVICE_FEE_REVENUE = 'SVC_FEE'      # Revenue: service fee earned
    GATEWAY_FEE_EXPENSE = 'GW_FEE'       # Expense: gateway processing fees
    REFUND_EXPENSE = 'REFUND_EXP'        # Expense: refund costs
    WALLET_FLOAT = 'WALLET_FLOAT'        # Asset: wallet balances held
    TAX_PAYABLE = 'TAX_PAY'              # Liability: collected taxes
    SUSPENSE = 'SUSPENSE'                # Asset: unclassified amounts

    code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=15, choices=TYPE_CHOICES, db_index=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
        help_text='Parent account for hierarchical chart',
    )
    description = models.TextField(blank=True)
    is_system = models.BooleanField(
        default=False,
        help_text='System-managed accounts cannot be deleted',
    )

    class Meta:
        app_label = 'wallet'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name} ({self.get_account_type_display()})"

    @property
    def is_debit_normal(self):
        """Asset & Expense accounts increase with debits."""
        return self.account_type in (self.TYPE_ASSET, self.TYPE_EXPENSE)


# ============================================================================
# JOURNAL ENTRIES
# ============================================================================

class JournalEntry(TimeStampedModel):
    """
    Header for a balanced accounting entry.
    Each JournalEntry has 2+ LedgerEntries whose debits == credits.
    """
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    date = models.DateField(default=timezone.now, db_index=True)
    reference = models.CharField(
        max_length=200, blank=True, db_index=True,
        help_text='Booking ID, payment txn ID, or descriptive reference',
    )
    description = models.CharField(max_length=500)
    entry_type = models.CharField(
        max_length=30, db_index=True,
        help_text='E.g. payment_received, refund_issued, commission_earned',
    )
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reversal_of',
    )

    class Meta:
        app_label = 'wallet'
        ordering = ['-date', '-created_at']
        verbose_name_plural = 'Journal Entries'
        indexes = [
            models.Index(fields=['entry_type', 'date']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        return f"JE-{self.uid.hex[:8]} {self.entry_type}: {self.description[:60]}"

    def clean(self):
        """Validate that debits == credits."""
        entries = self.entries.all()
        if entries.exists():
            total_debit = sum(e.debit for e in entries)
            total_credit = sum(e.credit for e in entries)
            if total_debit != total_credit:
                raise ValidationError(
                    f"Journal entry unbalanced: debit={total_debit}, credit={total_credit}"
                )


class LedgerEntry(TimeStampedModel):
    """
    Individual line item within a JournalEntry.
    Each line debits or credits exactly one Account.
    """
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT,
        related_name='entries',
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT,
        related_name='ledger_entries',
    )
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    narration = models.CharField(max_length=300, blank=True)

    class Meta:
        app_label = 'wallet'
        indexes = [
            models.Index(fields=['account', 'journal_entry']),
        ]

    def __str__(self):
        if self.debit > 0:
            return f"DR {self.account.code} ₹{self.debit}"
        return f"CR {self.account.code} ₹{self.credit}"

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("A ledger entry must be either debit or credit, not both.")
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("A ledger entry must have a non-zero debit or credit.")


# ============================================================================
# RECORDING HELPERS
# ============================================================================

def _get_or_create_account(code, name, account_type):
    """Get or create a system account by code."""
    account, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'account_type': account_type,
            'is_system': True,
        },
    )
    return account


@transaction.atomic
def record_payment_received(booking_ref, amount, gateway_fee=Decimal('0'), description=''):
    """
    Record customer payment received through a gateway.

    Debits: Cash Received (asset +)
    Credits: Customer Deposits (liability +)
    If gateway fee > 0, also debits Gateway Fee Expense.
    """
    amount = Decimal(str(amount))
    gateway_fee = Decimal(str(gateway_fee))

    cash_acct = _get_or_create_account(
        Account.CASH_RECEIVED, 'Cash Received', Account.TYPE_ASSET,
    )
    deposit_acct = _get_or_create_account(
        Account.CUSTOMER_DEPOSITS, 'Customer Deposits', Account.TYPE_LIABILITY,
    )

    je = JournalEntry.objects.create(
        reference=booking_ref,
        description=description or f'Payment received for {booking_ref}',
        entry_type='payment_received',
    )

    entries = [
        LedgerEntry(journal_entry=je, account=cash_acct, debit=amount, narration=f'Gateway receipt for {booking_ref}'),
        LedgerEntry(journal_entry=je, account=deposit_acct, credit=amount, narration=f'Customer deposit for {booking_ref}'),
    ]

    if gateway_fee > 0:
        fee_acct = _get_or_create_account(
            Account.GATEWAY_FEE_EXPENSE, 'Gateway Processing Fees', Account.TYPE_EXPENSE,
        )
        # Adjust cash received down by fee; book fee as expense
        entries[0].debit = amount - gateway_fee
        entries.append(
            LedgerEntry(journal_entry=je, account=fee_acct, debit=gateway_fee, narration=f'Gateway fee for {booking_ref}'),
        )

    LedgerEntry.objects.bulk_create(entries)
    return je


@transaction.atomic
def record_commission_earned(booking_ref, total_amount, commission_amount, description=''):
    """
    Record commission earned on a confirmed booking.
    Called when booking moves to confirmed state.

    Debits: Customer Deposits (liability -, reducing what we owe customer)
    Credits: Owner Payable (liability +, we now owe the owner)
             Commission Revenue (revenue +, our cut)
    """
    total_amount = Decimal(str(total_amount))
    commission_amount = Decimal(str(commission_amount))
    owner_share = total_amount - commission_amount

    deposit_acct = _get_or_create_account(
        Account.CUSTOMER_DEPOSITS, 'Customer Deposits', Account.TYPE_LIABILITY,
    )
    owner_acct = _get_or_create_account(
        Account.OWNER_PAYABLE, 'Owner Payable', Account.TYPE_LIABILITY,
    )
    comm_acct = _get_or_create_account(
        Account.COMMISSION_REVENUE, 'Commission Revenue', Account.TYPE_REVENUE,
    )

    je = JournalEntry.objects.create(
        reference=booking_ref,
        description=description or f'Commission earned on {booking_ref}',
        entry_type='commission_earned',
    )
    LedgerEntry.objects.bulk_create([
        LedgerEntry(journal_entry=je, account=deposit_acct, debit=total_amount, narration='Release customer deposit'),
        LedgerEntry(journal_entry=je, account=owner_acct, credit=owner_share, narration='Owner share payable'),
        LedgerEntry(journal_entry=je, account=comm_acct, credit=commission_amount, narration='Platform commission'),
    ])
    return je


@transaction.atomic
def record_refund_issued(booking_ref, refund_amount, description=''):
    """
    Record a refund paid back to customer.

    Debits: Customer Deposits (liability -, we owe less)
            OR Refund Expense (if booking was already earned)
    Credits: Cash Received (asset -, money going out)
    """
    refund_amount = Decimal(str(refund_amount))

    refund_acct = _get_or_create_account(
        Account.REFUND_EXPENSE, 'Refund Costs', Account.TYPE_EXPENSE,
    )
    cash_acct = _get_or_create_account(
        Account.CASH_RECEIVED, 'Cash Received', Account.TYPE_ASSET,
    )

    je = JournalEntry.objects.create(
        reference=booking_ref,
        description=description or f'Refund issued for {booking_ref}',
        entry_type='refund_issued',
    )
    LedgerEntry.objects.bulk_create([
        LedgerEntry(journal_entry=je, account=refund_acct, debit=refund_amount, narration='Refund cost'),
        LedgerEntry(journal_entry=je, account=cash_acct, credit=refund_amount, narration='Cash out for refund'),
    ])
    return je


@transaction.atomic
def record_owner_payout(owner_ref, amount, description=''):
    """
    Record payout to property owner.

    Debits: Owner Payable (liability -, we no longer owe them)
    Credits: Cash Received (asset -, money leaving platform)
    """
    amount = Decimal(str(amount))

    owner_acct = _get_or_create_account(
        Account.OWNER_PAYABLE, 'Owner Payable', Account.TYPE_LIABILITY,
    )
    cash_acct = _get_or_create_account(
        Account.CASH_RECEIVED, 'Cash Received', Account.TYPE_ASSET,
    )

    je = JournalEntry.objects.create(
        reference=owner_ref,
        description=description or f'Owner payout {owner_ref}',
        entry_type='owner_payout',
    )
    LedgerEntry.objects.bulk_create([
        LedgerEntry(journal_entry=je, account=owner_acct, debit=amount, narration='Clear owner payable'),
        LedgerEntry(journal_entry=je, account=cash_acct, credit=amount, narration='Bank transfer to owner'),
    ])
    return je


@transaction.atomic
def record_wallet_topup(user_ref, amount, description=''):
    """
    Record wallet top-up by customer.

    Debits: Cash Received (asset +, money in)
    Credits: Wallet Float (asset + but effectively liability — we hold it for user)
    """
    amount = Decimal(str(amount))

    cash_acct = _get_or_create_account(
        Account.CASH_RECEIVED, 'Cash Received', Account.TYPE_ASSET,
    )
    float_acct = _get_or_create_account(
        Account.WALLET_FLOAT, 'Wallet Float', Account.TYPE_LIABILITY,
    )

    je = JournalEntry.objects.create(
        reference=user_ref,
        description=description or f'Wallet top-up by {user_ref}',
        entry_type='wallet_topup',
    )
    LedgerEntry.objects.bulk_create([
        LedgerEntry(journal_entry=je, account=cash_acct, debit=amount, narration='Payment received'),
        LedgerEntry(journal_entry=je, account=float_acct, credit=amount, narration='Wallet balance credited'),
    ])
    return je


# ============================================================================
# TRIAL BALANCE
# ============================================================================

def trial_balance(as_of_date=None):
    """
    Compute trial balance: sum of all debits and credits per account.

    Returns dict:
        {
            'accounts': [
                {'code': 'CASH_RECV', 'name': ..., 'type': ..., 'debit': Decimal, 'credit': Decimal, 'balance': Decimal},
                ...
            ],
            'total_debit': Decimal,
            'total_credit': Decimal,
            'is_balanced': bool,
            'as_of_date': date,
        }
    """
    from django.db.models import Sum, Q

    filters = Q()
    if as_of_date:
        filters &= Q(journal_entry__date__lte=as_of_date)

    accounts = Account.objects.annotate(
        total_debit=Sum('ledger_entries__debit', filter=filters, default=Decimal('0')),
        total_credit=Sum('ledger_entries__credit', filter=filters, default=Decimal('0')),
    ).values('code', 'name', 'account_type', 'total_debit', 'total_credit')

    result_accounts = []
    grand_debit = Decimal('0')
    grand_credit = Decimal('0')

    for acct in accounts:
        dr = acct['total_debit'] or Decimal('0')
        cr = acct['total_credit'] or Decimal('0')
        balance = dr - cr
        result_accounts.append({
            'code': acct['code'],
            'name': acct['name'],
            'type': acct['account_type'],
            'debit': dr,
            'credit': cr,
            'balance': balance,
        })
        grand_debit += dr
        grand_credit += cr

    return {
        'accounts': result_accounts,
        'total_debit': grand_debit,
        'total_credit': grand_credit,
        'is_balanced': grand_debit == grand_credit,
        'as_of_date': as_of_date or timezone.now().date(),
    }
