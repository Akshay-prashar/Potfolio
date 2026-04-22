let pc = null;
let localStream = null;

const videoElement = document.getElementById('videoElement');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusOverlay = document.getElementById('statusOverlay');

function updateStatus(msg, state = 'info') {
    statusOverlay.textContent = msg;
    if (state === 'error') {
        statusOverlay.style.color = '#fca5a5';
        statusOverlay.style.borderColor = '#991b1b';
    } else if (state === 'success') {
        statusOverlay.style.color = '#86efac';
        statusOverlay.style.borderColor = '#166534';
    } else {
        statusOverlay.style.color = '#e2e8f0';
        statusOverlay.style.borderColor = '#334155';
    }
}

async function startStream() {
    startBtn.disabled = true;
    updateStatus("Requesting Camera...", "info");
    
    try {
        // Request maximum ideal HD quality without unstable `min` bounds that cause crashes
        localStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment',
                width: { ideal: 1920 },
                height: { ideal: 1080 },
                frameRate: { ideal: 30 }
            },
            audio: false
        });
        
        videoElement.srcObject = localStream;
        updateStatus("Connecting to App...", "info");

        // Set up RTCPeerConnection
        pc = new RTCPeerConnection();

        // Send local tracks
        localStream.getTracks().forEach(track => {
            pc.addTrack(track, localStream);
        });

        // Generate offer
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // Wait for ICE gathering to complete before POST
        await new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
                
                // Timeout after 2.5 seconds just in case it hangs locally
                setTimeout(() => {
                    pc.removeEventListener('icegatheringstatechange', checkState);
                    resolve();
                }, 2500);
            }
        });

        // Send to Python server via HTTP POST
        const response = await fetch('/offer', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Device': navigator.userAgent
            },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const answer = await response.json();
        await pc.setRemoteDescription(answer);

        updateStatus("Streaming Live", "success");
        stopBtn.disabled = false;

    } catch (e) {
        console.error(e);
        updateStatus("Error: " + e.message, "error");
        startBtn.disabled = false;
        if (localStream) {
            localStream.getTracks().forEach(t => t.stop());
        }
    }
}

function stopStream() {
    if (pc) {
        pc.close();
        pc = null;
    }
    if (localStream) {
        localStream.getTracks().forEach(t => t.stop());
        localStream = null;
    }
    videoElement.srcObject = null;
    
    updateStatus("Disconnected", "info");
    startBtn.disabled = false;
    stopBtn.disabled = true;
}

startBtn.addEventListener('click', startStream);
stopBtn.addEventListener('click', stopStream);
