document.addEventListener('DOMContentLoaded', () => {
    // 1. Onboarding Form
    const onboardForm = document.getElementById('onboard-form');
    if (onboardForm) {
        onboardForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('company-name').value;
            const sector = document.getElementById('sector').value;

            const res = await fetch('/api/v1/tenants/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, sector })
            });

            if (res.ok) {
                const data = await res.json();
                localStorage.setItem('tenant_id', data.tenant_id);
                localStorage.setItem('tenant_name', data.name);
                localStorage.setItem('tenant_sector', data.sector);
                window.location.href = '/dashboard';
            } else {
                alert("Error registering tenant");
            }
        });
    }

    // 2. Dashboard Logic
    const tenantId = localStorage.getItem('tenant_id');
    const sectorDisplay = document.getElementById('sector-display');
    const tenantName = document.getElementById('tenant-name');
    
    if (sectorDisplay && tenantName) {
        if (!tenantId) window.location.href = '/';
        sectorDisplay.innerText = localStorage.getItem('tenant_sector');
        tenantName.innerText = localStorage.getItem('tenant_name');
    }

    const fileUpload = document.getElementById('file-upload');
    const analyzeBtn = document.getElementById('analyze-btn');
    const fileListDisplay = document.createElement('div');
    fileListDisplay.className = "mt-2 text-sm text-gray-700";
    if(fileUpload) {
        fileUpload.parentNode.insertBefore(fileListDisplay, fileUpload.nextSibling);
    }
    
    let selectedFiles = [];

    if (fileUpload) {
        fileUpload.addEventListener('change', () => {
            if (fileUpload.files.length > 0) {
                // Accumulate files
                for(let i=0; i<fileUpload.files.length; i++) {
                    selectedFiles.push(fileUpload.files[i]);
                }
                analyzeBtn.classList.remove('hidden');
                
                // Update display
                fileListDisplay.innerHTML = "<strong>Selected Files:</strong><br/>" + selectedFiles.map(f => f.name).join('<br/>');
            }
        });
    }

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async () => {
            if (selectedFiles.length === 0) return;

            document.getElementById('loading').classList.remove('hidden');
            analyzeBtn.classList.add('hidden');

            const formData = new FormData();
            formData.append('tenant_id', tenantId);
            for (let i = 0; i < selectedFiles.length; i++) {
                formData.append('files', selectedFiles[i]);
            }

            try {
                const res = await fetch('/api/v1/upload/analyze', {
                    method: 'POST',
                    body: formData
                });

                if (res.ok) {
                    const data = await res.json();
                    displayResults(data);
                } else {
                    alert("Analysis failed. Check backend logs or API keys.");
                }
            } catch (err) {
                console.error(err);
                alert("Network error.");
            } finally {
                document.getElementById('loading').classList.add('hidden');
            }
        });
    }

    function displayResults(data) {
        document.getElementById('results-section').classList.remove('hidden');
        
        // Schema mapping
        document.getElementById('primary-key').innerText = data.schema_mapping.primary_entity_key;
        const schemaList = document.getElementById('schema-list');
        schemaList.innerHTML = '';
        data.schema_mapping.tables.forEach(t => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${t.file_name}</strong> - Role: <em>${t.role}</em> (Dropped: ${t.noise_columns.join(', ') || 'None'})`;
            schemaList.appendChild(li);
        });

        // Predictions
        const tbody = document.getElementById('predictions-body');
        tbody.innerHTML = '';
        
        // Sort by risk
        data.predictions.sort((a,b) => b.prediction.churn_probability - a.prediction.churn_probability);

        data.predictions.forEach(item => {
            if (item.prediction.risk_tier !== 'LOW') {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${item.prediction.entity_id}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600 font-bold">${item.prediction.risk_tier}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${(item.prediction.churn_probability * 100).toFixed(1)}%</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-indigo-600 hover:text-indigo-900 cursor-pointer view-playbook">View Playbook</td>
                `;
                tr.querySelector('.view-playbook').addEventListener('click', () => openDrawer(item));
                tbody.appendChild(tr);
            }
        });
    }

    const drawer = document.getElementById('drawer');
    const closeDrawerBtn = document.getElementById('close-drawer');

    if (closeDrawerBtn) {
        closeDrawerBtn.addEventListener('click', () => {
            drawer.classList.add('translate-x-full');
        });
    }

    function openDrawer(item) {
        const content = document.getElementById('drawer-content');
        
        let driversHtml = '';
        if (item.prediction.primary_drivers) {
            driversHtml = `<strong>Drivers:</strong> <ul class="list-disc pl-4 text-sm text-red-600">` + item.prediction.primary_drivers.map(d => `<li>${d}</li>`).join('') + `</ul>`;
        } else if (item.prediction.root_cause) {
            driversHtml = `<strong>Root Cause:</strong> <p class="text-sm text-red-600">${item.prediction.root_cause}</p>`;
        } else if (item.prediction.dormancy_type) {
            driversHtml = `<strong>Dormancy Type:</strong> <p class="text-sm text-red-600">${item.prediction.dormancy_type}</p>`;
        }

        content.innerHTML = `
            <div class="mb-4">
                <span class="text-xs font-bold bg-red-100 text-red-800 px-2 py-1 rounded">Risk: ${item.prediction.risk_tier}</span>
                <span class="text-xs font-bold bg-gray-100 text-gray-800 px-2 py-1 rounded ml-2">ID: ${item.prediction.entity_id}</span>
            </div>
            <div class="mb-6 bg-gray-50 p-4 rounded border">
                ${driversHtml}
            </div>
            <hr class="my-4">
            <h3 class="font-bold text-indigo-700 mb-2">Automated Action Plan</h3>
            <div class="bg-indigo-50 p-4 rounded border border-indigo-100">
                <p class="text-sm mb-2"><strong>Channel:</strong> ${item.playbook.channel}</p>
                <p class="text-sm mb-2"><strong>Action Type:</strong> ${item.playbook.action_type}</p>
                <div class="bg-white p-3 border rounded text-sm font-mono text-gray-700 mt-2">
                    ${item.playbook.action_payload}
                </div>
                <button class="mt-4 w-full bg-green-600 text-white py-2 rounded hover:bg-green-700 text-sm font-bold shadow">Deploy Intervention</button>
            </div>
        `;
        drawer.classList.remove('translate-x-full');
    }
});
