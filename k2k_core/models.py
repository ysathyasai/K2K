"""
Project Khet2Kitchen (K2K) - Core Database Schema & Models
Architecture: The K2K Intelligence Engine
Designed for Python 3.12+, Django 5+, MySQL (with local SQLite compatibility).
"""
import uuid
import hashlib
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ==============================================================================
# 1. USER & ROLE-BASED ACCESS CONTROL (RBAC)
# ==============================================================================

class UserRole(models.TextChoices):
    FARMER = 'FARMER', 'Farmer'
    HUB_MANAGER = 'HUB_MANAGER', 'Micro-Hub Manager'
    RETAILER = 'RETAILER', 'Urban Retailer'
    ADMIN = 'ADMIN', 'K2K System Administrator'


class RegionalLanguage(models.TextChoices):
    HINDI = 'hi', 'Hindi (हिंदी)'
    MARATHI = 'mr', 'Marathi (मराठी)'
    TELUGU = 'te', 'Telugu (తెలుగు)'
    TAMIL = 'ta', 'Tamil (தமிழ்)'
    KANNADA = 'kn', 'Kannada (ಕನ್ನಡ)'
    PUNJABI = 'pa', 'Punjabi (ਪੰਜਾਬੀ)'
    GUJARATI = 'gu', 'Gujarati (ગુજરાતી)'
    ENGLISH = 'en', 'English'


class User(AbstractUser):
    """
    Custom user model supporting phone-first authentication and agricultural roles.
    """
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.FARMER,
        db_index=True
    )
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Primary contact for OTP logins and voice SMS alerts."
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=RegionalLanguage.choices,
        default=RegionalLanguage.HINDI,
        help_text="Primary dialect for Voice-Assisted NLP interaction."
    )
    village = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True, db_index=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()}) - {self.phone_number or 'No Phone'}"


class FarmerProfile(models.Model):
    """
    Extended profile for smallholder farmers with explainable credit and reliability scores.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    land_size_acres = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('2.50'))
    soil_type = models.CharField(max_length=50, blank=True, default='Alluvial / Loamy')
    primary_water_source = models.CharField(max_length=50, blank=True, default='Borewell / Canal')
    
    # Explainable Alternative Credit & Reliability Score (0.0 to 100.0)
    # Computed from harvest fulfillment rate, quality grading history, and loan repayments
    k2k_reliability_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('85.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Transparent K2K Reliability Score replacing opaque middleman credit checks."
    )
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25000.00'))
    current_outstanding_credit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Digital Settlement Details
    upi_id = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    ifsc_code = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"Farmer: {self.user.get_full_name() or self.user.username} (Reliability: {self.k2k_reliability_score}%)"


class RetailerProfile(models.Model):
    """
    Extended profile for urban supermarkets, restaurant chains, and B2B aggregators.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='retailer_profile')
    business_name = models.CharField(max_length=150)
    business_type = models.CharField(max_length=50, default='Supermarket Chain')
    gstin = models.CharField(max_length=20, blank=True)
    delivery_address = models.TextField()
    credit_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Retailer: {self.business_name} ({self.user.username})"


# ==============================================================================
# 2. MICRO-HUB & LOGISTICS INFRASTRUCTURE
# ==============================================================================

class MicroHub(models.Model):
    """
    Village-level collection and initial grading center replacing the local predatory aggregator.
    """
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active & Receiving'
        AT_CAPACITY = 'AT_CAPACITY', 'At Capacity'
        MAINTENANCE = 'MAINTENANCE', 'Under Maintenance'

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_hubs'
    )
    village = models.CharField(max_length=100)
    district = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10000.00'))
    cold_storage_available = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} [{self.code}] - {self.district}"


# ==============================================================================
# 3. CROP MASTER & PERISHABILITY ENGINE
# ==============================================================================

class CropPerishabilityTier(models.TextChoices):
    URGENT_24H = 'URGENT_24H', 'Urgent Perishable (< 24 hrs - Leafy Greens)'
    HIGH_48H = 'HIGH_48H', 'High Perishable (24-48 hrs - Tomatoes, Berries)'
    MEDIUM_7D = 'MEDIUM_7D', 'Medium Perishable (3-7 days - Bell Peppers, Gourds)'
    STABLE_30D = 'STABLE_30D', 'Stable Shelf-Life (> 7 days - Onions, Potatoes)'


class Crop(models.Model):
    """
    Crop catalog defining shelf-life parameters, baseline MSP floor, and dynamic pricing elasticity.
    """
    name = models.CharField(max_length=80, unique=True, db_index=True)
    scientific_name = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=50, default='Vegetables')
    perishability_tier = models.CharField(
        max_length=20,
        choices=CropPerishabilityTier.choices,
        default=CropPerishabilityTier.HIGH_48H,
        db_index=True
    )
    standard_shelf_life_hours = models.IntegerField(default=48)
    
    # Statutory Price Floor / Cost-of-production Floor (₹ per kg)
    base_msp_price_per_kg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Unbreachable price floor to prevent distress selling."
    )
    # Market benchmark for dynamic pricing
    market_benchmark_price_per_kg = models.DecimalField(max_digits=8, decimal_places=2)
    standard_logistics_cost_per_kg = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('2.50'))
    
    # Grade Multipliers
    grade_a_premium_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))
    grade_c_discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('30.00'))

    def __str__(self):
        return f"{self.name} (MSP Floor: ₹{self.base_msp_price_per_kg}/kg)"


# ==============================================================================
# 4. DEMAND-LOCK SYSTEM (RETAILER PRE-ORDERS)
# ==============================================================================

class CommercialGrade(models.TextChoices):
    GRADE_A = 'GRADE_A', 'Grade A (Premium Retail)'
    GRADE_B = 'GRADE_B', 'Grade B (Standard Market)'
    GRADE_C = 'GRADE_C', 'Grade C (Industrial/Processing/Sauce)'
    REJECT = 'REJECT', 'Reject / Compost'


class DemandOrderStatus(models.TextChoices):
    PENDING_MATCH = 'PENDING_MATCH', 'Pending Farmer Allocation'
    PARTIALLY_ALLOCATED = 'PARTIALLY_ALLOCATED', 'Partially Allocated to Farmers'
    FULLY_LOCKED = 'FULLY_LOCKED', 'Demand Locked & Scheduled'
    IN_FULFILLMENT = 'IN_FULFILLMENT', 'Harvesting & Moving to Hubs'
    COMPLETED = 'COMPLETED', 'Fulfilled & Delivered'
    CANCELLED = 'CANCELLED', 'Cancelled'


class DemandOrder(models.Model):
    """
    Contract pre-order placed by urban retailers prior to harvest, locking quantity and price.
    """
    order_id = models.CharField(max_length=30, unique=True, db_index=True)
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demand_orders')
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name='demand_orders')
    target_delivery_date = models.DateField(db_index=True)
    required_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    fulfilled_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    required_grade = models.CharField(
        max_length=20,
        choices=CommercialGrade.choices,
        default=CommercialGrade.GRADE_A
    )
    locked_unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Agreed purchase price per kg locked at order placement."
    )
    max_acceptable_price = models.DecimalField(max_digits=8, decimal_places=2)
    delivery_destination = models.TextField(help_text="Urban distribution center or store location.")
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.CharField(
        max_length=25,
        choices=DemandOrderStatus.choices,
        default=DemandOrderStatus.PENDING_MATCH,
        db_index=True
    )
    is_demand_locked = models.BooleanField(
        default=True,
        help_text="Indicates guaranteed buyer commitment backed by platform agreement."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def remaining_unmatched_kg(self):
        return max(Decimal('0.00'), self.required_quantity_kg - self.fulfilled_quantity_kg)

    def __str__(self):
        return f"Order #{self.order_id} - {self.crop.name} ({self.required_quantity_kg} kg for {self.target_delivery_date})"


# ==============================================================================
# 5. SUPPLY MATCHING & HARVEST SCHEDULING
# ==============================================================================

class HarvestScheduleStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Scheduled Window Assigned'
    IN_PROGRESS = 'IN_PROGRESS', 'Harvesting Underway'
    COMPLETED = 'COMPLETED', 'Harvested & Delivered to Hub'
    CANCELLED = 'CANCELLED', 'Harvest Cancelled'


class HarvestSchedule(models.Model):
    """
    Algorithmically assigns exact harvest windows to farmers to fulfill locked demand.
    Eliminates speculative harvesting and post-harvest glut.
    """
    schedule_id = models.CharField(max_length=30, unique=True, db_index=True)
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='harvest_schedules')
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name='harvest_schedules')
    linked_demand_order = models.ForeignKey(
        DemandOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocated_schedules'
    )
    allocated_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    scheduled_harvest_date = models.DateField(db_index=True)
    harvest_window_start = models.TimeField(help_text="Optimal cool morning harvest window.")
    harvest_window_end = models.TimeField()
    target_hub = models.ForeignKey(MicroHub, on_delete=models.PROTECT, related_name='scheduled_deliveries')
    hub_dropoff_deadline = models.DateTimeField(help_text="Deadline to maintain peak freshness score.")
    match_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('90.00'),
        help_text="Algorithmic match score factoring distance, reliability, and crop readiness."
    )
    status = models.CharField(
        max_length=20,
        choices=HarvestScheduleStatus.choices,
        default=HarvestScheduleStatus.SCHEDULED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Schedule #{self.schedule_id} - {self.farmer.username} -> {self.crop.name} ({self.allocated_quantity_kg} kg)"


# ==============================================================================
# 6. PRODUCE BATCH & CRYPTOGRAPHIC TRACEABILITY
# ==============================================================================

class BatchStatus(models.TextChoices):
    HARVESTED = 'HARVESTED', 'Harvested at Farm'
    RECEIVED_AT_HUB = 'RECEIVED_AT_HUB', 'Received at Micro-Hub'
    AI_GRADED = 'AI_GRADED', 'AI Quality Graded'
    FLAGGED_FOR_MANUAL_REVIEW = 'FLAGGED_FOR_MANUAL_REVIEW', 'Flagged for Human Inspector Audit'
    PRICE_OFFERED = 'PRICE_OFFERED', 'Dynamic Price Offered'
    PRICE_ACCEPTED = 'PRICE_ACCEPTED', 'Price Accepted by Farmer'
    IN_COLD_STORAGE = 'IN_COLD_STORAGE', 'In Hub Cold Storage'
    CONSOLIDATED_FOR_TRANSIT = 'CONSOLIDATED_FOR_TRANSIT', 'Consolidated for Sweeping Route'
    IN_TRANSIT = 'IN_TRANSIT', 'In Transit on Truck'
    DELIVERED_RETAILER = 'DELIVERED_RETAILER', 'Delivered to Retailer'
    RE_ROUTED_PROCESSING = 'RE_ROUTED_PROCESSING', 'Re-routed to Food Processing Unit (Grade C)'
    RE_ROUTED_DISCOUNT = 'RE_ROUTED_DISCOUNT', 'Re-routed to Discount Outlet (Near Expiry)'
    COMPOSTED = 'COMPOSTED', 'Composted / Bio-Gas Recovery'


class ProduceBatch(models.Model):
    """
    Core physical-digital entity tracked from farm to kitchen with unique cryptographic traceability.
    """
    batch_id = models.CharField(max_length=40, unique=True, db_index=True)
    traceability_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash chaining Farm ID + Harvest Time + AI Grade + Hub + Truck + Retailer."
    )
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='produce_batches')
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name='produce_batches')
    harvest_schedule = models.ForeignKey(
        HarvestSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batches'
    )
    current_hub = models.ForeignKey(
        MicroHub,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventoried_batches'
    )
    assigned_demand_order = models.ForeignKey(
        DemandOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fulfilled_batches'
    )
    harvested_at = models.DateTimeField(default=timezone.now)
    received_at_hub = models.DateTimeField(null=True, blank=True)
    initial_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    accepted_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    current_status = models.CharField(
        max_length=30,
        choices=BatchStatus.choices,
        default=BatchStatus.HARVESTED,
        db_index=True
    )
    
    # Dynamic Shelf-Life & Freshness Engine
    freshness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Real-time dynamic freshness score decayed by ambient temperature and elapsed transit time."
    )
    estimated_shelf_life_hours_remaining = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('48.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_traceability_hash(self, salt="K2K"):
        raw_payload = f"{salt}:{self.batch_id}:{self.farmer_id}:{self.crop_id}:{self.harvested_at.isoformat()}"
        return hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if not self.batch_id:
            year = timezone.now().strftime("%Y")
            crop_prefix = (self.crop.name[:3] if self.crop else "CRP").upper()
            short_uuid = uuid.uuid4().hex[:6].upper()
            self.batch_id = f"K2K-{year}-{crop_prefix}-{short_uuid}"
        if not self.traceability_hash:
            self.traceability_hash = self.generate_traceability_hash()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Batch #{self.batch_id} ({self.crop.name}, {self.initial_quantity_kg} kg)"


# ==============================================================================
# 7. COMPUTER VISION AI GRADING
# ==============================================================================

class AIGradingRecord(models.Model):
    """
    Automated computer vision crop inspection record.
    Evaluates size uniformity, color uniformity, and surface defects with a strict confidence score.
    Includes human-in-the-loop fallback for low-confidence scans.
    """
    grading_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.OneToOneField(ProduceBatch, on_delete=models.CASCADE, related_name='grading_record')
    image_scan = models.ImageField(upload_to='crop_scans/%Y/%m/%d/', null=True, blank=True)
    image_url = models.URLField(blank=True, help_text="Direct link if hosted on S3/Cloudinary.")
    
    # Commercial Parameters
    size_uniformity_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Standard deviation from optimal commercial diameter (0-100)."
    )
    color_uniformity_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="HSV color distribution score (0-100)."
    )
    surface_defect_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of surface area showing blemishes, rot, or bruising (0-100%)."
    )
    detected_defects = models.JSONField(
        default=dict,
        blank=True,
        help_text="Defect breakdown, e.g. {'bruising': 2.1, 'insect_damage': 0.0, 'scabs': 1.2}"
    )
    
    # Resulting Commercial Grade
    final_grade = models.CharField(
        max_length=20,
        choices=CommercialGrade.choices,
        default=CommercialGrade.GRADE_B,
        db_index=True
    )
    
    # Confidence Score & Human-in-the-loop Guardrail
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.000')), MaxValueValidator(Decimal('1.000'))],
        help_text="Model prediction certainty (0.000 to 1.000)."
    )
    confidence_threshold = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal('0.820')
    )
    requires_manual_review = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True when confidence is below 0.82, mandating Hub Manager inspection."
    )
    
    # Manual Review Auditing
    is_manually_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audited_gradings'
    )
    manual_override_grade = models.CharField(
        max_length=20,
        choices=CommercialGrade.choices,
        null=True,
        blank=True
    )
    reviewer_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(auto_now_add=True)

    def effective_grade(self):
        """Returns the manual override if audited, otherwise the AI predicted grade."""
        return self.manual_override_grade if self.is_manually_reviewed and self.manual_override_grade else self.final_grade

    def __str__(self):
        return f"AI Grading for Batch {self.batch.batch_id} -> {self.effective_grade()} (Conf: {self.confidence_score})"


# ==============================================================================
# 8. TRANSPARENT DYNAMIC PRICING ENGINE
# ==============================================================================

class DynamicPricingRecord(models.Model):
    """
    Transparent, price-floor protected offer calculated per batch.
    Formula: Final Price = MAX(MSP Floor, Base Value + Grade Premium + Demand Surge - Logistics)
    Exposes every variable to the farmer for complete transparency.
    """
    class OfferStatus(models.TextChoices):
        OFFERED = 'OFFERED', 'Price Offer Dispatched to Farmer'
        ACCEPTED = 'ACCEPTED', 'Offer Accepted by Farmer'
        DISPUTED = 'DISPUTED', 'Farmer Disputed for Hub Manager Review'
        REJECTED = 'REJECTED', 'Offer Rejected'
        EXPIRED = 'EXPIRED', 'Offer Expired'

    pricing_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.OneToOneField(ProduceBatch, on_delete=models.CASCADE, related_name='pricing_record')
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pricing_records')
    
    # Mathematical Variables Exposed for Radical Transparency
    base_value_per_kg = models.DecimalField(max_digits=8, decimal_places=2)
    grade_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    grade_premium_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    demand_surge_bonus_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    logistics_deduction_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Statutory Price Floor Protection
    msp_floor_price_per_kg = models.DecimalField(max_digits=8, decimal_places=2)
    price_floor_enforced = models.BooleanField(
        default=False,
        help_text="True if market math fell below statutory MSP, protecting farmer from distress sales."
    )
    
    # Final Computed Settlement
    final_unit_price_per_kg = models.DecimalField(max_digits=8, decimal_places=2)
    total_gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Full itemized audit payload returned to Voice UI / Web UI
    pricing_breakdown = models.JSONField(
        default=dict,
        help_text="Itemized transparency ledger: base, quality_bonus, surge_bonus, transport_fee."
    )
    status = models.CharField(
        max_length=20,
        choices=OfferStatus.choices,
        default=OfferStatus.OFFERED,
        db_index=True
    )
    offered_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Pricing for Batch {self.batch.batch_id}: ₹{self.final_unit_price_per_kg}/kg (Total: ₹{self.total_gross_amount})"


# ==============================================================================
# 9. INTEGRATED AGRI-FINTECH & INPUT FINANCING
# ==============================================================================

class InputType(models.TextChoices):
    CERTIFIED_SEEDS = 'SEEDS', 'Certified High-Yield Seeds'
    BIO_FERTILIZER = 'BIO_FERTILIZER', 'Bio-Fertilizer / Compost'
    PESTICIDE = 'PESTICIDE', 'Organic Pest Repellent'
    DRIP_IRRIGATION = 'DRIP_IRRIGATION', 'Micro-Drip Equipment'


class InputLoanStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active Outstanding Loan'
    PARTIALLY_REPAID = 'PARTIALLY_REPAID', 'Partially Repaid via Harvest'
    FULLY_SETTLED = 'FULLY_SETTLED', 'Fully Settled'
    DEFAULTED = 'DEFAULTED', 'Defaulted'


class InputLoan(models.Model):
    """
    In-kind pre-season agricultural financing replacing predatory village moneylenders.
    Directly delivers certified inputs instead of cash to eliminate diversion risk.
    """
    loan_id = models.CharField(max_length=30, unique=True, db_index=True)
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='input_loans')
    input_type = models.CharField(max_length=30, choices=InputType.choices)
    package_name = models.CharField(max_length=150, help_text="e.g., Tomato Hybrid Seed Pack (500g) + Organic Bio-Potash")
    quantity_units = models.IntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2)
    total_loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_repaid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Fair interest rate (often 0% to 4% subsidized for smallholders)
    interest_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    disbursed_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=InputLoanStatus.choices,
        default=InputLoanStatus.ACTIVE,
        db_index=True
    )

    def record_repayment(self, amount):
        """Reduces outstanding balance and updates status."""
        self.amount_repaid += amount
        self.outstanding_balance = max(Decimal('0.00'), self.outstanding_balance - amount)
        if self.outstanding_balance == Decimal('0.00'):
            self.status = InputLoanStatus.FULLY_SETTLED
        else:
            self.status = InputLoanStatus.PARTIALLY_REPAID
        self.save()

    def __str__(self):
        return f"Loan #{self.loan_id} ({self.farmer.username}) - Outstanding: ₹{self.outstanding_balance}"


class FarmerWallet(models.Model):
    """
    Digital wallet for instant automated payouts upon crop drop-off and AI grading.
    """
    farmer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_lifetime_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_input_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Linked payout destination
    upi_id = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=30, blank=True)
    ifsc_code = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def credit(self, amount):
        self.current_balance += amount
        self.total_lifetime_earnings += amount
        self.save()

    def __str__(self):
        return f"Wallet: {self.farmer.username} (Balance: ₹{self.current_balance})"


class PayoutSettlement(models.Model):
    """
    Itemized digital settlement record.
    Automatically deducts input financing costs before transferring net profit to farmer.
    """
    class SettlementStatus(models.TextChoices):
        INITIATED = 'INITIATED', 'Initiated'
        PROCESSING = 'PROCESSING', 'Processing with Bank/UPI Gateway'
        SUCCESS = 'SUCCESS', 'Settlement Successful'
        FAILED = 'FAILED', 'Settlement Failed'

    settlement_id = models.CharField(max_length=40, unique=True, db_index=True)
    batch = models.ForeignKey(ProduceBatch, on_delete=models.CASCADE, related_name='settlements')
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_settlements')
    pricing_record = models.ForeignKey(DynamicPricingRecord, on_delete=models.PROTECT)
    
    # Financial Breakdown
    gross_produce_revenue = models.DecimalField(max_digits=12, decimal_places=2)
    input_loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    logistics_handling_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_payout_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Net profit instantly wired to farmer wallet / UPI."
    )
    
    payment_channel = models.CharField(max_length=30, default='INSTANT_UPI')
    transaction_reference = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=20,
        choices=SettlementStatus.choices,
        default=SettlementStatus.SUCCESS
    )
    settled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Settlement #{self.settlement_id} for {self.farmer.username}: Net ₹{self.net_payout_amount} (Deducted Loan: ₹{self.input_loan_deduction})"


# ==============================================================================
# 10. DYNAMIC ROUTE OPTIMIZATION & FLEET TRACKING
# ==============================================================================

class Vehicle(models.Model):
    """
    Fleet vehicles dispatched to sweep micro-hubs and consolidate small batches into commercial loads.
    """
    class VehicleStatus(models.TextChoices):
        IDLE = 'IDLE', 'Available at Depot'
        DISPATCHED = 'DISPATCHED', 'En-Route Sweeping Hubs'
        LOADING = 'LOADING', 'Loading at Micro-Hub'
        TRANSIT_TO_CITY = 'TRANSIT_TO_CITY', 'Express Transit to City'
        UNLOADING = 'UNLOADING', 'Unloading at Urban Center'
        MAINTENANCE = 'MAINTENANCE', 'Under Maintenance'

    vehicle_number = models.CharField(max_length=20, unique=True, db_index=True)
    driver_name = models.CharField(max_length=100)
    driver_phone = models.CharField(max_length=15)
    max_payload_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('3500.00'))
    has_cold_chain = models.BooleanField(
        default=False,
        help_text="Equipped with refrigerated reefer box for high-perishability leafy greens."
    )
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=25, choices=VehicleStatus.choices, default=VehicleStatus.IDLE)
    last_ping_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Truck {self.vehicle_number} ({self.get_status_display()}) - {self.max_payload_kg} kg max"


class TransitRoute(models.Model):
    """
    Dynamically computed sweep route prioritizing perishability urgency scores across micro-hubs.
    """
    class RouteStatus(models.TextChoices):
        OPTIMIZED = 'OPTIMIZED', 'Optimized & Queued'
        ACTIVE = 'ACTIVE', 'Active in Progress'
        COMPLETED = 'COMPLETED', 'Route Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    route_id = models.CharField(max_length=35, unique=True, db_index=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='routes')
    target_retail_hub = models.CharField(max_length=120, default='Central Urban Distribution Center')
    total_distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    estimated_duration_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Priority score calculated from aggregate perishability of inventoried batches
    priority_urgency_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Urgency multiplier computed by routing engine; leafy greens have top priority."
    )
    status = models.CharField(max_length=20, choices=RouteStatus.choices, default=RouteStatus.OPTIMIZED)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Route #{self.route_id} - Vehicle {self.vehicle.vehicle_number} (Urgency: {self.priority_urgency_score})"


class RouteWaypoint(models.Model):
    """
    Ordered waypoint in a dynamic sweep route, indicating batch pickups and hub inventory consolidated.
    """
    class WaypointAction(models.TextChoices):
        PICKUP = 'PICKUP', 'Pickup Hub Inventory'
        DELIVERY = 'DELIVERY', 'Deliver to Retailer'

    route = models.ForeignKey(TransitRoute, on_delete=models.CASCADE, related_name='waypoints')
    hub = models.ForeignKey(MicroHub, on_delete=models.PROTECT, related_name='route_stops')
    sequence_order = models.PositiveSmallIntegerField(default=1)
    action = models.CharField(max_length=15, choices=WaypointAction.choices, default=WaypointAction.PICKUP)
    batches = models.ManyToManyField(ProduceBatch, blank=True, related_name='transit_waypoints')
    planned_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    estimated_arrival = models.DateTimeField()
    actual_arrival = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f"Stop #{self.sequence_order}: {self.hub.name} ({self.planned_weight_kg} kg) - Route {self.route.route_id}"
