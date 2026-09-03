"""
Django management command to seed demo data for Project Khet2Kitchen (K2K).
Run: python manage.py seed_demo_data
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, time
from k2k_core.models import (
    User,
    UserRole,
    RegionalLanguage,
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
    BatchStatus,
    InputLoan,
    InputType,
    FarmerWallet,
    Vehicle
)


class Command(BaseCommand):
    help = "Seeds initial demo data for Project Khet2Kitchen hackathon demonstration."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("==> Seeding K2K Platform Demo Data..."))

        # 1. Create Demo Users
        # Farmer
        farmer_user, created = User.objects.get_or_create(
            username="santosh_patil",
            defaults={
                "first_name": "Santosh",
                "last_name": "Patil",
                "phone_number": "+919876543210",
                "role": UserRole.FARMER,
                "preferred_language": RegionalLanguage.MARATHI,
                "village": "Pimpalgaon",
                "district": "Nashik",
                "state": "Maharashtra",
                "latitude": Decimal("20.1714"),
                "longitude": Decimal("73.9856")
            }
        )
        if created:
            farmer_user.set_password("k2k_farmer_2026")
            farmer_user.save()

        FarmerProfile.objects.get_or_create(
            user=farmer_user,
            defaults={
                "land_size_acres": Decimal("3.50"),
                "soil_type": "Black Cotton / Loamy",
                "k2k_reliability_score": Decimal("88.50"),
                "credit_limit": Decimal("35000.00"),
                "current_outstanding_credit": Decimal("4500.00"),
                "upi_id": "santosh.patil@okhdfcbank",
                "bank_account_number": "50100238491823",
                "ifsc_code": "HDFC0001234"
            }
        )
        FarmerWallet.objects.get_or_create(
            farmer=farmer_user,
            defaults={
                "current_balance": Decimal("1250.00"),
                "total_lifetime_earnings": Decimal("45000.00"),
                "total_input_deductions": Decimal("8500.00"),
                "upi_id": "santosh.patil@okhdfcbank"
            }
        )

        # Hub Manager
        hub_manager, created = User.objects.get_or_create(
            username="vikram_shinde",
            defaults={
                "first_name": "Vikram",
                "last_name": "Shinde",
                "phone_number": "+919876543211",
                "role": UserRole.HUB_MANAGER,
                "village": "Niphad",
                "district": "Nashik",
                "state": "Maharashtra"
            }
        )
        if created:
            hub_manager.set_password("k2k_hub_2026")
            hub_manager.save()

        # Retailer
        retailer_user, created = User.objects.get_or_create(
            username="fresh_cart_mumbai",
            defaults={
                "first_name": "FreshCart",
                "last_name": "Urban Mart",
                "phone_number": "+919876543212",
                "role": UserRole.RETAILER,
                "district": "Mumbai",
                "state": "Maharashtra"
            }
        )
        if created:
            retailer_user.set_password("k2k_retail_2026")
            retailer_user.save()

        RetailerProfile.objects.get_or_create(
            user=retailer_user,
            defaults={
                "business_name": "FreshCart Supermarket Chain",
                "business_type": "Omnichannel Grocery",
                "gstin": "27AABCF1234F1Z8",
                "delivery_address": "FreshCart Fulfillment Hub 4, Vashi, Navi Mumbai 400703",
                "credit_balance": Decimal("150000.00")
            }
        )

        # 2. Micro-Hubs
        hub_niphad, _ = MicroHub.objects.get_or_create(
            code="HUB-NSK-NIP-01",
            defaults={
                "name": "Niphad Agri Micro-Hub",
                "manager": hub_manager,
                "village": "Niphad Rural Center",
                "district": "Nashik",
                "state": "Maharashtra",
                "pincode": "422303",
                "latitude": Decimal("20.0768"),
                "longitude": Decimal("74.1105"),
                "capacity_kg": Decimal("12000.00"),
                "cold_storage_available": True
            }
        )
        hub_junnar, _ = MicroHub.objects.get_or_create(
            code="HUB-PUN-JUN-02",
            defaults={
                "name": "Junnar Valley Micro-Hub",
                "village": "Otur Cross",
                "district": "Pune",
                "state": "Maharashtra",
                "pincode": "412409",
                "latitude": Decimal("19.2065"),
                "longitude": Decimal("73.8761"),
                "capacity_kg": Decimal("10000.00"),
                "cold_storage_available": False
            }
        )

        # 3. Crops
        crop_tomato, _ = Crop.objects.get_or_create(
            name="Hybrid Tomato (Tamatar)",
            defaults={
                "category": "Fruit Vegetable",
                "perishability_tier": CropPerishabilityTier.HIGH_48H,
                "standard_shelf_life_hours": 48,
                "base_msp_price_per_kg": Decimal("14.00"),
                "market_benchmark_price_per_kg": Decimal("24.00"),
                "standard_logistics_cost_per_kg": Decimal("2.50"),
                "grade_a_premium_pct": Decimal("25.00"),
                "grade_c_discount_pct": Decimal("30.00")
            }
        )
        crop_spinach, _ = Crop.objects.get_or_create(
            name="Organic Spinach (Palak)",
            defaults={
                "category": "Leafy Greens",
                "perishability_tier": CropPerishabilityTier.URGENT_24H,
                "standard_shelf_life_hours": 24,
                "base_msp_price_per_kg": Decimal("18.00"),
                "market_benchmark_price_per_kg": Decimal("32.00"),
                "standard_logistics_cost_per_kg": Decimal("3.00"),
                "grade_a_premium_pct": Decimal("30.00"),
                "grade_c_discount_pct": Decimal("40.00")
            }
        )
        crop_pepper, _ = Crop.objects.get_or_create(
            name="Green Bell Pepper (Shimla Mirch)",
            defaults={
                "category": "Vegetable",
                "perishability_tier": CropPerishabilityTier.MEDIUM_7D,
                "standard_shelf_life_hours": 120,
                "base_msp_price_per_kg": Decimal("22.00"),
                "market_benchmark_price_per_kg": Decimal("40.00"),
                "standard_logistics_cost_per_kg": Decimal("2.50"),
                "grade_a_premium_pct": Decimal("20.00"),
                "grade_c_discount_pct": Decimal("25.00")
            }
        )

        # 4. Retailer Demand Orders (Demand-Lock)
        tomorrow = timezone.now().date() + timedelta(days=1)
        demand_order, _ = DemandOrder.objects.get_or_create(
            order_id="ORD-MUM-2026-081",
            defaults={
                "retailer": retailer_user,
                "crop": crop_tomato,
                "target_delivery_date": tomorrow,
                "required_quantity_kg": Decimal("2500.00"),
                "fulfilled_quantity_kg": Decimal("500.00"),
                "required_grade": CommercialGrade.GRADE_A,
                "locked_unit_price": Decimal("28.00"),
                "max_acceptable_price": Decimal("30.00"),
                "delivery_destination": "Vashi Central Distribution Center, Navi Mumbai",
                "status": DemandOrderStatus.PARTIALLY_ALLOCATED,
                "is_demand_locked": True
            }
        )

        # 5. Algorithmic Harvest Schedule
        schedule, _ = HarvestSchedule.objects.get_or_create(
            schedule_id="SCH-NSK-2026-104",
            defaults={
                "farmer": farmer_user,
                "crop": crop_tomato,
                "linked_demand_order": demand_order,
                "allocated_quantity_kg": Decimal("500.00"),
                "scheduled_harvest_date": tomorrow,
                "harvest_window_start": time(6, 0),
                "harvest_window_end": time(9, 30),
                "target_hub": hub_niphad,
                "hub_dropoff_deadline": timezone.now() + timedelta(hours=14),
                "match_score": Decimal("94.50")
            }
        )

        # 6. In-Kind Input Financing Loan
        InputLoan.objects.get_or_create(
            loan_id="LOAN-IN-KIND-2026-042",
            defaults={
                "farmer": farmer_user,
                "input_type": InputType.CERTIFIED_SEEDS,
                "package_name": "Namdhari Hybrid Tomato Seeds (500g) + Bio-NPK Fertilizer Pack",
                "quantity_units": 2,
                "unit_cost": Decimal("2250.00"),
                "total_loan_amount": Decimal("4500.00"),
                "outstanding_balance": Decimal("4500.00"),
                "due_date": tomorrow + timedelta(days=15)
            }
        )

        # 7. Seed Ready Produce Batches for AI Grading & Dynamic Pricing Testing
        batch_ready, _ = ProduceBatch.objects.get_or_create(
            batch_id="K2K-2026-TOM-DEMO01",
            defaults={
                "farmer": farmer_user,
                "crop": crop_tomato,
                "harvest_schedule": schedule,
                "current_hub": hub_niphad,
                "initial_quantity_kg": Decimal("400.00"),
                "accepted_quantity_kg": Decimal("400.00"),
                "current_status": BatchStatus.RECEIVED_AT_HUB,
                "assigned_demand_order": demand_order
            }
        )

        # Batch with urgent perishable spinach at Junnar hub
        ProduceBatch.objects.get_or_create(
            batch_id="K2K-2026-SPN-DEMO02",
            defaults={
                "farmer": farmer_user,
                "crop": crop_spinach,
                "current_hub": hub_junnar,
                "initial_quantity_kg": Decimal("250.00"),
                "accepted_quantity_kg": Decimal("250.00"),
                "current_status": BatchStatus.PRICE_ACCEPTED
            }
        )

        # 8. Fleet Vehicle
        Vehicle.objects.get_or_create(
            vehicle_number="MH-15-K2K-5001",
            defaults={
                "driver_name": "Tukaram Gaikwad",
                "driver_phone": "+919822334455",
                "max_payload_kg": Decimal("3500.00"),
                "has_cold_chain": True,
                "current_latitude": Decimal("19.9975"),
                "current_longitude": Decimal("73.7898")
            }
        )

        self.stdout.write(self.style.SUCCESS("==> Demo data successfully seeded for K2K!"))
        self.stdout.write(self.style.SUCCESS(f"  Farmer created: {farmer_user.username} (+919876543210)"))
        self.stdout.write(self.style.SUCCESS(f"  Batch ready for AI Scan: {batch_ready.batch_id}"))
