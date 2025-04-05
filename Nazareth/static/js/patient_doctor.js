document.addEventListener("DOMContentLoaded", function () {
    const callNextBtn = document.getElementById("call-next");
    const notifyButtons = document.querySelectorAll(".btn-notify");
    const markSeenButtons = document.querySelectorAll(".btn-seen");

    // Call Next Patient
    if (callNextBtn) {
        callNextBtn.addEventListener("click", function () {
            alert("Calling the next patient...");

        });
    }

    // Notify Patient
    notifyButtons.forEach(button => {
        button.addEventListener("click", function () {
            const patientName = this.closest("tr").querySelector("td:nth-child(2)").textContent;
            alert(`Notifying ${patientName}...`);
            // Implement backend request logic here
        });
    });

    // Mark as Seen
    markSeenButtons.forEach(button => {
        button.addEventListener("click", function () {
            const row = this.closest("tr");
            row.style.opacity = "0.5"; // Dim the row to indicate patient seen
            alert("Patient marked as seen.");
            // Implement backend request logic here
        });
    });
});
