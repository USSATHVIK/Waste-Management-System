// Flash message auto-hide
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        let alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            alert.style.display = 'none';
        });
    }, 5000);
});

// Form validation
function validateForm() {
    let password = document.getElementById('password').value;
    if (password.length < 8) {
        alert('Password must be at least 8 characters long');
        return false;
    }
    return true;
}