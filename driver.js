let driversList = [];
let currentDriverId = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadDrivers();
  await loadDriverPortal();
  setInterval(loadDriverPortal, 4000);
});

async function loadDrivers() {
  try {
    const res = await fetch('/api/drivers');
    if (!res.ok) return;
    driversList = await res.json();
    
    const select = document.getElementById('driverSelect');
    select.innerHTML = driversList.map(d => `
      <option value="${d.id}">${escapeHtml(d.name)} (${d.vehicle_type})</option>
    `).join('');

    if (driversList.length > 0) {
      currentDriverId = driversList[0].id;
    }
  } catch (err) {
    console.error(err);
  }
}

function onDriverChanged() {
  currentDriverId = parseInt(document.getElementById('driverSelect').value);
  loadDriverPortal();
}

async function loadDriverPortal() {
  if (!currentDriverId) return;

  try {
    const res = await fetch('/api/trips');
    if (!res.ok) return;
    const allTrips = await res.json();

    // 1. 檢視此司機目前是否有進行中行程
    const myTrip = allTrips.find(t => 
      t.driver_id === currentDriverId && 
      ['ASSIGNED', 'EN_ROUTE', 'PICKED_UP'].includes(t.status)
    );

    renderMyActiveTrip(myTrip);

    // 2. 呈現所有待接單行程
    const available = allTrips.filter(t => t.status === 'NEW');
    renderAvailableJobs(available);

  } catch (err) {
    console.error('更新司機頁面失敗:', err);
  }
}

function renderMyActiveTrip(trip) {
  const section = document.getElementById('myActiveTripSection');
  if (!trip) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');
  document.getElementById('activeTripId').innerText = `#預約單-${trip.id}`;
  document.getElementById('activePickup').innerText = trip.pickup_location;
  document.getElementById('activeTime').innerText = `出發時間: ${trip.pickup_datetime}`;
  document.getElementById('activeAirport').innerText = trip.destination_airport;
  document.getElementById('activeFare').innerText = `NT$ ${Math.round(trip.estimated_fare).toLocaleString()}`;
  document.getElementById('activeCustomerName').innerText = `${trip.customer_name || '貴賓乘客'}`;
  document.getElementById('activePaxBags').innerText = `${trip.passengers} 位乘客 | ${trip.luggage} 件行李 | ${trip.vehicle_type}`;

  const callBtn = document.getElementById('activeCallBtn');
  if (trip.customer_phone) {
    callBtn.href = `tel:${trip.customer_phone}`;
    callBtn.classList.remove('opacity-50', 'pointer-events-none');
  } else {
    callBtn.href = '#';
    callBtn.classList.add('opacity-50', 'pointer-events-none');
  }

  // 狀態推進按鈕
  const btnContainer = document.getElementById('tripActionBtns');
  if (trip.status === 'ASSIGNED') {
    btnContainer.innerHTML = `
      <button onclick="updateMyTripStatus(${trip.id}, 'EN_ROUTE')" class="col-span-2 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
        <i class="fa-solid fa-route"></i>
        <span>我已出發前往上車地點</span>
      </button>
    `;
  } else if (trip.status === 'EN_ROUTE') {
    btnContainer.innerHTML = `
      <button onclick="updateMyTripStatus(${trip.id}, 'PICKED_UP')" class="col-span-2 py-2.5 bg-purple-600 hover:bg-purple-500 rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
        <i class="fa-solid fa-user-check"></i>
        <span>乘客已上車前往機場</span>
      </button>
    `;
  } else if (trip.status === 'PICKED_UP') {
    btnContainer.innerHTML = `
      <button onclick="updateMyTripStatus(${trip.id}, 'COMPLETED')" class="col-span-2 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
        <i class="fa-solid fa-flag-checkered"></i>
        <span>已平安送達機場航廈 (完成行程)</span>
      </button>
    `;
  }
}

function renderAvailableJobs(trips) {
  const container = document.getElementById('availableJobsList');
  document.getElementById('jobCountBadge').innerText = trips.length;

  if (trips.length === 0) {
    container.innerHTML = `
      <div class="p-8 text-center bg-slate-900 border border-slate-800 rounded-2xl text-slate-500">
        <i class="fa-solid fa-circle-check text-2xl text-emerald-500/50 mb-2"></i>
        <p class="text-xs font-medium">目前所有機場行程皆已被接單！</p>
        <p class="text-[11px] text-slate-600 mt-1">請保持待命，各 LINE 叫車群組有新送機需求將第一時間通知。</p>
      </div>
    `;
    return;
  }

  container.innerHTML = trips.map(t => `
    <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-4 shadow-lg space-y-3 transition">
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-500/30">
          #單號-${t.id}
        </span>
        <span class="text-xs font-bold text-emerald-400 font-mono">
          NT$ ${Math.round(t.estimated_fare).toLocaleString()}
        </span>
      </div>

      <div class="space-y-1.5 text-xs">
        <div>
          <p class="text-[11px] text-slate-400 flex items-center gap-1">
            <i class="fa-solid fa-location-dot text-rose-400"></i> 上車地點:
          </p>
          <p class="font-bold text-white pl-4">${escapeHtml(t.pickup_location)}</p>
        </div>

        <div>
          <p class="text-[11px] text-slate-400 flex items-center gap-1">
            <i class="fa-solid fa-plane-arrival text-sky-400"></i> 目的地機場:
          </p>
          <p class="font-bold text-sky-300 pl-4">${escapeHtml(t.destination_airport)}</p>
        </div>

        <div class="flex justify-between items-center text-[11px] text-slate-400 pt-1 border-t border-slate-800">
          <span><i class="fa-regular fa-clock text-amber-400 mr-1"></i> ${escapeHtml(t.pickup_datetime)}</span>
          <span><i class="fa-solid fa-users mr-1"></i> ${t.passengers} 人 | ${t.luggage} 箱</span>
        </div>
      </div>

      <button onclick="acceptTrip(${t.id})" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
        <i class="fa-solid fa-check"></i>
        <span>接單 (我來跑這趟送機)</span>
      </button>
    </div>
  `).join('');
}

async function acceptTrip(tripId) {
  if (!currentDriverId) {
    alert('請先選擇司機身分');
    return;
  }

  try {
    const res = await fetch(`/api/trips/${tripId}/assign`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ driver_id: currentDriverId })
    });

    if (res.ok) {
      loadDriverPortal();
    } else {
      const err = await res.json();
      alert(`接單失敗: ${err.detail || '行程可能已被其他司機搶先接單'}`);
    }
  } catch (err) {
    alert('網路通訊異常。');
  }
}

async function updateMyTripStatus(tripId, status) {
  try {
    const res = await fetch(`/api/trips/${tripId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });

    if (res.ok) {
      loadDriverPortal();
    }
  } catch (err) {
    console.error(err);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}
