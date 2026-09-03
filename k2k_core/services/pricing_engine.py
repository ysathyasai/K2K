"""
Transparent Dynamic Pricing Engine
Calculates price-floor protected offers exposing all variables to the farmer:
Final Price = MAX(MSP Floor, Base Value + Grade Premium + Demand Surge - Logistics Deduction)
"""
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db.models import Sum
from k2k_core.models import (
    ProduceBatch,
    DynamicPricingRecord,
    CommercialGrade,
    DemandOrder,
    DemandOrderStatus,
    BatchStatus
)


class DynamicPricingEngine:

    @classmethod
    def calculate_price_offer(cls, batch: ProduceBatch) -> DynamicPricingRecord:
        """
        Calculates a transparent, price-floor protected purchase offer for a graded batch.
        """
        crop = batch.crop
        grading = getattr(batch, 'grading_record', None)
        effective_grade = grading.effective_grade() if grading else CommercialGrade.GRADE_B

        # 1. Base Value (Benchmark wholesale price per kg)
        base_value = crop.market_benchmark_price_per_kg

        # 2. Grade Premium / Discount
        if effective_grade == CommercialGrade.GRADE_A:
            grade_multiplier = Decimal('1.00') + (crop.grade_a_premium_pct / Decimal('100.00'))
            grade_premium = (base_value * (crop.grade_a_premium_pct / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        elif effective_grade == CommercialGrade.GRADE_B:
            grade_multiplier = Decimal('1.00')
            grade_premium = Decimal('0.00')
        elif effective_grade == CommercialGrade.GRADE_C:
            # Industrial food processing / puree rate
            discount_pct = crop.grade_c_discount_pct / Decimal('100.00')
            grade_multiplier = Decimal('1.00') - discount_pct
            grade_premium = -(base_value * discount_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:  # REJECT
            grade_multiplier = Decimal('0.00')
            grade_premium = -base_value

        # 3. Real-Time Demand Surge Bonus
        # Calculates surge multiplier based on active locked demand from urban retailers
        active_orders = DemandOrder.objects.filter(
            crop=crop,
            status__in=[DemandOrderStatus.PENDING_MATCH, DemandOrderStatus.PARTIALLY_ALLOCATED]
        )
        total_unmet_demand_kg = sum(o.remaining_unmatched_kg() for o in active_orders)
        
        if total_unmet_demand_kg > Decimal('5000.00'):
            # High demand surge: +15% bonus
            demand_surge_bonus = (base_value * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            surge_label = "+15% High Urban Demand Surge"
        elif total_unmet_demand_kg > Decimal('1000.00'):
            # Moderate surge: +8% bonus
            demand_surge_bonus = (base_value * Decimal('0.08')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            surge_label = "+8% Moderate Demand Surge"
        else:
            demand_surge_bonus = Decimal('0.00')
            surge_label = "Standard Demand (No Surge)"

        # 4. Logistics Deduction (Hub to Urban Center transit cost share)
        logistics_deduction = crop.standard_logistics_cost_per_kg

        # 5. Raw Price Calculation
        raw_price_per_kg = (base_value + grade_premium + demand_surge_bonus - logistics_deduction).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 6. Price-Floor Protection (MSP Floor Guarantee)
        msp_floor = crop.base_msp_price_per_kg
        if effective_grade == CommercialGrade.REJECT:
            final_unit_price = Decimal('0.00')
            price_floor_enforced = False
        elif raw_price_per_kg < msp_floor:
            final_unit_price = msp_floor
            price_floor_enforced = True
        else:
            final_unit_price = raw_price_per_kg
            price_floor_enforced = False

        # Total gross amount for the batch
        accepted_kg = batch.accepted_quantity_kg if batch.accepted_quantity_kg is not None else batch.initial_quantity_kg
        total_gross_amount = (final_unit_price * accepted_kg).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Full transparent explanation ledger
        breakdown = {
            "crop_name": crop.name,
            "commercial_grade": effective_grade,
            "base_market_price_per_kg": float(base_value),
            "quality_grade_adjustment_per_kg": float(grade_premium),
            "demand_surge_bonus_per_kg": float(demand_surge_bonus),
            "demand_surge_context": surge_label,
            "logistics_transport_deduction_per_kg": float(logistics_deduction),
            "raw_calculated_rate_per_kg": float(raw_price_per_kg),
            "statutory_msp_price_floor_per_kg": float(msp_floor),
            "price_floor_protection_applied": price_floor_enforced,
            "final_net_offer_per_kg": float(final_unit_price),
            "total_accepted_weight_kg": float(accepted_kg),
            "total_gross_value_rupees": float(total_gross_amount),
            "transparency_guarantee": "K2K guarantees 100% price transparency. No hidden commission or middleman cut."
        }

        # Save record
        pricing_record, _ = DynamicPricingRecord.objects.update_or_create(
            batch=batch,
            defaults={
                'farmer': batch.farmer,
                'base_value_per_kg': base_value,
                'grade_multiplier': grade_multiplier,
                'grade_premium_per_kg': grade_premium,
                'demand_surge_bonus_per_kg': demand_surge_bonus,
                'logistics_deduction_per_kg': logistics_deduction,
                'msp_floor_price_per_kg': msp_floor,
                'price_floor_enforced': price_floor_enforced,
                'final_unit_price_per_kg': final_unit_price,
                'total_gross_amount': total_gross_amount,
                'pricing_breakdown': breakdown,
                'status': DynamicPricingRecord.OfferStatus.OFFERED,
            }
        )

        batch.current_status = BatchStatus.PRICE_OFFERED
        batch.save()

        return pricing_record

    @classmethod
    def accept_price_offer(cls, pricing_record: DynamicPricingRecord) -> DynamicPricingRecord:
        """
        Farmer accepts dynamic price offer.
        """
        pricing_record.status = DynamicPricingRecord.OfferStatus.ACCEPTED
        pricing_record.accepted_at = timezone.now()
        pricing_record.save()

        batch = pricing_record.batch
        batch.current_status = BatchStatus.PRICE_ACCEPTED
        batch.save()

        return pricing_record
