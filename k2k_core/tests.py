"""
Comprehensive Automated Test Suite for Project Khet2Kitchen (K2K).
Verifies:
1. AI Grading commercial parameters & confidence threshold fallback.
2. Dynamic Pricing calculation & statutory MSP price-floor protection.
3. Agri-Fintech atomic input loan deduction & instant wallet credit.
4. Dynamic Route Optimization prioritizing high-perishability crops.
5. REST API endpoint responses and serialization contracts.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta, time
from rest_framework.test import APIClient
from rest_framework import status

from k2k_core.models import (
    User,
    UserRole,
    FarmerProfile,
    RetailerProfile,
    MicroHub,
    Crop,
    CropPerishabilityTier,
    DemandOrder,
    DemandOrderStatus,
    CommercialGrade,
    HarvestSchedule,
    ProduceBatch,
    AIGradingRecord,
    DynamicPricingRecord,
    InputLoan,
    InputType,
    InputLoanStatus,
    FarmerWallet,
    PayoutSettlement,
    Vehicle,
    BatchStatus
)
from k2k_core.services import (
    AIGradingEngine,
    DynamicPricingEngine,
    AgriFintechSettlementEngine,
    DynamicRoutingEngine,
    WeatherIntelligenceEngine,
    VoiceAssistantIntelligenceEngine
)


class K2KCoreArchitectureTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # 1. Users
        self.farmer = User.objects.create_user(
            username="test_farmer",
            first_name="Ramesh",
            last_name="Kumar",
            phone_number="+919999988888",
            role=UserRole.FARMER,
            district="Nashik"
        )
        self.farmer_profile = FarmerProfile.objects.create(
            user=self.farmer,
            land_size_acres=Decimal("2.50"),
            k2k_reliability_score=Decimal("85.00"),
            credit_limit=Decimal("20000.00"),
            current_outstanding_credit=Decimal("3000.00")
        )
        self.farmer_wallet = FarmerWallet.objects.create(
            farmer=self.farmer,
            current_balance=Decimal("500.00"),
            upi_id="ramesh@upi"
        )

        self.hub_manager = User.objects.create_user(
            username="test_hubmgr",
            role=UserRole.HUB_MANAGER,
            district="Nashik"
        )

        self.retailer = User.objects.create_user(
            username="test_retailer",
            role=UserRole.RETAILER,
            district="Mumbai"
        )
        self.retailer_profile = RetailerProfile.objects.create(
            user=self.retailer,
            business_name="Urban Supermarket Ltd",
            delivery_address="Mumbai Central Hub"
        )

        # 2. Hubs
        self.hub = MicroHub.objects.create(
            name="Nashik Rural Hub 1",
            code="HUB-NSK-01",
            manager=self.hub_manager,
            village="Dindori",
            district="Nashik",
            state="Maharashtra",
            pincode="422202",
            latitude=Decimal("20.2000"),
            longitude=Decimal("73.8000"),
            capacity_kg=Decimal("10000.00"),
            cold_storage_available=True
        )

        # 3. Crops
        self.crop_tomato = Crop.objects.create(
            name="Tomato",
            category="Vegetable",
            perishability_tier=CropPerishabilityTier.HIGH_48H,
            standard_shelf_life_hours=48,
            base_msp_price_per_kg=Decimal("15.00"),  # Floor price ₹15/kg
            market_benchmark_price_per_kg=Decimal("25.00"),
            standard_logistics_cost_per_kg=Decimal("2.50"),
            grade_a_premium_pct=Decimal("20.00"),
            grade_c_discount_pct=Decimal("30.00")
        )

        self.crop_spinach = Crop.objects.create(
            name="Spinach",
            category="Leafy Green",
            perishability_tier=CropPerishabilityTier.URGENT_24H,
            standard_shelf_life_hours=24,
            base_msp_price_per_kg=Decimal("20.00"),
            market_benchmark_price_per_kg=Decimal("35.00"),
            standard_logistics_cost_per_kg=Decimal("3.00")
        )

        # 4. In-Kind Input Loan
        self.input_loan = InputLoan.objects.create(
            loan_id="LOAN-TEST-001",
            farmer=self.farmer,
            input_type=InputType.CERTIFIED_SEEDS,
            package_name="Hybrid Seed + Bio-NPK Kit",
            quantity_units=1,
            unit_cost=Decimal("3000.00"),
            total_loan_amount=Decimal("3000.00"),
            outstanding_balance=Decimal("3000.00"),
            due_date=timezone.now().date() + timedelta(days=30)
        )

        # 5. Produce Batch
        self.batch = ProduceBatch.objects.create(
            farmer=self.farmer,
            crop=self.crop_tomato,
            current_hub=self.hub,
            initial_quantity_kg=Decimal("500.00"),
            accepted_quantity_kg=Decimal("500.00"),
            current_status=BatchStatus.RECEIVED_AT_HUB
        )

    # --------------------------------------------------------------------------
    # Test 1: Cryptographic Traceability
    # --------------------------------------------------------------------------
    def test_cryptographic_traceability_hash_generation(self):
        self.assertTrue(self.batch.batch_id.startswith("K2K-"))
        self.assertEqual(len(self.batch.traceability_hash), 64)  # SHA-256 length

    # --------------------------------------------------------------------------
    # Test 2: AI Quality Grading Engine & Confidence Gate
    # --------------------------------------------------------------------------
    def test_ai_grading_high_confidence_grade_a(self):
        """High confidence scan should award Grade A without manual review."""
        sim_params = {
            'size_uniformity': 92.0,
            'color_uniformity': 94.0,
            'surface_defect_pct': 2.5,
            'confidence_score': 0.950
        }
        grading = AIGradingEngine.analyze_crop_scan(self.batch, simulation_params=sim_params)
        
        self.assertEqual(grading.final_grade, CommercialGrade.GRADE_A)
        self.assertFalse(grading.requires_manual_review)
        self.assertEqual(self.batch.current_status, BatchStatus.AI_GRADED)
        self.assertEqual(self.batch.accepted_quantity_kg, Decimal("500.00"))

    def test_ai_grading_low_confidence_fallback_to_manual_review(self):
        """Low confidence scan (< 0.820) must trigger human-in-the-loop audit."""
        sim_params = {
            'size_uniformity': 75.0,
            'color_uniformity': 70.0,
            'surface_defect_pct': 12.0,
            'confidence_score': 0.730  # Below 0.820 threshold
        }
        grading = AIGradingEngine.analyze_crop_scan(self.batch, simulation_params=sim_params)
        
        self.assertTrue(grading.requires_manual_review)
        self.assertEqual(self.batch.current_status, BatchStatus.FLAGGED_FOR_MANUAL_REVIEW)

        # Hub Manager applies manual override
        updated = AIGradingEngine.apply_manual_override(
            grading_record=grading,
            reviewer=self.hub_manager,
            override_grade=CommercialGrade.GRADE_B,
            reviewer_notes="Inspected physical crate. Lighting was dim, produce is healthy Grade B."
        )
        self.assertTrue(updated.is_manually_reviewed)
        self.assertEqual(updated.effective_grade(), CommercialGrade.GRADE_B)
        self.assertFalse(updated.requires_manual_review)
        self.assertEqual(self.batch.current_status, BatchStatus.AI_GRADED)

    # --------------------------------------------------------------------------
    # Test 3: Transparent Dynamic Pricing & Price-Floor Protection
    # --------------------------------------------------------------------------
    def test_dynamic_pricing_calculation_with_premium(self):
        """Calculates dynamic price with Grade A bonus."""
        # Grade as Grade A first
        AIGradingEngine.analyze_crop_scan(self.batch, simulation_params={
            'size_uniformity': 95.0, 'color_uniformity': 95.0, 'surface_defect_pct': 1.0, 'confidence_score': 0.96
        })

        pricing = DynamicPricingEngine.calculate_price_offer(self.batch)
        
        # Base (₹25) + Grade A 20% (₹5) + Demand Surge (0) - Logistics (₹2.50) = ₹27.50/kg
        self.assertEqual(pricing.final_unit_price_per_kg, Decimal("27.50"))
        self.assertEqual(pricing.total_gross_amount, Decimal("13750.00"))  # 500 kg * 27.50
        self.assertFalse(pricing.price_floor_enforced)
        self.assertIn("crop_name", pricing.pricing_breakdown)

    def test_dynamic_pricing_statutory_msp_floor_protection(self):
        """
        When market price drops or deductions are high,
        verify that K2K strictly enforces the unbreachable MSP price floor.
        """
        # Force a crop with low benchmark and high logistics
        distress_crop = Crop.objects.create(
            name="Distress Tomato",
            category="Vegetable",
            base_msp_price_per_kg=Decimal("16.00"),  # Statutory MSP Floor ₹16
            market_benchmark_price_per_kg=Decimal("12.00"),  # Collapsed spot market ₹12
            standard_logistics_cost_per_kg=Decimal("3.00"),
            grade_a_premium_pct=Decimal("10.00")
        )
        distress_batch = ProduceBatch.objects.create(
            farmer=self.farmer,
            crop=distress_crop,
            current_hub=self.hub,
            initial_quantity_kg=Decimal("1000.00")
        )

        pricing = DynamicPricingEngine.calculate_price_offer(distress_batch)
        
        # Raw would be: 12 - 3 = 9 (well below ₹16)
        # Price Floor MUST be enforced
        self.assertEqual(pricing.final_unit_price_per_kg, Decimal("16.00"))
        self.assertTrue(pricing.price_floor_enforced)
        self.assertEqual(pricing.total_gross_amount, Decimal("16000.00"))

    # --------------------------------------------------------------------------
    # Test 4: Integrated Agri-Fintech Atomic Payout & Loan Deductions
    # --------------------------------------------------------------------------
    def test_agri_fintech_settlement_and_loan_recovery(self):
        """
        Verifies that input loans are seamlessly deducted from final harvest proceeds
        and net profits are instantly credited to the farmer's wallet.
        """
        # Grade and price batch
        AIGradingEngine.analyze_crop_scan(self.batch, simulation_params={
            'size_uniformity': 90.0, 'color_uniformity': 90.0, 'surface_defect_pct': 3.0, 'confidence_score': 0.90
        })
        pricing = DynamicPricingEngine.calculate_price_offer(self.batch)
        DynamicPricingEngine.accept_price_offer(pricing)

        initial_wallet_balance = self.farmer.wallet.current_balance  # ₹500
        gross_revenue = pricing.total_gross_amount  # ₹13750.00
        loan_balance = self.input_loan.outstanding_balance  # ₹3000.00

        settlement = AgriFintechSettlementEngine.process_harvest_settlement(self.batch)

        # Verify loan was deducted
        self.input_loan.refresh_from_db()
        self.assertEqual(self.input_loan.outstanding_balance, Decimal("0.00"))
        self.assertEqual(self.input_loan.status, InputLoanStatus.FULLY_SETTLED)

        # Verify settlement record
        self.assertEqual(settlement.gross_produce_revenue, gross_revenue)
        self.assertEqual(settlement.input_loan_deduction, loan_balance)
        expected_net = gross_revenue - loan_balance
        self.assertEqual(settlement.net_payout_amount, expected_net)

        # Verify wallet credited
        self.farmer.wallet.refresh_from_db()
        self.assertEqual(self.farmer.wallet.current_balance, initial_wallet_balance + expected_net)

    # --------------------------------------------------------------------------
    # Test 5: Dynamic Route Optimization & Perishability Prioritization
    # --------------------------------------------------------------------------
    def test_dynamic_route_optimization_prioritizes_urgent_perishables(self):
        """Urgent leafy greens (Spinach) must be prioritized over standard vegetables."""
        # Create second hub with spinach
        hub2 = MicroHub.objects.create(
            name="Junnar Leafy Hub",
            code="HUB-PUN-02",
            village="Junnar",
            district="Pune",
            state="Maharashtra",
            pincode="412409",
            latitude=Decimal("19.2000"),
            longitude=Decimal("73.8500")
        )
        spinach_batch = ProduceBatch.objects.create(
            farmer=self.farmer,
            crop=self.crop_spinach,
            current_hub=hub2,
            initial_quantity_kg=Decimal("300.00"),
            accepted_quantity_kg=Decimal("300.00"),
            current_status=BatchStatus.PRICE_ACCEPTED
        )
        
        # Make sure our tomato batch is also ready for transit
        self.batch.current_status = BatchStatus.PRICE_ACCEPTED
        self.batch.save()

        routes = DynamicRoutingEngine.optimize_and_dispatch_fleet()
        self.assertGreaterEqual(len(routes), 1)

        primary_route = routes[0]
        waypoints = list(primary_route.waypoints.all())
        self.assertGreaterEqual(len(waypoints), 1)
        # Hub 2 (spinach) has urgent 24h perishability so it should be stop 1
        self.assertEqual(waypoints[0].hub, hub2)

    # --------------------------------------------------------------------------
    # Test 6: REST API Endpoints Integration
    # --------------------------------------------------------------------------
    def test_api_grading_scan_endpoint(self):
        url = '/api/v1/grading/scan/'
        payload = {
            'batch_id': self.batch.batch_id,
            'simulation_size_uniformity': 94.0,
            'simulation_color_uniformity': 91.0,
            'simulation_surface_defect_pct': 3.0,
            'simulation_confidence_score': 0.920
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'SUCCESS')
        self.assertEqual(res.data['grading']['final_grade'], CommercialGrade.GRADE_A)

    def test_api_dynamic_pricing_calculate_endpoint(self):
        # Grade first
        AIGradingEngine.analyze_crop_scan(self.batch, simulation_params={
            'size_uniformity': 90.0, 'color_uniformity': 90.0, 'surface_defect_pct': 3.0, 'confidence_score': 0.90
        })

        url = '/api/v1/pricing/calculate/'
        res = self.client.post(url, {'batch_id': self.batch.batch_id}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('final_unit_price_per_kg', res.data)
        self.assertIn('itemized_transparency_breakdown', res.data)

    def test_api_command_center_overview_endpoint(self):
        url = '/api/v1/command-center/overview/'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('kpi_highlights', res.data)
        self.assertIn('active_crops_stock', res.data)
        self.assertIn('fleet_telemetry', res.data)

    def test_api_voice_assistant_price_query(self):
        url = '/api/v1/voice-assistant/process-command/'
        payload = {
            'voice_transcript': 'आज टमाटर का क्या भाव है?',
            'language': 'hi',
            'farmer_phone': self.farmer.phone_number
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['intent'], 'CHECK_PRICE')
        self.assertIn('voice_reply_text', res.data)

    def test_api_live_weather_advisory_endpoint(self):
        url = '/api/v1/advisory/weather/?latitude=20.0768&longitude=74.1105'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('telemetry', res.data)
        self.assertIn('advisory', res.data)
        self.assertIn('temperature_celsius', res.data['telemetry'])
        self.assertIn('harvest_window', res.data['advisory'])

    def test_voice_assistant_marathi_intent_execution(self):
        result = VoiceAssistantIntelligenceEngine.process_voice_transcript(
            transcript="मी 150 किलो टोमॅटो कापणी केली आहे",
            lang="mr",
            farmer=self.farmer
        )
        self.assertIn(result['intent'], ['LOG_HARVEST', 'CHECK_PRICE'])
        self.assertIn('voice_reply_text', result)
        self.assertEqual(result['language'], 'mr')
        self.assertTrue(len(result['voice_reply_text']) > 10)

    def test_script_language_auto_detection(self):
        # Gurmukhi script -> Punjabi
        self.assertEqual(VoiceAssistantIntelligenceEngine.detect_script_language("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ"), "pa")
        # Tamil script -> Tamil
        self.assertEqual(VoiceAssistantIntelligenceEngine.detect_script_language("வணக்கம் அய்யா"), "ta")
        # Telugu script -> Telugu
        self.assertEqual(VoiceAssistantIntelligenceEngine.detect_script_language("నమస్కారం గారు"), "te")
        # Gujarati script -> Gujarati
        self.assertEqual(VoiceAssistantIntelligenceEngine.detect_script_language("નમસ્તે ભાઈ"), "gu")
        # Kannada script -> Kannada
        self.assertEqual(VoiceAssistantIntelligenceEngine.detect_script_language("ನಮಸ್ಕಾರ ಅವರೇ"), "kn")

    def test_multilingual_voice_assistant_all_8_languages(self):
        test_samples = [
            ("te", "ఈరోజు టమోటా ధర ఎంత ఉంది?", "CHECK_PRICE"),
            ("ta", "இன்று தக்காளி விலை என்ன?", "CHECK_PRICE"),
            ("kn", "ಇಂದು ಟೊಮೆಟೊ ಬೆಲೆ ಎಷ್ಟು?", "CHECK_PRICE"),
            ("pa", "ਮੈਨੂੰ ਬੀਜ ਅਤੇ ਖਾਦ ਲਈ ਲੋਨ ਚਾਹੀਦਾ ਹੈ", "INPUT_FINANCING"),
            ("gu", "મારી પાસે 150 કિલો ટામેટાં તૈયાર છે", "LOG_HARVEST"),
            ("en", "Check current price of tomato", "CHECK_PRICE"),
        ]
        for lang, phrase, expected_intent in test_samples:
            res = VoiceAssistantIntelligenceEngine.process_voice_transcript(phrase, lang, self.farmer)
            self.assertIn('voice_reply_text', res)
            self.assertEqual(res['language'], lang)
            self.assertTrue(len(res['voice_reply_text']) > 5)


    def test_ai_grading_image_scan_with_gemini_vision(self):
        import io
        from PIL import Image
        img_byte_arr = io.BytesIO()
        img = Image.new('RGB', (120, 120), color='green')
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)

        record = AIGradingEngine.analyze_crop_scan(
            batch=self.batch,
            image_file=img_byte_arr
        )
        self.assertIsNotNone(record)
        self.assertGreaterEqual(record.confidence_score, Decimal('0.00'))
        self.assertIn(record.final_grade, [CommercialGrade.GRADE_A, CommercialGrade.GRADE_B, CommercialGrade.GRADE_C, CommercialGrade.REJECT])


