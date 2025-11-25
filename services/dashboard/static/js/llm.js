function acceptRecommendation() {
    fetch('/api/accept_recommendation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert('Success: ' + data.message);
            // Optionally refresh the page or update the UI
            location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to accept recommendation');
    });
}


// Add this to your status update function
function updateAcceptButton(state) {
    const acceptBtn = document.getElementById('accept-recommendation-btn');
    if (state.best_config && state.best_config.config) {
        acceptBtn.disabled = false;
        acceptBtn.title = 'Accept the current LLM recommendation';
    } else {
        acceptBtn.disabled = true;
        acceptBtn.title = 'No recommendation available';
    }
}
