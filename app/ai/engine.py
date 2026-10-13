import math
from datetime import datetime
from app.models import Order, Inventory, Machine, Worker, Alert, db

GARMENT_FABRIC_RATES = {
    'Shirts': 1.7,      # 1.7 meters per shirt
    'Denim': 1.5,       # 1.5 meters per jean
    'T-Shirts': 1.2,    # 1.2 meters per t-shirt
    'Dresses': 2.5,     # 2.5 meters per dress
    'Jackets': 2.2      # 2.2 meters per jacket
}

# Standard Allowed Minutes (SAM) per garment unit
GARMENT_SAM = {
    'Shirts': 22.0,
    'Denim': 35.0,
    'T-Shirts': 15.0,
    'Dresses': 30.0,
    'Jackets': 45.0
}

STAGE_SEQUENCE = [
    'Order Confirmed',
    'Fabric Received',
    'Cutting',
    'Stitching',
    'Quality Check',
    'Packing',
    'Delivered'
]

class AIEngine:
    
    @staticmethod
    def predict_fabric_requirement(garment_type, quantity):
        rate = GARMENT_FABRIC_RATES.get(garment_type, 1.6)
        base_meters = rate * int(quantity)
        waste_allowance = base_meters * 0.08  # 8% cutting waste
        total_required = round(base_meters + waste_allowance, 2)
        
        return {
            'garment_type': garment_type,
            'quantity': int(quantity),
            'base_requirement_meters': round(base_meters, 2),
            'waste_allowance_meters': round(waste_allowance, 2),
            'total_fabric_meters': total_required,
            'estimated_rolls': math.ceil(total_required / 50.0)  # 50m per roll
        }

    @staticmethod
    def predict_workforce_requirement(garment_type, quantity, deadline_days):
        sam = GARMENT_SAM.get(garment_type, 25.0)
        total_sam = sam * int(quantity)
        total_hours = total_sam / 60.0
        
        # 8 working hours per day per worker, 85% expected efficiency
        effective_hours_per_worker = 8.0 * 0.85
        deadline_days = max(1, int(deadline_days))
        
        total_worker_days = total_hours / effective_hours_per_worker
        recommended_workers = math.ceil(total_worker_days / deadline_days)
        
        return {
            'garment_type': garment_type,
            'quantity': int(quantity),
            'deadline_days': deadline_days,
            'total_production_hours': round(total_hours, 1),
            'required_worker_days': round(total_worker_days, 1),
            'recommended_workers': recommended_workers
        }

    @staticmethod
    def predict_delivery_delay_risk(order):
        if not order or not order.deadline:
            return {'risk_level': 'Low Risk', 'probability': 10, 'reason': 'No order deadline set.'}
            
        now = datetime.utcnow()
        days_left = (order.deadline - now).total_seconds() / (24 * 3600)
        progress = order.progress_percentage
        
        if order.status == 'Delivered' or progress >= 100:
            return {'risk_level': 'Low Risk', 'probability': 0, 'reason': 'Order already delivered.'}
            
        if days_left <= 0:
            return {
                'risk_level': 'High Risk',
                'probability': 98,
                'reason': 'Deadline has already passed!'
            }
            
        remaining_progress = 100 - progress
        required_rate_per_day = remaining_progress / max(0.5, days_left)
        
        if required_rate_per_day > 35 or (days_left < 2 and progress < 50):
            risk_level = 'High Risk'
            probability = min(95, round(60 + (required_rate_per_day * 0.8)))
            reason = f'Requires unrealistic {round(required_rate_per_day, 1)}% completion speed per day.'
        elif required_rate_per_day > 18 or (days_left < 4 and progress < 60):
            risk_level = 'Medium Risk'
            probability = round(35 + (required_rate_per_day * 0.9))
            reason = f'Tight schedule! Needs {round(required_rate_per_day, 1)}% daily progress.'
        else:
            risk_level = 'Low Risk'
            probability = max(5, round(required_rate_per_day * 0.8))
            reason = 'Production is progressing on target schedule.'
            
        return {
            'risk_level': risk_level,
            'probability': min(99, probability),
            'reason': reason,
            'days_left': round(days_left, 1),
            'required_daily_rate': round(required_rate_per_day, 1)
        }

    @staticmethod
    def calculate_worker_productivity(completed_tasks, target_tasks, attendance_count, total_days):
        if total_days <= 0:
            return {'productivity_score': 85.0, 'grade': 'A'}
            
        task_ratio = min(1.3, completed_tasks / max(1, target_tasks))
        attendance_ratio = min(1.0, attendance_count / max(1, total_days))
        
        score = (task_ratio * 70.0) + (attendance_ratio * 30.0)
        score = round(min(100.0, score), 1)
        
        if score >= 90:
            grade = 'A+'
        elif score >= 80:
            grade = 'A'
        elif score >= 70:
            grade = 'B'
        else:
            grade = 'C'
            
        return {'productivity_score': score, 'grade': grade}

    @staticmethod
    def generate_ai_assistant_recommendations():
        recommendations = []
        
        # 1. Check Orders for Delay Risks
        active_orders = Order.query.filter(Order.status != 'Delivered').all()
        for order in active_orders:
            risk_info = AIEngine.predict_delivery_delay_risk(order)
            if risk_info['risk_level'] == 'High Risk':
                recommendations.append({
                    'category': 'Delay Risk',
                    'icon': 'bi-exclamation-triangle-fill',
                    'color': 'danger',
                    'title': f'Critical Delay Risk for Order #{order.id} ({order.garment_type})',
                    'message': f'Order #{order.id} ({order.quantity} pcs) has a {risk_info["probability"]}% chance of delay. {risk_info["reason"]}',
                    'action': f'Reallocate 3 extra workers to {order.current_stage} department immediately.'
                })
            elif risk_info['risk_level'] == 'Medium Risk':
                recommendations.append({
                    'category': 'Schedule Alert',
                    'icon': 'bi-clock-history',
                    'color': 'warning',
                    'title': f'Tight Timeline for Order #{order.id}',
                    'message': f'Order #{order.id} requires {risk_info["required_daily_rate"]}% daily output to meet deadline in {risk_info["days_left"]} days.',
                    'action': 'Monitor floor output closely today.'
                })

        # 2. Check Low Inventory Stock
        low_inventory = Inventory.query.filter(Inventory.quantity <= Inventory.minimum_stock).all()
        for item in low_inventory:
            recommendations.append({
                'category': 'Inventory Alert',
                'icon': 'bi-box-seam',
                'color': 'warning',
                'title': f'Low Stock: {item.item_name}',
                'message': f'Current quantity of {item.item_name} ({item.quantity} {item.unit}) is below minimum stock threshold ({item.minimum_stock} {item.unit}).',
                'action': f'Issue purchase order for {item.minimum_stock * 2} {item.unit} immediately.'
            })

        # 3. Check Machine Maintenance
        maintenance_machines = Machine.query.filter(
            (Machine.status == 'Maintenance') | (Machine.status == 'Idle')
        ).all()
        for machine in maintenance_machines:
            recommendations.append({
                'category': 'Machine Optimization',
                'icon': 'bi-gear-wide-connected',
                'color': 'info',
                'title': f'Machine Idle/Maintenance: {machine.machine_name}',
                'message': f'{machine.machine_name} ({machine.machine_type}) is currently in status [{machine.status}].',
                'action': 'Schedule technician inspection or reassign waiting orders to operational lines.'
            })

        # 4. Check Workforce Utilization
        available_workers = Worker.query.filter_by(status='Available').count()
        busy_workers = Worker.query.filter_by(status='Busy').count()
        total_workers = max(1, available_workers + busy_workers)
        utilization = round((busy_workers / total_workers) * 100, 1)

        if utilization < 50 and active_orders:
            recommendations.append({
                'category': 'Workforce Optimization',
                'icon': 'bi-people-fill',
                'color': 'primary',
                'title': 'Unallocated Worker Capacity',
                'message': f'Worker utilization rate is currently {utilization}%. {available_workers} workers are available.',
                'action': 'Assign unallocated workers to Stitching and Quality Check lines.'
            })
            
        if not recommendations:
            recommendations.append({
                'category': 'System Status',
                'icon': 'bi-check-circle-fill',
                'color': 'success',
                'title': 'Factory Operating at Optimum Efficiency',
                'message': 'No immediate production bottlenecks or inventory shortages detected across floor lines.',
                'action': 'Continue standard operating workflow.'
            })
            
        return recommendations

    @staticmethod
    def get_fashion_trend_intelligence():
        return {
            'trending_designs': [
                {'name': 'Oversized Shirts', 'popularity': 92, 'image': 'images/inventory/fabric_rolls.jpg', 'growth': '+24%'},
                {'name': 'Summer Dresses', 'popularity': 88, 'image': 'images/workers/dept_quality.jpg', 'growth': '+19%'},
                {'name': 'Denim Jackets', 'popularity': 85, 'image': 'images/workers/dept_cutting.jpg', 'growth': '+15%'}
            ],
            'trending_colors': [
                {'name': 'Black', 'hex': '#1e293b', 'popularity': 95},
                {'name': 'White', 'hex': '#cbd5e1', 'popularity': 90},
                {'name': 'Pastel Pink', 'hex': '#f472b6', 'popularity': 88},
                {'name': 'Olive Green', 'hex': '#65a30d', 'popularity': 84},
                {'name': 'Beige / Tan', 'hex': '#d97706', 'popularity': 79}
            ],
            'trending_fabrics': [
                {'name': 'Cotton', 'demand_pct': 42, 'growth': '+18%', 'eco_rating': 'A+'},
                {'name': 'Denim', 'demand_pct': 28, 'growth': '+12%', 'eco_rating': 'A'},
                {'name': 'Linen', 'demand_pct': 18, 'growth': '+24%', 'eco_rating': 'A+'},
                {'name': 'Silk', 'demand_pct': 12, 'growth': '+8%', 'eco_rating': 'B+'}
            ],
            'ai_recommendations': [
                "Demand for oversized cotton shirts is increasing. Consider increasing production by 20%.",
                "Pastel color dresses are trending for summer season.",
                "Denim jacket demand may increase next month."
            ],
            'decision_support': {
                'product': 'Oversized Cotton Shirt',
                'recommended_units': 5000,
                'required_fabric_meters': 8500,
                'required_workers': 25,
                'expected_demand': 'High'
            },
            'sustainability_index': 92.5,
            'ai_forecast': 'Spring/Summer 2026 demands sustainable lightweight natural weaves, oversized silhouettes, and pastel palette accents.'
        }
