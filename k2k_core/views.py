"""
API Views for Project Khet2Kitchen (K2K) Intelligence Engine.
Implements scalable Django REST Framework endpoints.
"""
from decimal import Decimal
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count, Q

from k2k_core.models import (
    User,
    UserRole,
    MicroHub,
    Crop,
    DemandOrder,
    DemandOrderStatus,
    HarvestSchedule,
    ProduceBatch,
    AIGradingRecord,
    DynamicPricingRecord,
    InputLoan,
    FarmerWallet,
    PayoutSettlement,
    Vehicle,
    TransitRoute,
    BatchStatus,
    CommercialGrade,
    CropPerishabilityTier
)
from k2k_core.serializers import (
    ProduceBatchSerializer,
    AIGradingRecordSerializer,
    DynamicPricingRecordSerializer,
    PayoutSettlementSerializer,
    TransitRouteSerializer,
    DemandOrderSerializer,
    CropSerializer,
    MicroHubSerializer,
    HarvestScheduleSerializer,
    FarmerWalletSerializer,
    AIGradingScanRequestSerializer,
    AIGradingManualReviewSerializer,
    DynamicPricingCalculateSerializer,
    DynamicPricingAcceptSerializer,
    AgriFintechPayoutSerializer,
    VoiceAssistantCommandSerializer
)
from k2k_core.services import (
    AIGradingEngine,
    DynamicPricingEngine,
    AgriFintechSettlementEngine,
    DynamicRoutingEngine,
    WeatherIntelligenceEngine,
    VoiceAssistantIntelligenceEngine
)


# ==============================================================================
# 1. COMPUTER VISION AI GRADING ENDPOINTS
# ==============================================================================

class AIGradingScanView(APIView):
    """
    POST /api/v1/grading/scan/
    Accepts smartphone crop scans at village micro-hubs.
    Evaluates: size uniformity, color uniformity, surface defect %.
    Returns Commercial Grade & Confidence Score with Human-in-the-Loop fallback if confidence < 0.82.
    """
    def post(self, request):
        serializer = AIGradingScanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch_id = serializer.validated_data['batch_id']
        batch = get_object_or_404(ProduceBatch, batch_id=batch_id)

        # Simulation or image upload
        image_file = serializer.validated_data.get('image')
        sim_params = None
        if not image_file and ('simulation_confidence_score' in serializer.validated_data or 'simulation_size_uniformity' in serializer.validated_data):
            sim_params = {
                'size_uniformity': serializer.validated_data.get('simulation_size_uniformity', 88.0),
                'color_uniformity': serializer.validated_data.get('simulation_color_uniformity', 90.0),
                'surface_defect_pct': serializer.validated_data.get('simulation_surface_defect_pct', 4.0),
                'confidence_score': serializer.validated_data.get('simulation_confidence_score', 0.910),
            }

        grading_record = AIGradingEngine.analyze_crop_scan(
            batch=batch,
            image_file=image_file,
            simulation_params=sim_params
        )

        response_data = {
            "status": "FLAGGED_FOR_MANUAL_REVIEW" if grading_record.requires_manual_review else "SUCCESS",
            "message": "AI Confidence is below threshold (0.820). Forwarded to Hub Manager for manual audit." if grading_record.requires_manual_review else "Crop successfully graded by K2K AI Engine.",
            "batch_id": batch.batch_id,
            "crop": batch.crop.name,
            "grading": AIGradingRecordSerializer(grading_record).data,
            "human_in_the_loop_required": grading_record.requires_manual_review,
            "next_recommended_step": "Awaiting Hub Manager Review" if grading_record.requires_manual_review else "Proceed to Dynamic Pricing"
        }

        http_status = status.HTTP_202_ACCEPTED if grading_record.requires_manual_review else status.HTTP_200_OK
        return Response(response_data, status=http_status)


class AIGradingManualReviewView(APIView):
    """
    POST /api/v1/grading/manual-review/
    Auditing endpoint for Hub Managers to review flagged scans and sign off or override grades.
    """
    def post(self, request):
        serializer = AIGradingManualReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        grading_id = serializer.validated_data['grading_id']
        override_grade = serializer.validated_data['override_grade']
        reviewer_notes = serializer.validated_data.get('reviewer_notes', '')

        grading_record = get_object_or_404(AIGradingRecord, grading_id=grading_id)
        reviewer = request.user if request.user.is_authenticated else None

        updated_record = AIGradingEngine.apply_manual_override(
            grading_record=grading_record,
            reviewer=reviewer,
            override_grade=override_grade,
            reviewer_notes=reviewer_notes
        )

        return Response({
            "status": "OVERRIDE_CONFIRMED",
            "message": f"Grade finalized to {override_grade} by Hub Manager.",
            "batch_id": updated_record.batch.batch_id,
            "effective_grade": updated_record.effective_grade(),
            "grading": AIGradingRecordSerializer(updated_record).data
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 2. TRANSPARENT DYNAMIC PRICING ENDPOINTS
# ==============================================================================

class DynamicPricingCalculateView(APIView):
    """
    POST /api/v1/pricing/calculate/
    Calculates a price-floor protected purchase offer.
    Variables exposed: Base Value + Grade Premium + Demand Surge - Logistics Deductions.
    Strictly bounded by statutory MSP floor.
    """
    def post(self, request):
        serializer = DynamicPricingCalculateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch_id = serializer.validated_data['batch_id']
        batch = get_object_or_404(ProduceBatch, batch_id=batch_id)

        pricing_record = DynamicPricingEngine.calculate_price_offer(batch)

        return Response({
            "status": "OFFER_CALCULATED",
            "batch_id": batch.batch_id,
            "farmer": batch.farmer.get_full_name() or batch.farmer.username,
            "pricing_record_id": str(pricing_record.pricing_id),
            "final_unit_price_per_kg": float(pricing_record.final_unit_price_per_kg),
            "total_gross_amount": float(pricing_record.total_gross_amount),
            "price_floor_enforced": pricing_record.price_floor_enforced,
            "itemized_transparency_breakdown": pricing_record.pricing_breakdown
        }, status=status.HTTP_200_OK)


class DynamicPricingAcceptView(APIView):
    """
    POST /api/v1/pricing/accept-offer/
    Farmer accepts the dynamic price offer, locking the transaction for immediate payout.
    """
    def post(self, request):
        serializer = DynamicPricingAcceptSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch_id = serializer.validated_data['batch_id']
        batch = get_object_or_404(ProduceBatch, batch_id=batch_id)

        pricing_record = getattr(batch, 'pricing_record', None)
        if not pricing_record:
            return Response(
                {"error": "No pricing record found for this batch. Calculate price first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        DynamicPricingEngine.accept_price_offer(pricing_record)

        return Response({
            "status": "PRICE_OFFER_ACCEPTED",
            "message": "Price offer accepted by farmer. Batch queued for automatic digital payout and transit.",
            "batch_id": batch.batch_id,
            "final_unit_price_per_kg": float(pricing_record.final_unit_price_per_kg),
            "total_gross_amount": float(pricing_record.total_gross_amount)
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 3. INTEGRATED AGRI-FINTECH & AUTOMATED PAYBACK ENDPOINTS
# ==============================================================================

class AgriFintechPayoutView(APIView):
    """
    POST /api/v1/fintech/settle-payout/
    Executes atomic harvest settlement:
    Deducts in-kind financing (certified seeds, bio-fertilizers) from final payout.
    Instantly transfers remaining net profits to the farmer's digital wallet/UPI.
    """
    def post(self, request):
        serializer = AgriFintechPayoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch_id = serializer.validated_data['batch_id']
        payment_channel = serializer.validated_data.get('payment_channel', 'INSTANT_UPI')
        batch = get_object_or_404(ProduceBatch, batch_id=batch_id)

        try:
            settlement = AgriFintechSettlementEngine.process_harvest_settlement(
                batch=batch,
                payment_channel=payment_channel
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        wallet = batch.farmer.wallet
        return Response({
            "status": "PAYOUT_COMPLETED",
            "message": "Digital payout processed successfully with automated input loan deduction.",
            "settlement_id": settlement.settlement_id,
            "transaction_reference": settlement.transaction_reference,
            "itemized_receipt": {
                "farmer": batch.farmer.get_full_name() or batch.farmer.username,
                "batch_id": batch.batch_id,
                "crop": batch.crop.name,
                "gross_produce_revenue": float(settlement.gross_produce_revenue),
                "in_kind_loan_deduction": float(settlement.input_loan_deduction),
                "logistics_handling_fee": float(settlement.logistics_handling_fee),
                "net_amount_transferred": float(settlement.net_payout_amount),
                "payment_destination": f"{wallet.bank_name} / UPI: {wallet.upi_id}",
                "farmer_wallet_new_balance": float(wallet.current_balance),
                "timestamp": settlement.settled_at.isoformat()
            }
        }, status=status.HTTP_200_OK)


class FarmerWalletDetailView(APIView):
    """
    GET /api/v1/fintech/wallet/?phone=+919876543210
    Retrieves farmer wallet balance, outstanding input loans, and settlement history.
    """
    def get(self, request):
        phone = request.query_params.get('phone')
        if phone:
            user = get_object_or_404(User, phone_number=phone)
        elif request.user.is_authenticated:
            user = request.user
        else:
            user = User.objects.filter(role=UserRole.FARMER).first()
            if not user:
                return Response({"error": "No farmer user found."}, status=status.HTTP_404_NOT_FOUND)

        wallet, _ = FarmerWallet.objects.get_or_create(farmer=user)
        loans = InputLoan.objects.filter(farmer=user)
        settlements = PayoutSettlement.objects.filter(farmer=user).order_by('-settled_at')[:5]

        return Response({
            "farmer": user.get_full_name() or user.username,
            "phone": user.phone_number,
            "wallet_balance": float(wallet.current_balance),
            "lifetime_earnings": float(wallet.total_lifetime_earnings),
            "total_input_loans_deducted": float(wallet.total_input_deductions),
            "active_input_loans": [
                {
                    "loan_id": l.loan_id,
                    "input_type": l.get_input_type_display(),
                    "package": l.package_name,
                    "outstanding_balance": float(l.outstanding_balance),
                    "status": l.get_status_display()
                } for l in loans
            ],
            "recent_settlements": PayoutSettlementSerializer(settlements, many=True).data
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 4. DYNAMIC ROUTE OPTIMIZATION ENDPOINTS
# ==============================================================================

class DynamicRouteOptimizeView(APIView):
    """
    POST /api/v1/logistics/optimize-routes/
    Consolidates small agricultural batches into commercial-scale loads.
    Dynamically routes trucks to sweep local hubs based on real-time inventory updates and prioritizing perishable crops.
    """
    def post(self, request):
        created_routes = DynamicRoutingEngine.optimize_and_dispatch_fleet()

        return Response({
            "status": "ROUTES_OPTIMIZED",
            "routes_generated_count": len(created_routes),
            "message": f"Successfully consolidated micro-hub inventory into {len(created_routes)} prioritized sweep routes.",
            "routes": TransitRouteSerializer(created_routes, many=True).data
        }, status=status.HTTP_200_OK)


class TransitRouteListView(APIView):
    """
    GET /api/v1/logistics/routes/
    Lists all active sweep routes and waypoint stops.
    """
    def get(self, request):
        routes = TransitRoute.objects.all().order_by('-created_at')[:10]
        return Response(TransitRouteSerializer(routes, many=True).data)


# ==============================================================================
# 5. K2K COMMAND CENTER & UNIFIED INTELLIGENCE ENGINE
# ==============================================================================

class CommandCenterOverviewView(APIView):
    """
    GET /api/v1/command-center/overview/
    Live B2B Admin dashboard showing active crops, unmatched demand, and transit vehicles.
    """
    def get(self, request):
        now = timezone.now()

        # 1. Active Crops & Hub Inventories
        active_crops = Crop.objects.all()
        crop_summary = []
        for c in active_crops:
            hub_batches = ProduceBatch.objects.filter(
                crop=c,
                current_status__in=[
                    BatchStatus.RECEIVED_AT_HUB,
                    BatchStatus.AI_GRADED,
                    BatchStatus.PRICE_ACCEPTED,
                    BatchStatus.IN_COLD_STORAGE
                ]
            )
            total_hub_stock = hub_batches.aggregate(
                total=Sum('accepted_quantity_kg')
            )['total'] or Decimal('0.00')

            crop_summary.append({
                "crop_id": c.id,
                "name": c.name,
                "perishability_tier": c.get_perishability_tier_display(),
                "base_msp_floor": float(c.base_msp_price_per_kg),
                "market_benchmark": float(c.market_benchmark_price_per_kg),
                "current_hub_stock_kg": float(total_hub_stock),
                "active_batches_count": hub_batches.count()
            })

        # 2. Unmatched Retailer Demand Matrix
        pending_demand = DemandOrder.objects.filter(
            status__in=[DemandOrderStatus.PENDING_MATCH, DemandOrderStatus.PARTIALLY_ALLOCATED]
        ).select_related('retailer', 'crop')

        demand_matrix = []
        total_unmatched_kg = Decimal('0.00')
        for order in pending_demand:
            unmatched = order.remaining_unmatched_kg()
            total_unmatched_kg += unmatched
            demand_matrix.append({
                "order_id": order.order_id,
                "retailer_name": order.retailer.get_full_name() or order.retailer.username,
                "crop": order.crop.name,
                "required_quantity_kg": float(order.required_quantity_kg),
                "fulfilled_quantity_kg": float(order.fulfilled_quantity_kg),
                "unmatched_kg": float(unmatched),
                "target_delivery_date": order.target_delivery_date.isoformat(),
                "locked_unit_price": float(order.locked_unit_price),
                "status": order.get_status_display()
            })

        # 3. Transit Fleet & Sweeping Vehicles
        active_vehicles = Vehicle.objects.all()
        vehicle_telemetry = []
        for v in active_vehicles:
            vehicle_telemetry.append({
                "vehicle_number": v.vehicle_number,
                "driver_name": v.driver_name,
                "driver_phone": v.driver_phone,
                "status": v.get_status_display(),
                "has_cold_chain": v.has_cold_chain,
                "max_payload_kg": float(v.max_payload_kg),
                "current_location": {
                    "latitude": float(v.current_latitude) if v.current_latitude else 18.5204,
                    "longitude": float(v.current_longitude) if v.current_longitude else 73.8567
                }
            })

        # 4. Critical Perishability & Spoilage Risk Alerts
        perishable_alerts = ProduceBatch.objects.filter(
            crop__perishability_tier__in=[CropPerishabilityTier.URGENT_24H, CropPerishabilityTier.HIGH_48H],
            current_status__in=[BatchStatus.PRICE_ACCEPTED, BatchStatus.IN_COLD_STORAGE]
        ).select_related('crop', 'current_hub')[:5]

        alerts = []
        for b in perishable_alerts:
            alerts.append({
                "batch_id": b.batch_id,
                "crop": b.crop.name,
                "hub": b.current_hub.name if b.current_hub else "Drop Hub",
                "quantity_kg": float(b.accepted_quantity_kg or b.initial_quantity_kg),
                "perishability": b.crop.get_perishability_tier_display(),
                "action_required": "Prioritize vehicle sweep within next 4 hours to eliminate post-harvest degradation."
            })

        # 5. Financial Settlement Metrics
        total_payouts = PayoutSettlement.objects.aggregate(
            total_net=Sum('net_payout_amount'),
            total_loans_recovered=Sum('input_loan_deduction')
        )

        return Response({
            "timestamp": now.isoformat(),
            "k2k_system_status": "OPERATIONAL_HEALTHY",
            "kpi_highlights": {
                "total_active_crops": len(crop_summary),
                "total_unmatched_retailer_demand_kg": float(total_unmatched_kg),
                "active_fleet_trucks": active_vehicles.count(),
                "total_farmer_payouts_disbursed_rupees": float(total_payouts['total_net'] or Decimal('0.00')),
                "total_input_loans_recovered_rupees": float(total_payouts['total_loans_recovered'] or Decimal('0.00'))
            },
            "active_crops_stock": crop_summary,
            "unmatched_demand_orders": demand_matrix,
            "fleet_telemetry": vehicle_telemetry,
            "urgent_perishability_alerts": alerts
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 6. FARMER MULTILINGUAL VOICE/UI NLP ASSISTANT
# ==============================================================================

class VoiceAssistantCommandView(APIView):
    """
    POST /api/v1/voice-assistant/process-command/
    Processes multilingual voice commands from farmers in Hindi, Marathi, Telugu, Tamil, Kannada, or English.
    Intents supported:
    1. CHECK_PRICE (e.g., 'आज टमाटर का क्या भाव है?', 'What is tomato price?')
    2. LOG_HARVEST (e.g., 'मैंने 200 किलो शिमला मिर्च तोड़ी है', 'Logged 200 kg capsicum')
    3. INPUT_FINANCING (e.g., 'मुझे खाद और बीज का लोन चाहिए', 'Request seeds and fertilizer loan')
    4. WALLET_STATUS (e.g., 'मेरा पैसा कब आएगा?', 'When is my payout coming?')
    """
    def post(self, request):
        serializer = VoiceAssistantCommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        transcript = serializer.validated_data['voice_transcript'].strip()
        lang = serializer.validated_data.get('language', 'hi')
        phone = serializer.validated_data.get('farmer_phone')

        farmer = User.objects.filter(phone_number=phone).first() if phone else None
        if not farmer:
            farmer = User.objects.filter(role=UserRole.FARMER).first()

        result = VoiceAssistantIntelligenceEngine.process_voice_transcript(
            transcript=transcript,
            lang=lang,
            farmer=farmer
        )
        return Response(result, status=status.HTTP_200_OK)


# ==============================================================================
# 7. MODEL VIEWSETS FOR BROWSABLE CRUD OPERATIONS
# ==============================================================================

class CropViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer


class MicroHubViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MicroHub.objects.all()
    serializer_class = MicroHubSerializer


class DemandOrderViewSet(viewsets.ModelViewSet):
    queryset = DemandOrder.objects.all().order_by('-created_at')
    serializer_class = DemandOrderSerializer


class HarvestScheduleViewSet(viewsets.ModelViewSet):
    queryset = HarvestSchedule.objects.all().order_by('-scheduled_harvest_date')
    serializer_class = HarvestScheduleSerializer


class ProduceBatchViewSet(viewsets.ModelViewSet):
    queryset = ProduceBatch.objects.all().order_by('-created_at')
    serializer_class = ProduceBatchSerializer


# ==============================================================================
# 8. LIVE WEATHER INTELLIGENCE & AGRONOMIC ADVISORY
# ==============================================================================

class LiveWeatherAdvisoryView(APIView):
    """
    GET /api/v1/advisory/weather/?latitude=20.0768&longitude=74.1105
    Fetches real-time weather from Open-Meteo for given coordinates and outputs AI agronomic advisory.
    """
    def get(self, request):
        try:
            lat = float(request.query_params.get('latitude', 20.0768))
            lon = float(request.query_params.get('longitude', 74.1105))
        except (TypeError, ValueError):
            return Response({"error": "Invalid latitude or longitude format."}, status=status.HTTP_400_BAD_REQUEST)

        advisory_data = WeatherIntelligenceEngine.get_weather_and_agronomic_advisory(latitude=lat, longitude=lon)
        return Response(advisory_data, status=status.HTTP_200_OK)

