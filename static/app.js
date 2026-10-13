const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const queueList = document.getElementById('queue-list');
const imageElement = document.getElementById('image');
const imageContainer = document.getElementById('image-container');
const noImageMsg = document.getElementById('no-image');
const loadingMsg = document.getElementById('loading');
const editorTitle = document.getElementById('editor-title');
const statusBar = document.getElementById('status-bar');
const btnSave = document.getElementById('btn-save');
const btnSkip = document.getElementById('btn-skip');

let queue = [];
let currentIndex = -1;
let cropper = null;

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// File Upload Handlers
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(files) {
    for (let file of files) {
        if (!file.type.startsWith('image/')) continue;
        queue.push({ file: file, status: 'pending', id: Date.now() + Math.random() });
    }
    renderQueue();
    if (currentIndex === -1 && queue.length > 0) {
        loadItem(0);
    }
}

function renderQueue() {
    queueList.innerHTML = '';
    queue.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = `list-group-item queue-item ${index === currentIndex ? 'active' : ''} ${item.status === 'done' ? 'done text-success' : ''}`;
        div.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1 text-truncate" style="max-width: 150px;">${escapeHtml(item.file.name)}</h6>
                <small>${item.status === 'done' ? '✅' : (index === currentIndex ? '⏳' : '⌛')}</small>
            </div>
        `;
        div.onclick = () => {
            if (item.status !== 'done') loadItem(index);
        };
        queueList.appendChild(div);
    });
}

async function loadItem(index) {
    if (index >= queue.length) {
        // Done with all
        currentIndex = -1;
        renderQueue();
        noImageMsg.classList.remove('d-none');
        imageContainer.classList.add('d-none');
        btnSave.disabled = true;
        btnSkip.disabled = true;
        statusBar.innerHTML = "<span class='text-success fw-bold'>🎉 Tüm fotoğraflar başarıyla işlendi! (Masaüstü eOkul_Hazir_Fotograflar klasörüne bakınız)</span>";
        return;
    }

    currentIndex = index;
    const item = queue[index];
    renderQueue();
    
    noImageMsg.classList.add('d-none');
    imageContainer.classList.add('d-none');
    loadingMsg.classList.remove('d-none');
    btnSave.disabled = true;
    btnSkip.disabled = false;
    editorTitle.innerText = `Düzenleniyor: ${item.file.name}`;
    statusBar.innerText = "Yüz algılanıyor...";

    // Destroy old cropper
    if (cropper) { cropper.destroy(); cropper = null; }

    const formData = new FormData();
    formData.append('image', item.file);

    try {
        const response = await fetch('/api/detect', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (data.error) {
            statusBar.innerHTML = `<span class="text-danger">Hata: ${escapeHtml(data.error)}</span>`;
            loadingMsg.classList.add('d-none');
            return;
        }

        imageElement.src = data.image_data;
        imageElement.onload = () => {
            loadingMsg.classList.add('d-none');
            imageContainer.classList.remove('d-none');
            
            // Wait for image render
            setTimeout(() => {
                cropper = new Cropper(imageElement, {
                    aspectRatio: 133 / 171,
                    viewMode: 1,
                    autoCropArea: 1,
                    ready() {
                        // Set the auto-detected crop box
                        const box = data.crop_box;
                        const imageData = cropper.getImageData();
                        
                        // Crop box is in natural pixels. Convert to canvas coordinates.
                        const ratio = imageData.width / imageData.naturalWidth;
                        
                        cropper.setCropBoxData({
                            left: box.x * ratio,
                            top: box.y * ratio,
                            width: box.width * ratio,
                            height: box.height * ratio
                        });
                        
                        btnSave.disabled = false;
                        if (box.face_found) {
                            statusBar.innerHTML = "<span class='text-primary'>Yüz otomatik algılandı ve ortalandı. Gerekirse fare ile ince ayar yapabilirsiniz.</span>";
                        } else {
                            statusBar.innerHTML = "<span class='text-warning'>Yüz bulunamadı. Lütfen kırpma alanını manuel ayarlayın.</span>";
                        }
                    }
                });
            }, 100);
        };
    } catch (e) {
        statusBar.innerHTML = `<span class="text-danger">Bağlantı hatası: ${escapeHtml(e.message)}</span>`;
        loadingMsg.classList.add('d-none');
    }
}

btnSkip.onclick = () => {
    loadItem(currentIndex + 1);
};

btnSave.onclick = async () => {
    if (!cropper) return;
    
    btnSave.disabled = true;
    btnSkip.disabled = true;
    statusBar.innerText = "Kaydediliyor ve e-Okul için optimize ediliyor (>20 KB)...";

    // Get cropped canvas at original resolution
    const canvas = cropper.getCroppedCanvas();
    const dataUrl = canvas.toDataURL('image/png'); // Send lossless to backend, let backend do JPEG compression

    try {
        const item = queue[currentIndex];
        const res = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: dataUrl,
                filename: item.file.name
            })
        });
        
        const data = await res.json();
        
        if (data.error) {
            statusBar.innerHTML = `<span class="text-danger">Kayıt hatası: ${escapeHtml(data.error)}</span>`;
            btnSave.disabled = false;
            btnSkip.disabled = false;
        } else {
            // Success!
            const sizeKB = (data.size / 1024).toFixed(1);
            statusBar.innerHTML = `<span class="text-success">✅ Kaydedildi! (${sizeKB} KB) -> ${escapeHtml(data.path)}</span>`;
            item.status = 'done';
            
            // Move to next
            setTimeout(() => {
                loadItem(currentIndex + 1);
            }, 500);
        }
    } catch (e) {
        statusBar.innerHTML = `<span class="text-danger">Kayıt hatası: ${escapeHtml(e.message)}</span>`;
        btnSave.disabled = false;
        btnSkip.disabled = false;
    }
};
