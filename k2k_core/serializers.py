"""
Django REST Framework Serializers for Project Khet2Kitchen (K2K).
"""
from rest_framework import serializers
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
    RouteWaypoint,
    CommercialGrade
)


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role', 'phone_number', 'preferred_language', 'village', 'district']


class FarmerProfileSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    class Meta:
        model = FarmerProfile
        fields = '__all__'


class RetailerProfileSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    class Meta:
        model = RetailerProfile
        fields = '__all__'


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = '__all__'


class MicroHubSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    class Meta:
        model = MicroHub
        fields = '__all__'


class DemandOrderSerializer(serializers.ModelSerializer):
    retailer_name = serializers.CharField(source='retailer.get_full_name', read_only=True)
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    remaining_unmatched_kg = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = DemandOrder
        fields = '__all__'


class HarvestScheduleSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    target_hub_name = serializers.CharField(source='target_hub.name', read_only=True)

    class Meta:
        model = HarvestSchedule
        fields = '__all__'


class AIGradingRecordSerializer(serializers.ModelSerializer):
    effective_grade = serializers.CharField(read_only=True)
    reviewer_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)

    class Meta:
        model = AIGradingRecord
        fields = '__all__'


class DynamicPricingRecordSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)

    class Meta:
        model = DynamicPricingRecord
        fields = '__all__'


class ProduceBatchSerializer(serializers.ModelSerializer):
    crop_name = serializers.CharField(source='crop.name', read_only=True)
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)
    hub_name = serializers.CharField(source='current_hub.name', read_only=True)
    grading_record = AIGradingRecordSerializer(read_only=True)
    pricing_record = DynamicPricingRecordSerializer(read_only=True)

    class Meta:
        model = ProduceBatch
        fields = '__all__'


class InputLoanSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)

    class Meta:
        model = InputLoan
        fields = '__all__'


class FarmerWalletSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)

    class Meta:
        model = FarmerWallet
        fields = '__all__'


class PayoutSettlementSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)
    batch_code = serializers.CharField(source='batch.batch_id', read_only=True)

    class Meta:
        model = PayoutSettlement
        fields = '__all__'


class RouteWaypointSerializer(serializers.ModelSerializer):
    hub_name = serializers.CharField(source='hub.name', read_only=True)
    batch_ids = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='batch_id',
        source='batches'
    )

    class Meta:
        model = RouteWaypoint
        fields = '__all__'


class TransitRouteSerializer(serializers.ModelSerializer):
    vehicle_number = serializers.CharField(source='vehicle.vehicle_number', read_only=True)
    driver_name = serializers.CharField(source='vehicle.driver_name', read_only=True)
    waypoints = RouteWaypointSerializer(many=True, read_only=True)

    class Meta:
        model = TransitRoute
        fields = '__all__'


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'


# ==============================================================================
# OPERATION & ACTION SERIALIZERS
# ==============================================================================

class AIGradingScanRequestSerializer(serializers.Serializer):
    batch_id = serializers.CharField(required=True, help_text="Unique Batch Code e.g. K2K-2026-TOM-B89E23")
    image = serializers.ImageField(required=False, help_text="Smartphone crop scan photograph")
    simulation_size_uniformity = serializers.FloatField(required=False, min_value=0, max_value=100)
    simulation_color_uniformity = serializers.FloatField(required=False, min_value=0, max_value=100)
    simulation_surface_defect_pct = serializers.FloatField(required=False, min_value=0, max_value=100)
    simulation_confidence_score = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)


class AIGradingManualReviewSerializer(serializers.Serializer):
    grading_id = serializers.UUIDField(required=True)
    override_grade = serializers.ChoiceField(choices=CommercialGrade.choices, required=True)
    reviewer_notes = serializers.CharField(required=False, allow_blank=True, default="Manual audit verification passed.")


class DynamicPricingCalculateSerializer(serializers.Serializer):
    batch_id = serializers.CharField(required=True)


class DynamicPricingAcceptSerializer(serializers.Serializer):
    batch_id = serializers.CharField(required=True)


class AgriFintechPayoutSerializer(serializers.Serializer):
    batch_id = serializers.CharField(required=True)
    payment_channel = serializers.CharField(default='INSTANT_UPI')


class VoiceAssistantCommandSerializer(serializers.Serializer):
    farmer_phone = serializers.CharField(required=False, default="+919876543210")
    voice_transcript = serializers.CharField(required=True, help_text="Speech-to-text string in regional language or English")
    language = serializers.CharField(default='hi', help_text="Language code: hi, mr, te, ta, kn, en")
