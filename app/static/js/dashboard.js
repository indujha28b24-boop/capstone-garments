// StitchTech ERP - Dashboard & Analytics Engine with Chart.js

document.addEventListener('DOMContentLoaded', function () {
    // 1. Initialize Analytics Charts if analytics canvas exists
    const ordersCanvas = document.getElementById('ordersChart');
    const stageCanvas = document.getElementById('stageChart');
    const machineCanvas = document.getElementById('machineChart');

    if (ordersCanvas) {
        fetch('/owner/api/analytics-data')
            .then(res => res.json())
            .then(data => {
                // Monthly Orders & Revenue Line Chart
                new Chart(ordersCanvas, {
                    type: 'line',
                    data: {
                        labels: data.months,
                        datasets: [{
                            label: 'Monthly Orders',
                            data: data.monthly_orders,
                            borderColor: '#0284c7',
                            backgroundColor: 'rgba(2, 132, 199, 0.15)',
                            tension: 0.4,
                            fill: true,
                            borderWidth: 3,
                            pointRadius: 5
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: true, position: 'top' }
                        },
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });

                // Production Stage Bottleneck Bar Chart
                if (stageCanvas) {
                    new Chart(stageCanvas, {
                        type: 'bar',
                        data: {
                            labels: data.stages,
                            datasets: [{
                                label: 'Orders at Stage',
                                data: data.stage_counts,
                                backgroundColor: ['#38bdf8', '#818cf8', '#fbbf24', '#34d399', '#a78bfa', '#f472b6', '#10b981'],
                                borderRadius: 8
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: true }
                            }
                        }
                    });
                }

                // Machine Status Doughnut Chart
                if (machineCanvas) {
                    new Chart(machineCanvas, {
                        type: 'doughnut',
                        data: {
                            labels: data.machine_statuses,
                            datasets: [{
                                data: data.machine_counts,
                                backgroundColor: ['#10b981', '#f59e0b', '#ef4444']
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { position: 'bottom' }
                            }
                        }
                    });
                }

                // Delay Reasons Chart
                const delayCanvas = document.getElementById('delayChart');
                if (delayCanvas && data.delay_reasons) {
                    new Chart(delayCanvas, {
                        type: 'bar',
                        data: {
                            labels: data.delay_reasons,
                            datasets: [{
                                label: 'Delay Incidents',
                                data: data.delay_counts,
                                backgroundColor: '#ef4444',
                                borderRadius: 6
                            }]
                        },
                        options: {
                            responsive: true,
                            indexAxis: 'y',
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                x: { beginAtZero: true, ticks: { stepSize: 1 } }
                            }
                        }
                    });
                }
            })
            .catch(err => console.error('Error fetching analytics data:', err));
    }

    // 2. Interactive AI Fabric Calculation
    const aiFabricBtn = document.getElementById('calcFabricBtn');
    if (aiFabricBtn) {
        aiFabricBtn.addEventListener('click', function () {
            const garmentType = document.getElementById('aiGarmentType').value;
            const quantity = document.getElementById('aiQuantity').value;

            fetch('/owner/api/ai/fabric', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ garment_type: garmentType, quantity: quantity })
            })
            .then(res => res.json())
            .then(res => {
                document.getElementById('aiFabricResult').innerHTML = `
                    <div class="alert alert-info border-0 shadow-sm mt-3">
                        <h6 class="fw-bold mb-2"><i class="bi bi-cpu-fill me-2"></i>AI Fabric Requirement Prediction</h6>
                        <ul class="mb-0 small">
                            <li>Base Requirement: <strong>${res.base_requirement_meters} meters</strong></li>
                            <li>Cutting Waste (8%): <strong>+${res.waste_allowance_meters} meters</strong></li>
                            <li><strong>Total Required Stock: <span class="fs-5 text-primary">${res.total_fabric_meters} meters</span></strong> (~${res.estimated_rolls} rolls)</li>
                        </ul>
                    </div>
                `;
            });
        });
    }

    // 3. Interactive AI Workforce Calculation
    const aiWorkforceBtn = document.getElementById('calcWorkforceBtn');
    if (aiWorkforceBtn) {
        aiWorkforceBtn.addEventListener('click', function () {
            const garmentType = document.getElementById('aiWfGarmentType').value;
            const quantity = document.getElementById('aiWfQuantity').value;
            const deadlineDays = document.getElementById('aiWfDeadline').value;

            fetch('/owner/api/ai/workforce', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ garment_type: garmentType, quantity: quantity, deadline_days: deadlineDays })
            })
            .then(res => res.json())
            .then(res => {
                document.getElementById('aiWorkforceResult').innerHTML = `
                    <div class="alert alert-success border-0 shadow-sm mt-3">
                        <h6 class="fw-bold mb-2"><i class="bi bi-people-fill me-2"></i>AI Workforce Allocation Prediction</h6>
                        <ul class="mb-0 small">
                            <li>Total Standard Production Hours: <strong>${res.total_production_hours} hrs</strong></li>
                            <li>Required Worker-Days: <strong>${res.required_worker_days} days</strong></li>
                            <li><strong>Recommended Workforce: <span class="fs-5 text-success">${res.recommended_workers} Workers</span></strong> for ${res.deadline_days} days</li>
                        </ul>
                    </div>
                `;
            });
        });
    }
});
