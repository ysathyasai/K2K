"""
URL routing for Project Khet2Kitchen (K2K) API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from k2k_core.views import (
    AIGradingScanView,
    AIGradingManualReviewView,
    DynamicPricingCalculateView,
    DynamicPricingAcceptView,
    AgriFintechPayoutView,
    FarmerWalletDetailView,
    DynamicRouteOptimizeView,
    TransitRouteListView,
    CommandCenterOverviewView,
    VoiceAssistantCommandView,
    CropViewSet,
    MicroHubViewSet,
    DemandOrderViewSet,
    HarvestScheduleViewSet,
    ProduceBatchViewSet
)

router = DefaultRouter()
router.register(r'crops', CropViewSet, basename='crop')
router.register(r'hubs', MicroHubViewSet, basename='hub')
router.register(r'demand-orders', DemandOrderViewSet, basename='demand-order')
router.register(r'harvest-schedules', HarvestScheduleViewSet, basename='harvest-schedule')
router.register(r'batches', ProduceBatchViewSet, basename='batch')

urlpatterns = [
    # 1. Computer Vision AI Quality Grading
    path('grading/scan/', AIGradingScanView.as_view(), name='ai-grading-scan'),
    path('grading/manual-review/', AIGradingManualReviewView.as_view(), name='ai-grading-manual-review'),

    # 2. Transparent Dynamic Pricing Engine
    path('pricing/calculate/', DynamicPricingCalculateView.as_view(), name='dynamic-pricing-calculate'),
    path('pricing/accept-offer/', DynamicPricingAcceptView.as_view(), name='dynamic-pricing-accept'),

    # 3. Integrated Agri-Fintech & Automatic Payback
    path('fintech/settle-payout/', AgriFintechPayoutView.as_view(), name='agri-fintech-settle-payout'),
    path('fintech/wallet/', FarmerWalletDetailView.as_view(), name='farmer-wallet-detail'),

    # 4. Dynamic Route Optimization
    path('logistics/optimize-routes/', DynamicRouteOptimizeView.as_view(), name='logistics-optimize-routes'),
    path('logistics/routes/', TransitRouteListView.as_view(), name='logistics-routes-list'),

    # 5. K2K Command Center (B2B Admin Dashboard)
    path('command-center/overview/', CommandCenterOverviewView.as_view(), name='command-center-overview'),

    # 6. Farmer Multilingual Voice/UI NLP Assistant
    path('voice-assistant/process-command/', VoiceAssistantCommandView.as_view(), name='voice-assistant-command'),

    # Standard Browsable REST Resources
    path('', include(router.urls)),
]
