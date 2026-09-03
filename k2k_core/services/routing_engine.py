"""
Dynamic Route Optimization Engine
Consolidates small agricultural batches across micro-hubs into commercial truckloads.
Dynamically calculates sweep routes prioritizing highly perishable crops (e.g., leafy greens).
"""
from decimal import Decimal, ROUND_HALF_UP
import uuid
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from k2k_core.models import (
    MicroHub,
    ProduceBatch,
    Vehicle,
    TransitRoute,
    RouteWaypoint,
    CropPerishabilityTier,
    BatchStatus
)


class DynamicRoutingEngine:

    PERISHABILITY_WEIGHTS = {
        CropPerishabilityTier.URGENT_24H: Decimal('3.50'),
        CropPerishabilityTier.HIGH_48H: Decimal('2.20'),
        CropPerishabilityTier.MEDIUM_7D: Decimal('1.30'),
        CropPerishabilityTier.STABLE_30D: Decimal('1.00'),
    }

    @classmethod
    def calculate_batch_urgency(cls, batch: ProduceBatch) -> Decimal:
        """
        Computes urgency index based on crop perishability tier and hours elapsed at hub.
        """
        base_multiplier = cls.PERISHABILITY_WEIGHTS.get(
            batch.crop.perishability_tier,
            Decimal('1.00')
        )
        
        # Calculate hours since harvest
        now = timezone.now()
        hours_elapsed = max(Decimal('1.00'), Decimal(str((now - batch.harvested_at).total_seconds() / 3600.0)))
        
        # Urgency increases as hours increase towards standard shelf life
        shelf_life = Decimal(str(batch.crop.standard_shelf_life_hours))
        decay_factor = min(Decimal('3.00'), Decimal('1.00') + (hours_elapsed / shelf_life))
        
        return (base_multiplier * decay_factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def optimize_and_dispatch_fleet(cls) -> list:
        """
        Scans all micro-hubs for uncollected produce batches, clusters loads by vehicle payload,
        and generates prioritized waypoint sequences.
        """
        # Find ready batches awaiting transit
        ready_batches = ProduceBatch.objects.filter(
            current_status__in=[
                BatchStatus.PRICE_ACCEPTED,
                BatchStatus.IN_COLD_STORAGE,
                BatchStatus.AI_GRADED
            ],
            current_hub__isnull=False
        ).select_related('crop', 'current_hub')

        if not ready_batches.exists():
            return []

        # Find idle or available vehicles
        available_vehicles = Vehicle.objects.filter(
            status__in=[Vehicle.VehicleStatus.IDLE, Vehicle.VehicleStatus.DISPATCHED]
        )
        if not available_vehicles.exists():
            # Auto-provision a fleet vehicle if none exist for hackathon demo
            vehicle = Vehicle.objects.create(
                vehicle_number="MH-12-K2K-9001",
                driver_name="Ramesh Yadav",
                driver_phone="+919876543210",
                max_payload_kg=Decimal('3500.00'),
                has_cold_chain=True,
                status=Vehicle.VehicleStatus.IDLE
            )
            available_vehicles = [vehicle]

        # Group batches by MicroHub and compute Hub Perishability Urgency
        hubs_data = {}
        for b in ready_batches:
            hub = b.current_hub
            if hub.id not in hubs_data:
                hubs_data[hub.id] = {
                    'hub': hub,
                    'batches': [],
                    'total_kg': Decimal('0.00'),
                    'weighted_urgency_sum': Decimal('0.00'),
                    'urgent_leafy_count': 0
                }
            
            weight = b.accepted_quantity_kg if b.accepted_quantity_kg else b.initial_quantity_kg
            urgency = cls.calculate_batch_urgency(b)
            
            hubs_data[hub.id]['batches'].append(b)
            hubs_data[hub.id]['total_kg'] += weight
            hubs_data[hub.id]['weighted_urgency_sum'] += (weight * urgency)
            if b.crop.perishability_tier == CropPerishabilityTier.URGENT_24H:
                hubs_data[hub.id]['urgent_leafy_count'] += 1

        # Calculate average urgency score per hub
        hub_queue = []
        for hub_info in hubs_data.values():
            if hub_info['total_kg'] > Decimal('0.00'):
                avg_urgency = (hub_info['weighted_urgency_sum'] / hub_info['total_kg']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                avg_urgency = Decimal('1.00')
            
            hub_queue.append({
                'hub': hub_info['hub'],
                'batches': hub_info['batches'],
                'total_kg': hub_info['total_kg'],
                'avg_urgency': avg_urgency,
                'has_urgent_leafy': hub_info['urgent_leafy_count'] > 0
            })

        # Sort hubs: highest urgency first (perishables like spinach/coriander get swept first)
        hub_queue.sort(key=lambda x: (x['has_urgent_leafy'], x['avg_urgency']), reverse=True)

        created_routes = []
        vehicle_idx = 0
        current_time = timezone.now()

        for vehicle in available_vehicles:
            if not hub_queue:
                break

            route_uuid = uuid.uuid4().hex[:6].upper()
            route_id = f"ROUTE-{timezone.now().strftime('%Y%m%d')}-{route_uuid}"
            
            # Create TransitRoute
            route = TransitRoute.objects.create(
                route_id=route_id,
                vehicle=vehicle,
                target_retail_hub="Pune-Mumbai Central Mega Aggregation Center",
                total_distance_km=Decimal('85.50'),
                estimated_duration_hours=Decimal('3.50'),
                priority_urgency_score=hub_queue[0]['avg_urgency'] if hub_queue else Decimal('50.00'),
                status=TransitRoute.RouteStatus.ACTIVE
            )

            current_load = Decimal('0.00')
            waypoint_seq = 1
            allocated_hubs = []

            for hub_entry in list(hub_queue):
                hub = hub_entry['hub']
                hub_batches = hub_entry['batches']
                hub_weight = hub_entry['total_kg']

                if current_load + hub_weight <= vehicle.max_payload_kg:
                    # Allocate full hub
                    waypoint = RouteWaypoint.objects.create(
                        route=route,
                        hub=hub,
                        sequence_order=waypoint_seq,
                        action=RouteWaypoint.WaypointAction.PICKUP,
                        planned_weight_kg=hub_weight,
                        estimated_arrival=current_time + timedelta(hours=waypoint_seq * 0.8)
                    )
                    waypoint.batches.set(hub_batches)
                    
                    # Update batches status
                    for b in hub_batches:
                        b.current_status = BatchStatus.CONSOLIDATED_FOR_TRANSIT
                        b.save()

                    current_load += hub_weight
                    waypoint_seq += 1
                    allocated_hubs.append(hub_entry)
                elif current_load < vehicle.max_payload_kg:
                    # Partial allocation of batches up to vehicle capacity
                    remaining_capacity = vehicle.max_payload_kg - current_load
                    partial_batches = []
                    partial_weight = Decimal('0.00')
                    
                    for b in hub_batches:
                        b_wt = b.accepted_quantity_kg if b.accepted_quantity_kg else b.initial_quantity_kg
                        if partial_weight + b_wt <= remaining_capacity:
                            partial_batches.append(b)
                            partial_weight += b_wt
                            b.current_status = BatchStatus.CONSOLIDATED_FOR_TRANSIT
                            b.save()

                    if partial_batches:
                        waypoint = RouteWaypoint.objects.create(
                            route=route,
                            hub=hub,
                            sequence_order=waypoint_seq,
                            action=RouteWaypoint.WaypointAction.PICKUP,
                            planned_weight_kg=partial_weight,
                            estimated_arrival=current_time + timedelta(hours=waypoint_seq * 0.8)
                        )
                        waypoint.batches.set(partial_batches)
                        current_load += partial_weight
                        waypoint_seq += 1

                    # Break as truck is full
                    break

            # Remove allocated hubs from queue
            for h in allocated_hubs:
                hub_queue.remove(h)

            vehicle.status = Vehicle.VehicleStatus.DISPATCHED
            vehicle.save()

            created_routes.append(route)

        return created_routes
