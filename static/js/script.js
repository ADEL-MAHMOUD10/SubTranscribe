function updateFileName() {
    const fileInput = document.getElementById('file');
    const fileName = document.getElementById('file-name');
    fileName.textContent = fileInput.files[0] ? fileInput.files[0].name : 'No file chosen';
}

const form = document.getElementById('upload-form');
form.addEventListener('submit', function (e) {
    e.preventDefault();
    document.getElementById('progress-container').style.display = 'block';
    updateProgress();
    form.submit();
});

function updateProgress(transcriptId) {
    const interval = setInterval(() => {
        fetch('/progress')
            .then(response => response.json())
            .then(data => {
                const progressBar = document.getElementById('progress-bar');
                const progressText = document.getElementById('progress-text');
                const progressMessage = document.getElementById('progress-message');

                progressBar.value = data.status;
                progressText.textContent = `${data.status}%`;
                progressMessage.textContent = data.message;

                if (data.status >= 100) {
                    clearInterval(interval);

                    setTimeout(() => {
                        window.location.href = `/download/${transcriptId}`;
                    }, 1000); 
                }
            });
    }, 1000);
}


