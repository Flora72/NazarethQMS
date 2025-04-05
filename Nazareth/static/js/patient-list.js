function editPatient(queueNumber) {
    alert(`Edit patient with Queue Number: ${queueNumber}`);

}

function deletePatient(queueNumber) {
    if (confirm('Are you sure you want to delete this patient?')) {
        fetch(`/delete-patient/${queueNumber}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Patient deleted successfully.');
                document.querySelector(`tr[data-queue-number="${queueNumber}"]`).remove();
            } else {
                alert('Failed to delete the patient: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while deleting the patient.');
        });
    }
}

// Helper function to get CSRF token
function getCSRFToken() {
    const cookieValue = document.cookie.split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue;
}


function moveToNext(queueNumber) {
    fetch(`/move-patient-next/${queueNumber}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(), // Include CSRF token
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Patient moved to the next stage.');
        } else {
            alert('Failed to move the patient: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while moving the patient.');
    });
}

function updateDepartment(queueNumber, department) {
    fetch(`/update-department/${queueNumber}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ department: department })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Department updated successfully.');
        } else {
            alert('Failed to update department: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while updating the department.');
    });
}
