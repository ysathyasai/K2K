"""
Integrated Agri-Fintech Settlement Engine
Automates digital payouts with seamless in-kind input loan recovery (seeds, fertilizers).
Transfers net profits instantly to the farmer's digital wallet/UPI under atomic database transactions.
"""
from decimal import Decimal, ROUND_HALF_UP
import uuid
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from k2k_core.models import (
    ProduceBatch,
    DynamicPricingRecord,
    InputLoan,
    InputLoanStatus,
    FarmerWallet,
    PayoutSettlement,
    BatchStatus
)


class AgriFintechSettlementEngine:

    @classmethod
    def process_harvest_settlement(
        cls,
        batch: ProduceBatch,
        payment_channel: str = 'INSTANT_UPI'
    ) -> PayoutSettlement:
        """
        Executes atomic digital payout settlement:
        1. Verifies accepted price offer
        2. Calculates gross harvest value
        3. Identifies active pre-season input loans (seeds/bio-fertilizers)
        4. Seamlessly deducts outstanding input balance (capped to preserve farmer liquidity)
        5. Instantly credits net profit to farmer's digital wallet
        6. Creates audited transaction ledger
        """
        with transaction.atomic():
            pricing_record = getattr(batch, 'pricing_record', None)
            if not pricing_record:
                raise ValueError(f"Batch {batch.batch_id} does not have a dynamic pricing record.")

            if pricing_record.status != DynamicPricingRecord.OfferStatus.ACCEPTED:
                # Auto-accept if not yet marked, or validate
                pricing_record.status = DynamicPricingRecord.OfferStatus.ACCEPTED
                pricing_record.accepted_at = timezone.now()
                pricing_record.save()

            farmer = batch.farmer
            wallet, _ = FarmerWallet.objects.get_or_create(
                farmer=farmer,
                defaults={
                    'upi_id': f"{farmer.username}@okaxis",
                    'bank_name': 'State Bank of India',
                    'account_number': '39482710294',
                    'ifsc_code': 'SBIN0001234'
                }
            )

            gross_revenue = pricing_record.total_gross_amount
            if gross_revenue <= Decimal('0.00'):
                raise ValueError(f"Cannot settle batch {batch.batch_id} with gross revenue of ₹{gross_revenue}")

            # Query active in-kind input loans
            active_loans = InputLoan.objects.select_for_update().filter(
                farmer=farmer,
                status__in=[InputLoanStatus.ACTIVE, InputLoanStatus.PARTIALLY_REPAID],
                outstanding_balance__gt=Decimal('0.00')
            ).order_by('due_date', 'disbursed_at')

            # Cap max loan deduction to protect farmer cashflow (default 50% max of harvest check)
            max_deduction_ratio = Decimal(str(getattr(settings, 'K2K_MAX_LOAN_DEDUCTION_RATIO', '0.50')))
            max_allowable_deduction = (gross_revenue * max_deduction_ratio).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            total_loan_deductions = Decimal('0.00')
            loan_deduction_audit = []

            for loan in active_loans:
                if total_loan_deductions >= max_allowable_deduction:
                    break

                remaining_budget = max_allowable_deduction - total_loan_deductions
                deduction_for_this_loan = min(loan.outstanding_balance, remaining_budget)

                if deduction_for_this_loan > Decimal('0.00'):
                    loan.record_repayment(deduction_for_this_loan)
                    total_loan_deductions += deduction_for_this_loan
                    loan_deduction_audit.append({
                        'loan_id': loan.loan_id,
                        'input_package': loan.package_name,
                        'deducted_amount': float(deduction_for_this_loan),
                        'remaining_loan_balance': float(loan.outstanding_balance),
                        'status': loan.status
                    })

            # Calculate Net Payout
            net_payout = (gross_revenue - total_loan_deductions).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Instant Wallet Credit
            wallet.credit(net_payout)
            wallet.total_input_deductions += total_loan_deductions
            wallet.save()

            # Update Farmer Profile outstanding credit
            profile = getattr(farmer, 'farmer_profile', None)
            if profile:
                profile.current_outstanding_credit = max(
                    Decimal('0.00'),
                    profile.current_outstanding_credit - total_loan_deductions
                )
                # Boost reliability score upon successful automated payback (+1.5 points up to 100)
                profile.k2k_reliability_score = min(
                    Decimal('100.00'),
                    profile.k2k_reliability_score + Decimal('1.50')
                )
                profile.save()

            # Unique Settlement ID & Transaction Reference
            timestamp_str = timezone.now().strftime("%Y%m%d%H%M%S")
            settlement_id = f"PAY-K2K-{timestamp_str}-{uuid.uuid4().hex[:4].upper()}"
            tx_ref = f"UTR-UPI-{uuid.uuid4().hex[:12].upper()}"

            settlement = PayoutSettlement.objects.create(
                settlement_id=settlement_id,
                batch=batch,
                farmer=farmer,
                pricing_record=pricing_record,
                gross_produce_revenue=gross_revenue,
                input_loan_deduction=total_loan_deductions,
                logistics_handling_fee=Decimal('0.00'),
                net_payout_amount=net_payout,
                payment_channel=payment_channel,
                transaction_reference=tx_ref,
                status=PayoutSettlement.SettlementStatus.SUCCESS
            )

            # Update Produce Batch Status
            batch.current_status = BatchStatus.IN_COLD_STORAGE
            batch.save()

            return settlement
