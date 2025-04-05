 document.getElementById('registerForm').addEventListener('submit', function(event) {
        event.preventDefault();

        const name = document.getElementById('name').value;
        const department = document.getElementById('department').value;
        const priority = document.getElementById('priority').value;

        fetch('/register/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, department, priority })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = '/queue_status/';
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => console.error('Error:', error));
    });

