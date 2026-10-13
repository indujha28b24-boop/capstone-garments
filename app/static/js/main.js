// StitchTech ERP - General UI Interactions & Chart.js Dark Theme Defaults

if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#94A3B8';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.08)';
    if (Chart.defaults.scale) {
        Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.06)';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = '#94A3B8';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.08)';
    }
    // Password visibility toggle
    const toggleButtons = document.querySelectorAll('.toggle-password');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            const targetId = this.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                if (input.type === 'password') {
                    input.type = 'text';
                    this.innerHTML = '<i class="bi bi-eye-slash-fill"></i>';
                } else {
                    input.type = 'password';
                    this.innerHTML = '<i class="bi bi-eye-fill"></i>';
                }
            }
        });
    });

    // Mobile Sidebar Toggle
    const sidebarToggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('open');
        });
    }

    // Auto dismiss bootstrap alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});
