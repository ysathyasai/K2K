"""
Django Admin Configuration for Project Khet2Kitchen (K2K).
Provides rich administrative controls for K2K operations.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from k2k_core.models import (
    User,
    FarmerProfile,
    RetailerProfile,
    MicroHub,
    Crop,
    DemandOrder,
    HarvestSchedule,
    ProduceBatch,
    AIGradingRecord,
    DynamicPricingRecord,
    InputLoan,
    FarmerWallet,
    PayoutSettlement,
    Vehicle,
    TransitRoute,
    RouteWaypoint
)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'phone_number', 'role', 'preferred_language', 'village', 'district')
    list_filter = ('role', 'preferred_language', 'district')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('K2K Role & Contact', {'fields': ('role', 'phone_number', 'preferred_language')}),
        ('Location & Geography', {'fields': ('village', 'district', 'state', 'pincode', 'latitude', 'longitude')}),
    )


@admin.register(FarmerProfile)
class FarmerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'land_size_acres', 'k2k_reliability_score', 'credit_limit', 'current_outstanding_credit')
    search_fields = ('user__username', 'user__phone_number', 'upi_id')


@admin.register(RetailerProfile)
class RetailerProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'business_type', 'gstin', 'user')
    search_fields = ('business_name', 'gstin')


@admin.register(MicroHub)
class MicroHubAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'district', 'capacity_kg', 'cold_storage_available', 'status')
    list_filter = ('cold_storage_available', 'status', 'district')


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'perishability_tier', 'base_msp_price_per_kg', 'market_benchmark_price_per_kg')
    list_filter = ('perishability_tier', 'category')


@admin.register(DemandOrder)
class DemandOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'retailer', 'crop', 'required_quantity_kg', 'fulfilled_quantity_kg', 'locked_unit_price', 'status')
    list_filter = ('status', 'crop', 'required_grade')
    search_fields = ('order_id', 'retailer__username')


@admin.register(HarvestSchedule)
class HarvestScheduleAdmin(admin.ModelAdmin):
    list_display = ('schedule_id', 'farmer', 'crop', 'allocated_quantity_kg', 'scheduled_harvest_date', 'target_hub', 'status')
    list_filter = ('status', 'crop', 'scheduled_harvest_date')


@admin.register(ProduceBatch)
class ProduceBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'farmer', 'crop', 'current_hub', 'initial_quantity_kg', 'accepted_quantity_kg', 'current_status', 'freshness_score')
    list_filter = ('current_status', 'crop')
    search_fields = ('batch_id', 'traceability_hash', 'farmer__username')


@admin.register(AIGradingRecord)
class AIGradingRecordAdmin(admin.ModelAdmin):
    list_display = ('batch', 'final_grade', 'confidence_score', 'requires_manual_review', 'is_manually_reviewed', 'manual_override_grade')
    list_filter = ('final_grade', 'requires_manual_review', 'is_manually_reviewed')


@admin.register(DynamicPricingRecord)
class DynamicPricingRecordAdmin(admin.ModelAdmin):
    list_display = ('batch', 'farmer', 'final_unit_price_per_kg', 'price_floor_enforced', 'total_gross_amount', 'status')
    list_filter = ('price_floor_enforced', 'status')


@admin.register(InputLoan)
class InputLoanAdmin(admin.ModelAdmin):
    list_display = ('loan_id', 'farmer', 'input_type', 'package_name', 'total_loan_amount', 'outstanding_balance', 'status')
    list_filter = ('input_type', 'status')


@admin.register(FarmerWallet)
class FarmerWalletAdmin(admin.ModelAdmin):
    list_display = ('farmer', 'current_balance', 'total_lifetime_earnings', 'total_input_deductions')


@admin.register(PayoutSettlement)
class PayoutSettlementAdmin(admin.ModelAdmin):
    list_display = ('settlement_id', 'farmer', 'gross_produce_revenue', 'input_loan_deduction', 'net_payout_amount', 'status')
    list_filter = ('status', 'payment_channel')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_number', 'driver_name', 'driver_phone', 'max_payload_kg', 'has_cold_chain', 'status')
    list_filter = ('has_cold_chain', 'status')


@admin.register(TransitRoute)
class TransitRouteAdmin(admin.ModelAdmin):
    list_display = ('route_id', 'vehicle', 'priority_urgency_score', 'status')
    list_filter = ('status',)


@admin.register(RouteWaypoint)
class RouteWaypointAdmin(admin.ModelAdmin):
    list_display = ('route', 'hub', 'sequence_order', 'action', 'planned_weight_kg', 'is_completed')
