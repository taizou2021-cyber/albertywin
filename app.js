// ==========================================
// 台北機場專車 - 全功能三合一單頁應用程式
// ==========================================

let currentFilter = '';
let currentTripForAssign = null;
let cachedDrivers = [];
let groups = [];
let currentGroup = null;
let currentDriverId = null;
let currentDriverFilter = 'ALL';
let cachedAllTrips = [];

const SCENARIOS = {
  taoyuan: "明天早上 06:30 需要一輛商務車前往桃園機場第二航廈，從台北晶華酒店大廳出發，4位大人、3件28吋大行李、1個登機箱、1組高爾夫球具，搭長榮 BR87，聯絡電話 0912-345-678",
  songshan: "明天下午 14:00 需要一台轎車去松山機場國際線，從信義區君悅酒店大門出發，2人、2件28吋大箱，班機 JL098，電話 0933-882-910",
  return_arrival: "班機 BR88 預計明日上午 08:30 抵達桃園機場第二航廈，2位大人、2件28吋大行李，需要專車接送回台北市信義區，電話 0933-882-910",
  rejection: "請問明天早上 9 點可以派一輛車送我們去九份老街一日遊嗎？2 個人有行李。",
  template: "上車地點：台北市大安區和平大苑\n前往機場：桃園機場一航\n出發時間：2026-10-06 05:30\n搭乘人數：3位\n行李件數：28吋大箱2個、登機箱1個、嬰兒推車1台\n航班編號：JX800\n聯絡電話：0955-771-320",
  help: "/help"
};

document.addEventListener('DOMContentLoaded', async () => {
  // 檢查網址參數是否指定開啟特定分頁 (?tab=driver 或 #simulator)
  const urlParams = new URLSearchParams(window.location.search);
  const tabParam = urlParams.get('tab') || window.location.hash.replace('#', '') || 'dispatch';
  switchTab(tabParam);

  // 初始化各模組資料
  await loadAllData();
  await loadSimulatorGroups();

  // 每 3.5 秒自動同步一次，讓「模擬器叫車 ➔ 調度中心跳出 ➔ 司機端接單」實現跨分頁即時聯動！
  setInterval(loadAllData, 3500);

  // 初始化直客預約表單、行李防呆與隧道監控
  initBookingDate();
  onLuggageOrPaxChanged();
  checkTunnelStatus();
  setInterval(checkTunnelStatus, 8000);
});

// ==========================================
// 1. 三合一主分頁切換邏輯
// ==========================================

function switchTab(tabName) {
  const validTabs = ['dispatch', 'driver', 'book', 'simulator', 'guide'];
  if (!validTabs.includes(tabName)) {
    tabName = 'dispatch';
  }

  // 隱藏所有分頁內容
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.remove('active');
  });

  // 重置導航按鈕樣式
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('bg-sky-600', 'text-white', 'font-semibold', 'shadow');
    btn.classList.add('text-slate-400');
  });

  // 顯示選中分頁
  const targetContent = document.getElementById(`tab-${tabName}`);
  const targetNav = document.getElementById(`nav-${tabName}`);
  if (targetContent) targetContent.classList.add('active');
  if (targetNav) {
    targetNav.classList.remove('text-slate-400');
    targetNav.classList.add('bg-sky-600', 'text-white', 'font-semibold', 'shadow');
  }

  // 同步更新網址 hash，方便使用者儲存書籤
  if (history.replaceState) {
    history.replaceState(null, null, `#${tabName}`);
  }
}

// ==========================================
// 2. 全域資料同步核心 (調度中心 + 司機接單端)
// ==========================================

async function loadAllData() {
  await Promise.all([
    fetchStats(),
    fetchTripsAndSyncDriver(),
    fetchGroups(),
    fetchDrivers()
  ]);
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('statTotal').innerText = data.total_trips;
    document.getElementById('statNew').innerText = data.new_trips;
    document.getElementById('statActive').innerText = data.active_trips;
    document.getElementById('statCompleted').innerText = data.completed_trips;
    document.getElementById('statGroups').innerText = data.total_groups;
    document.getElementById('statDrivers').innerText = data.active_drivers;

    // 若有待接單行程，在頂部「司機手機接單」分頁按鈕顯示醒目標記
    const navBadge = document.getElementById('navDriverBadge');
    if (data.new_trips > 0) {
      navBadge.innerText = data.new_trips;
      navBadge.classList.remove('hidden');
    } else {
      navBadge.classList.add('hidden');
    }
  } catch (err) {
    console.error('載入統計資料失敗:', err);
  }
}

async function fetchTripsAndSyncDriver() {
  try {
    const res = await fetch('/api/trips');
    if (!res.ok) return;
    const allTrips = await res.json();

    // 1. 渲染調度中心清單 (根據篩選條件)
    let filteredTrips = allTrips;
    if (currentFilter) {
      filteredTrips = allTrips.filter(t => t.status === currentFilter);
    }
    renderDispatchTrips(filteredTrips);

    // 2. 同步渲染司機接單端
    renderDriverPortal(allTrips);
  } catch (err) {
    console.error('載入行程失敗:', err);
  }
}

// ==========================================
// 3. 調度控制中心功能
// ==========================================

function renderDispatchTrips(trips) {
  const container = document.getElementById('tripsList');
  if (!trips || trips.length === 0) {
    container.innerHTML = `
      <div class="py-12 text-center text-slate-500">
        <i class="fa-solid fa-plane-slash text-3xl mb-2 text-slate-600"></i>
        <p class="text-sm font-medium">此類別目前尚無預約送機行程。</p>
        <p class="text-xs text-slate-600 mt-1">您可以切換至「LINE 多群組模擬器」測試送出叫車需求，行程將即時呈現在此！</p>
      </div>
    `;
    return;
  }

  container.innerHTML = trips.map(trip => {
    let badge = '';
    if (trip.status === 'NEW') {
      badge = `<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span>待派車接單</span>`;
    } else if (trip.status === 'ASSIGNED') {
      badge = `<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">已派車</span>`;
    } else if (trip.status === 'EN_ROUTE') {
      badge = `<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">司機前往中</span>`;
    } else if (trip.status === 'PICKED_UP') {
      badge = `<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">已上車前往機場</span>`;
    } else if (trip.status === 'COMPLETED') {
      badge = `<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">已送達機場</span>`;
    } else {
      badge = `<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">${trip.status}</span>`;
    }

    const driverInfo = trip.driver_name ? `
      <div class="mt-2 text-xs bg-slate-950/60 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <div class="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">
            <i class="fa-solid fa-id-badge"></i>
          </div>
          <div>
            <p class="font-medium text-white">${escapeHtml(trip.driver_name)} <span class="text-slate-400 font-normal">(${escapeHtml(trip.driver_vehicle)})</span></p>
            <p class="text-[11px] text-slate-400 font-mono">車牌: <span class="text-sky-300 font-bold">${escapeHtml(trip.driver_plate)}</span> | 手機: <a href="tel:${trip.driver_phone}" class="text-emerald-400 hover:underline">${escapeHtml(trip.driver_phone)}</a></p>
          </div>
        </div>
        <div class="flex items-center space-x-1">
          <button onclick="changeTripStatus(${trip.id}, 'COMPLETED')" class="px-2.5 py-1 bg-emerald-600/30 hover:bg-emerald-600/60 text-emerald-300 rounded text-[11px] font-medium border border-emerald-500/40">
            完成行程
          </button>
        </div>
      </div>
    ` : `
      <div class="mt-2 flex items-center justify-between bg-amber-950/20 p-2.5 rounded-xl border border-amber-500/20">
        <span class="text-xs text-amber-300 flex items-center gap-1.5">
          <i class="fa-solid fa-triangle-exclamation"></i>
          等待車隊派車 / 司機接單
        </span>
        <button onclick="openAssignModal(${JSON.stringify(trip).replace(/"/g, '&quot;')})" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-semibold shadow transition">
          <i class="fa-solid fa-user-plus mr-1"></i> 指派司機
        </button>
      </div>
    `;

    return `
      <div class="p-4 bg-slate-950/40 hover:bg-slate-950/80 rounded-xl transition border border-slate-800 space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center space-x-2">
            <span class="font-mono text-xs font-bold text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-500/30">#${trip.id}</span>
            ${trip.trip_type === 'ARRIVAL' ? `
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                <i class="fa-solid fa-plane-arrival"></i> 返台接機
              </span>
            ` : `
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30 flex items-center gap-1">
                <i class="fa-solid fa-plane-departure"></i> 台北送機
              </span>
            `}
            ${trip.matched_trip_id ? `
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center gap-1">
                <i class="fa-solid fa-repeat"></i> 配對連環單 #${trip.matched_trip_id}
              </span>
            ` : ''}
            <span class="text-xs text-slate-300 font-medium flex items-center gap-1">
              <i class="fa-brands fa-line text-emerald-400 text-sm"></i>
              ${escapeHtml(trip.line_group_name || 'LINE 叫車群組')}
            </span>
          </div>
          <div class="flex items-center space-x-2">
            ${badge}
            <span class="text-xs text-slate-400 font-mono">${formatTime(trip.created_at)}</span>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-slate-900/60 p-3 rounded-xl border border-slate-800">
          <div>
            <p class="text-slate-400 flex items-center gap-1.5 mb-0.5">
              <i class="fa-solid fa-location-dot text-rose-400"></i>
              <span>上車接送地點:</span>
            </p>
            <p class="text-sm font-semibold text-white pl-4">${escapeHtml(trip.pickup_location)}</p>
            <p class="text-[11px] text-amber-400 pl-4 mt-1 font-mono">
              <i class="fa-regular fa-clock mr-1"></i> ${escapeHtml(trip.pickup_datetime)}
            </p>
          </div>

          <div>
            <p class="text-slate-400 flex items-center gap-1.5 mb-0.5">
              <i class="fa-solid fa-plane text-sky-400"></i>
              <span>目的地機場 / 返北航廈:</span>
            </p>
            <p class="text-sm font-semibold text-sky-300 pl-4 flex items-center gap-1.5">
              <span>${escapeHtml(trip.destination_airport)}</span>
              <span class="text-[10px] bg-sky-500/20 text-sky-300 px-1.5 py-0.2 rounded font-normal">機場專車</span>
            </p>
            ${trip.terminal_flight_no ? `<p class="text-[11px] text-slate-300 pl-4 mt-1 font-mono"><i class="fa-solid fa-ticket mr-1 text-slate-400"></i> 航班: ${escapeHtml(trip.terminal_flight_no)}</p>` : ''}
          </div>
        </div>

        <div class="flex flex-wrap items-center justify-between text-xs text-slate-300 gap-2">
          <div class="flex items-center space-x-3">
            <span><i class="fa-solid fa-users text-slate-400 mr-1"></i> ${trip.passengers} 位乘客</span>
            <span><i class="fa-solid fa-suitcase-rolling text-sky-400 mr-1"></i> ${escapeHtml(trip.luggage_breakdown || (trip.luggage + ' 件行李'))}</span>
            <span class="bg-slate-800 px-2 py-0.5 rounded text-[11px] text-slate-300 border border-slate-700">${escapeHtml(trip.vehicle_type)}</span>
          </div>

          <div class="flex items-center space-x-3">
            <span><i class="fa-solid fa-user text-slate-400 mr-1"></i> ${escapeHtml(trip.customer_name || '貴賓')}</span>
            ${trip.customer_phone ? `<a href="tel:${trip.customer_phone}" class="text-emerald-400 hover:underline font-mono"><i class="fa-solid fa-phone mr-1"></i> ${escapeHtml(trip.customer_phone)}</a>` : '<span class="text-slate-500">未留電話</span>'}
            <div class="text-right">
              <span class="font-bold text-emerald-400 text-sm">NT$ ${Math.round(trip.estimated_fare).toLocaleString()}</span>
              <span class="text-[10px] text-slate-400 ml-1">(司機實收 NT$ ${Math.round(trip.driver_payout || trip.estimated_fare - 50).toLocaleString()})</span>
            </div>
          </div>
        </div>

        ${trip.raw_message ? `
          <div class="text-[11px] text-slate-400 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-800 italic">
            <span class="font-semibold text-slate-300 not-italic">群組原文：</span> "${escapeHtml(trip.raw_message)}"
          </div>
        ` : ''}

        ${driverInfo}
      </div>
    `;
  }).join('');
}

async function fetchGroups() {
  try {
    const res = await fetch('/api/groups');
    if (!res.ok) return;
    groups = await res.json();
    document.getElementById('groupCountBadge').innerText = groups.length;
    
    const container = document.getElementById('groupsList');
    if (groups.length === 0) {
      container.innerHTML = `<p class="text-xs text-slate-500 italic">尚無註冊之群組。</p>`;
      return;
    }

    container.innerHTML = groups.map(g => `
      <div class="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between text-xs">
        <div class="min-w-0 pr-2">
          <p class="font-medium text-white truncate flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            ${escapeHtml(g.group_name)}
          </p>
          <p class="text-[10px] text-slate-500 font-mono mt-0.5">群組識別: ${escapeHtml(g.group_id.slice(-12))}</p>
        </div>
        <div class="text-right flex-shrink-0">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">
            ${g.trip_count} 趟預約
          </span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('載入群組失敗:', err);
  }
}

async function fetchDrivers() {
  try {
    const res = await fetch('/api/drivers');
    if (!res.ok) return;
    cachedDrivers = await res.json();
    
    // 1. 調度中心司機名單
    const container = document.getElementById('driversList');
    if (cachedDrivers.length === 0) {
      container.innerHTML = `<p class="text-xs text-slate-500 italic">目前無登記司機。</p>`;
    } else {
      container.innerHTML = cachedDrivers.map(d => `
        <div class="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between text-xs">
          <div>
            <p class="font-medium text-white">${escapeHtml(d.name)}</p>
            <p class="text-[11px] text-slate-400 font-mono">${escapeHtml(d.vehicle_model)} (${escapeHtml(d.license_plate)})</p>
          </div>
          <div class="text-right">
            <span class="text-amber-400 font-semibold text-xs">★ ${d.rating.toFixed(1)}</span>
            <p class="text-[10px] text-slate-500">${d.total_trips} 趟</p>
          </div>
        </div>
      `).join('');
    }

    // 2. 司機端身分選單 (若尚未初始化)
    const select = document.getElementById('driverSelect');
    if (select && select.children.length === 0 && cachedDrivers.length > 0) {
      select.innerHTML = cachedDrivers.map(d => `
        <option value="${d.id}">${escapeHtml(d.name)} - ${escapeHtml(d.license_plate)}</option>
      `).join('');
      currentDriverId = cachedDrivers[0].id;
    }
  } catch (err) {
    console.error('載入司機名單失敗:', err);
  }
}

function setFilter(status) {
  currentFilter = status;
  document.querySelectorAll('.filter-tab').forEach(tab => {
    if (tab.getAttribute('data-status') === status) {
      tab.classList.remove('text-slate-400');
      tab.classList.add('bg-sky-600', 'text-white');
    } else {
      tab.classList.remove('bg-sky-600', 'text-white');
      tab.classList.add('text-slate-400');
    }
  });
  fetchTripsAndSyncDriver();
}

function openAssignModal(trip) {
  currentTripForAssign = trip;
  document.getElementById('modalTripId').innerText = trip.id;
  document.getElementById('modalAirport').innerText = trip.destination_airport;
  document.getElementById('modalPickup').innerText = trip.pickup_location;
  document.getElementById('modalTime').innerText = trip.pickup_datetime;
  document.getElementById('modalPax').innerText = `${trip.passengers} 位乘客，${trip.luggage} 件行李 (${trip.vehicle_type})`;

  const select = document.getElementById('modalDriverSelect');
  select.innerHTML = cachedDrivers.map(d => `
    <option value="${d.id}">${escapeHtml(d.name)} - ${escapeHtml(d.vehicle_model)} [${escapeHtml(d.license_plate)}] (${d.vehicle_type})</option>
  `).join('');

  document.getElementById('assignModal').classList.remove('hidden');
}

function closeAssignModal() {
  document.getElementById('assignModal').classList.add('hidden');
  currentTripForAssign = null;
}

async function confirmAssignment() {
  if (!currentTripForAssign) return;
  const driverId = parseInt(document.getElementById('modalDriverSelect').value);
  if (!driverId) return;

  try {
    const res = await fetch(`/api/trips/${currentTripForAssign.id}/assign`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ driver_id: driverId })
    });

    if (res.ok) {
      closeAssignModal();
      loadAllData();
    } else {
      const err = await res.json();
      alert(`派車失敗: ${err.detail || '未知錯誤'}`);
    }
  } catch (e) {
    alert('派車網路傳輸錯誤');
  }
}

async function changeTripStatus(tripId, newStatus) {
  try {
    const res = await fetch(`/api/trips/${tripId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      loadAllData();
    }
  } catch (e) {
    console.error(e);
  }
}

function openAddDriverModal() {
  document.getElementById('addDriverModal').classList.remove('hidden');
}

function closeAddDriverModal() {
  document.getElementById('addDriverModal').classList.add('hidden');
}

async function submitNewDriver(e) {
  e.preventDefault();
  const name = document.getElementById('newDriverName').value.trim();
  const phone = document.getElementById('newDriverPhone').value.trim();
  const vehicle_model = document.getElementById('newDriverVehicle').value.trim();
  const license_plate = document.getElementById('newDriverPlate').value.trim();
  const vehicle_type = document.getElementById('newDriverType').value;

  try {
    const res = await fetch('/api/drivers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone, vehicle_model, license_plate, vehicle_type, is_active: true })
    });
    if (res.ok) {
      closeAddDriverModal();
      document.getElementById('addDriverForm').reset();
      fetchDrivers();
      fetchStats();
    } else {
      alert('新增司機失敗。');
    }
  } catch (err) {
    alert('連線失敗。');
  }
}

// ==========================================
// 4. 司機手機接單端功能
// ==========================================
// 4. 司機手機接單端功能 (吸引外部運將核心利器)
// ==========================================

function onDriverChanged() {
  currentDriverId = parseInt(document.getElementById('driverSelect').value);
  fetchTripsAndSyncDriver();
}

function setDriverFilter(filter) {
  currentDriverFilter = filter;
  ['all', 'bundle', 'tomorrow'].forEach(id => {
    const btn = document.getElementById(`driver-tab-${id}`);
    if (btn) {
      btn.classList.remove('bg-sky-600', 'text-white');
      btn.classList.add('text-slate-400');
    }
  });

  const activeBtn = document.getElementById(
    filter === 'ALL' ? 'driver-tab-all' : (filter === 'RETURN_BUNDLE' ? 'driver-tab-bundle' : 'driver-tab-tomorrow')
  );
  if (activeBtn) {
    activeBtn.classList.remove('text-slate-400');
    activeBtn.classList.add('bg-sky-600', 'text-white');
  }

  const desc = document.getElementById('driverFilterDesc');
  if (desc) {
    if (filter === 'ALL') {
      desc.innerText = '群組一發送叫車需求立即同步跳出，點擊按鈕一鍵搶單：';
    } else if (filter === 'RETURN_BUNDLE') {
      desc.innerText = '💡【回程不空車】：去程送機到機場後，順風承接回程接機單，一趟賺兩趟車資，實收翻倍！';
    } else if (filter === 'TOMORROW') {
      desc.innerText = '📅【明日預約班表】：提前鎖定明日清晨早鳥送機行程，安心排班出車！';
    }
  }

  renderDriverPortal(cachedAllTrips);
}

function renderDriverPortal(allTrips) {
  cachedAllTrips = allTrips;
  if (!currentDriverId && cachedDrivers.length > 0) {
    currentDriverId = cachedDrivers[0].id;
  }
  if (!currentDriverId) return;

  // 1. 檢視該司機目前承接之任務
  const myTrip = allTrips.find(t => 
    t.driver_id === currentDriverId && 
    ['ASSIGNED', 'EN_ROUTE', 'PICKED_UP'].includes(t.status)
  );

  const myTripSection = document.getElementById('myActiveTripSection');
  if (myTrip) {
    myTripSection.classList.remove('hidden');
    document.getElementById('activeTripId').innerText = `#預約單-${myTrip.id}`;
    document.getElementById('activePickup').innerText = myTrip.pickup_location;
    document.getElementById('activeTime').innerText = `出發時間: ${myTrip.pickup_datetime}`;
    document.getElementById('activeAirport').innerText = myTrip.destination_airport;
    const payout = Math.round(myTrip.driver_payout || myTrip.estimated_fare - 50);
    document.getElementById('activeFare').innerText = `NT$ ${payout.toLocaleString()}`;
    document.getElementById('activeCustomerName').innerText = `${myTrip.customer_name || '貴賓乘客'}`;
    const lugDesc = myTrip.luggage_breakdown || `${myTrip.luggage} 件行李`;
    document.getElementById('activePaxBags').innerText = `${myTrip.passengers} 位乘客 | ${lugDesc} | ${myTrip.vehicle_type}`;

    const matchedNotice = document.getElementById('activeMatchedNotice');
    if (myTrip.matched_trip_id) {
      const paired = allTrips.find(t => t.id === myTrip.matched_trip_id);
      if (paired) {
        matchedNotice.classList.remove('hidden');
        document.getElementById('activeMatchedText').innerText = `已綁定雙向連環單 #${paired.id}（${paired.trip_type === 'ARRIVAL' ? '回程接機' : '送機'}：${paired.pickup_location} ➔ ${paired.destination_airport}）`;
      } else {
        matchedNotice.classList.remove('hidden');
        document.getElementById('activeMatchedText').innerText = `已綁定雙向連環單 #${myTrip.matched_trip_id}`;
      }
    } else {
      matchedNotice.classList.add('hidden');
    }

    const callBtn = document.getElementById('activeCallBtn');
    if (myTrip.customer_phone) {
      callBtn.href = `tel:${myTrip.customer_phone}`;
      callBtn.classList.remove('opacity-50', 'pointer-events-none');
    } else {
      callBtn.href = '#';
      callBtn.classList.add('opacity-50', 'pointer-events-none');
    }

    const btnContainer = document.getElementById('tripActionBtns');
    if (myTrip.status === 'ASSIGNED') {
      btnContainer.innerHTML = `
        <button onclick="updateDriverTripStatus(${myTrip.id}, 'EN_ROUTE')" class="col-span-2 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
          <i class="fa-solid fa-route"></i>
          <span>我已出發前往上車地點</span>
        </button>
      `;
    } else if (myTrip.status === 'EN_ROUTE') {
      btnContainer.innerHTML = `
        <button onclick="updateDriverTripStatus(${myTrip.id}, 'PICKED_UP')" class="col-span-2 py-2.5 bg-purple-600 hover:bg-purple-500 rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
          <i class="fa-solid fa-user-check"></i>
          <span>乘客已上車前往目的地</span>
        </button>
      `;
    } else if (myTrip.status === 'PICKED_UP') {
      btnContainer.innerHTML = `
        <button onclick="updateDriverTripStatus(${myTrip.id}, 'COMPLETED')" class="col-span-2 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
          <i class="fa-solid fa-flag-checkered"></i>
          <span>已平安送達目的地航廈 (完成行程)</span>
        </button>
      `;
    }
  } else {
    myTripSection.classList.add('hidden');
  }

  // 2. 呈現所有待接單之行程 (NEW)
  let availableTrips = allTrips.filter(t => t.status === 'NEW');

  // 3. 找出「回程不空車」配對組 (去程 DEPARTURE + 回程 ARRIVAL 同一機場)
  const pairedDepIds = new Set();
  const pairedArrIds = new Set();
  const pairs = [];

  const depTrips = availableTrips.filter(t => t.trip_type === 'DEPARTURE');
  const arrTrips = availableTrips.filter(t => t.trip_type === 'ARRIVAL');

  for (const dep of depTrips) {
    if (pairedDepIds.has(dep.id)) continue;
    const depAirportCode = dep.destination_airport.includes('TSA') || dep.destination_airport.includes('松山') ? 'TSA' : 'TPE';
    const matchArr = arrTrips.find(a => {
      if (pairedArrIds.has(a.id)) return false;
      const arrAirportCode = (a.pickup_location.includes('TSA') || a.pickup_location.includes('松山') || a.destination_airport.includes('TSA')) ? 'TSA' : 'TPE';
      return arrAirportCode === depAirportCode;
    });

    if (matchArr) {
      pairedDepIds.add(dep.id);
      pairedArrIds.add(matchArr.id);
      pairs.push({ dep, arr: matchArr });
    }
  }

  // 4. 根據當前司機子分頁篩選
  if (currentDriverFilter === 'RETURN_BUNDLE') {
    // 僅顯示有回程配對的行程
    availableTrips = availableTrips.filter(t => pairedDepIds.has(t.id) || pairedArrIds.has(t.id));
  } else if (currentDriverFilter === 'TOMORROW') {
    // 僅顯示明日預約班表 (包含明天、早鳥、或明日日期)
    availableTrips = availableTrips.filter(t => 
      t.pickup_datetime.includes('明天') || 
      t.pickup_datetime.includes('明日') || 
      t.pickup_datetime.includes('早鳥')
    );
  }

  const availableContainer = document.getElementById('availableJobsList');
  document.getElementById('jobCountBadge').innerText = availableTrips.length;

  if (availableTrips.length === 0) {
    availableContainer.innerHTML = `
      <div class="p-8 text-center bg-slate-900 border border-slate-800 rounded-2xl text-slate-500">
        <i class="fa-solid fa-circle-check text-2xl text-emerald-500/50 mb-2"></i>
        <p class="text-xs font-medium">此類別目前尚無等待接單的行程！</p>
        <p class="text-[11px] text-slate-600 mt-1">請切換至「全部待接單」，或至模擬器測試叫車即時派單。</p>
      </div>
    `;
    return;
  }

  let html = '';

  // 若在全部或回程專區，且有配對組，優先在頂部渲染【回程不空車】雙向合購卡片！
  const renderedSingleTripIds = new Set();

  if (pairs.length > 0 && (currentDriverFilter === 'ALL' || currentDriverFilter === 'RETURN_BUNDLE')) {
    pairs.forEach(({ dep, arr }) => {
      renderedSingleTripIds.add(dep.id);
      renderedSingleTripIds.add(arr.id);

      const totalFare = dep.estimated_fare + arr.estimated_fare;
      const totalSystemFee = 100; // 50 * 2
      const netPayout = totalFare - totalSystemFee;
      const uberFee = Math.round(totalFare * 0.25);
      const savedUber = uberFee - totalSystemFee;

      html += `
        <div class="bg-gradient-to-b from-sky-950/60 via-slate-900 to-emerald-950/50 border-2 border-sky-500/60 rounded-2xl p-4 shadow-2xl space-y-3.5">
          
          <!-- 雙向套票頂部標籤 -->
          <div class="flex items-center justify-between">
            <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40 flex items-center gap-1.5">
              <i class="fa-solid fa-repeat text-sky-400 animate-spin" style="animation-duration: 4s;"></i>
              <span>【回程不空車】雙向連環單（去程送機 ＋ 回程接機）</span>
            </span>
            <span class="text-xs font-extrabold text-emerald-300 font-mono">
              實收 NT$ ${netPayout.toLocaleString()}
            </span>
          </div>

          <!-- 去程與回程兩段式明細 -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            
            <!-- 第 1 段：去程送機 -->
            <div class="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800 space-y-1">
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold text-sky-400 bg-sky-950/70 px-1.5 py-0.5 rounded border border-sky-500/30">
                  第 1 段・去程送機 #${dep.id}
                </span>
                <span class="text-[11px] font-mono text-emerald-400 font-bold">NT$ ${Math.round(dep.estimated_fare).toLocaleString()}</span>
              </div>
              <p class="font-semibold text-white truncate"><i class="fa-solid fa-location-dot text-rose-400 mr-1"></i>${escapeHtml(dep.pickup_location)}</p>
              <p class="text-[11px] text-slate-300 truncate"><i class="fa-solid fa-plane-departure text-sky-400 mr-1"></i>${escapeHtml(dep.destination_airport)}</p>
              <p class="text-[10px] text-amber-400 font-mono"><i class="fa-regular fa-clock mr-1"></i>${escapeHtml(dep.pickup_datetime)}</p>
            </div>

            <!-- 第 2 段：回程接機 -->
            <div class="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800 space-y-1">
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold text-emerald-400 bg-emerald-950/70 px-1.5 py-0.5 rounded border border-emerald-500/30">
                  第 2 段・回程接機 #${arr.id}
                </span>
                <span class="text-[11px] font-mono text-emerald-400 font-bold">NT$ ${Math.round(arr.estimated_fare).toLocaleString()}</span>
              </div>
              <p class="font-semibold text-white truncate"><i class="fa-solid fa-plane-arrival text-emerald-400 mr-1"></i>${escapeHtml(arr.pickup_location)}</p>
              <p class="text-[11px] text-slate-300 truncate"><i class="fa-solid fa-house text-indigo-400 mr-1"></i>${escapeHtml(arr.destination_airport)}</p>
              <p class="text-[10px] text-amber-400 font-mono"><i class="fa-regular fa-clock mr-1"></i>${escapeHtml(arr.pickup_datetime)}</p>
            </div>

          </div>

          <!-- 收益試算與對比 Uber 節省抽成 -->
          <div class="bg-slate-950/90 p-2.5 rounded-xl border border-slate-800 text-xs flex flex-wrap items-center justify-between gap-2">
            <div class="space-y-0.5">
              <p class="text-slate-400 text-[11px]">雙趟總車資 NT$ ${totalFare.toLocaleString()} - 系統費 NT$ 100</p>
              <p class="text-xs font-extrabold text-emerald-400">★ 司機實收：NT$ ${netPayout.toLocaleString()}</p>
            </div>
            <div class="text-right">
              <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold border border-emerald-500/30 inline-flex items-center gap-1">
                <i class="fa-solid fa-coins text-amber-400"></i>
                比 Uber 25% 抽成多賺 NT$ ${savedUber.toLocaleString()}
              </span>
            </div>
          </div>

          <!-- 接單按鈕組 -->
          <div class="space-y-1.5">
            <button onclick="acceptTripByDriver(${dep.id}, true)" class="w-full py-2.5 bg-gradient-to-r from-sky-600 to-emerald-600 hover:from-sky-500 hover:to-emerald-500 active:scale-[0.98] rounded-xl text-xs font-bold text-white transition shadow-lg flex items-center justify-center gap-2">
              <i class="fa-solid fa-bolt text-amber-300"></i>
              <span>⚡ 一鍵搶下雙向套票 (雙倍賺 NT$ ${netPayout.toLocaleString()})</span>
            </button>
            <div class="grid grid-cols-2 gap-2 text-[11px]">
              <button onclick="acceptTripByDriver(${dep.id}, false)" class="py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition text-center">
                僅單接第 1 段送機
              </button>
              <button onclick="acceptTripByDriver(${arr.id}, false)" class="py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition text-center">
                僅單接第 2 段回程
              </button>
            </div>
          </div>

        </div>
      `;
    });
  }

  // 5. 渲染其餘單趟行程 (未成對或在明日早鳥班表)
  const remainingTrips = availableTrips.filter(t => !renderedSingleTripIds.has(t.id));

  remainingTrips.forEach(t => {
    const fare = Math.round(t.estimated_fare);
    const payout = Math.round(t.driver_payout || fare - 50);
    const uberFee = Math.round(fare * 0.25);
    const savedUber = uberFee - 50;

    const isArrival = t.trip_type === 'ARRIVAL';

    html += `
      <div class="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-4 shadow-lg space-y-3 transition">
        
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-500/30">
              #單號-${t.id}
            </span>
            ${isArrival ? `
              <span class="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-bold border border-emerald-500/30 flex items-center gap-1">
                <i class="fa-solid fa-plane-arrival"></i> 返台接機
              </span>
            ` : `
              <span class="text-[10px] bg-sky-500/20 text-sky-300 px-2 py-0.5 rounded font-bold border border-sky-500/30 flex items-center gap-1">
                <i class="fa-solid fa-plane-departure"></i> 台北送機
              </span>
            `}
          </div>

          <div class="text-right">
            <span class="text-xs font-bold text-emerald-400 font-mono">
              實收 NT$ ${payout.toLocaleString()}
            </span>
            <p class="text-[9px] text-slate-500">(車資 NT$ ${fare.toLocaleString()} - 系統費 50)</p>
          </div>
        </div>

        <div class="space-y-1.5 text-xs">
          <div>
            <p class="text-[11px] text-slate-400 flex items-center gap-1">
              <i class="fa-solid fa-location-dot text-rose-400"></i> ${isArrival ? '機場接機位置' : '台北上車地點'}:
            </p>
            <p class="font-bold text-white pl-4">${escapeHtml(t.pickup_location)}</p>
          </div>

          <div>
            <p class="text-[11px] text-slate-400 flex items-center gap-1">
              <i class="fa-solid fa-plane text-sky-400"></i> ${isArrival ? '送達目的地' : '目的地機場'}:
            </p>
            <p class="font-bold text-sky-300 pl-4">${escapeHtml(t.destination_airport)}</p>
          </div>

          <div class="flex justify-between items-center text-[11px] text-slate-400 pt-1.5 border-t border-slate-800">
            <span><i class="fa-regular fa-clock text-amber-400 mr-1"></i> ${escapeHtml(t.pickup_datetime)}</span>
            <span><i class="fa-solid fa-users mr-1"></i> ${t.passengers} 人 | <i class="fa-solid fa-suitcase-rolling text-sky-400 mr-0.5"></i> ${escapeHtml(t.luggage_breakdown || (t.luggage + ' 箱'))} (${escapeHtml(t.vehicle_type)})</span>
          </div>
        </div>

        <!-- 收益亮點與 Uber 抽成比較 -->
        <div class="bg-slate-950/70 p-2 rounded-xl border border-slate-800 flex items-center justify-between text-[11px]">
          <span class="text-slate-400">免收 25% 抽成・實收 97%</span>
          <span class="text-emerald-400 font-semibold flex items-center gap-1">
            <i class="fa-solid fa-piggy-bank text-amber-400"></i>
            省下抽成 NT$ ${savedUber.toLocaleString()}
          </span>
        </div>

        <button onclick="acceptTripByDriver(${t.id}, false)" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] rounded-xl text-xs font-bold text-white transition shadow flex items-center justify-center gap-2">
          <i class="fa-solid fa-check"></i>
          <span>接單 (我來跑此趟・實收 NT$ ${payout.toLocaleString()})</span>
        </button>
      </div>
    `;
  });

  availableContainer.innerHTML = html;
}

async function acceptTripByDriver(tripId, bundleMatched = false) {
  if (!currentDriverId) {
    alert('請先選擇司機身分');
    return;
  }

  try {
    const res = await fetch(`/api/trips/${tripId}/assign`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        driver_id: currentDriverId,
        bundle_matched_trip: bundleMatched
      })
    });

    if (res.ok) {
      if (bundleMatched) {
        alert('🎉 恭喜！一鍵雙向連環接單成功！您已同時鎖定「去程送機」與「回程接機」，回程零空車，實收翻倍入帳！');
      } else {
        alert('🎉 接單成功！請依預約時間準時出車前往上車地點。');
      }
      loadAllData();
    } else {
      const err = await res.json();
      alert(`接單失敗: ${err.detail || '行程可能已被其他司機搶先接單'}`);
    }
  } catch (err) {
    alert('網路通訊異常。');
  }
}

async function updateDriverTripStatus(tripId, status) {
  try {
    const res = await fetch(`/api/trips/${tripId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });

    if (res.ok) {
      loadAllData();
    }
  } catch (err) {
    console.error(err);
  }
}

// ==========================================
// 5. LINE 多群組模擬器功能
// ==========================================

async function loadSimulatorGroups() {
  try {
    const res = await fetch('/api/groups');
    if (!res.ok) return;
    groups = await res.json();

    const select = document.getElementById('simGroupSelect');
    if (select) {
      select.innerHTML = groups.map(g => `
        <option value="${g.group_id}">${escapeHtml(g.group_name)}</option>
      `).join('');

      if (groups.length > 0) {
        currentGroup = groups[0];
        updateChatHeader();
      }
    }
  } catch (err) {
    console.error(err);
  }
}

function onGroupChanged() {
  const selectedId = document.getElementById('simGroupSelect').value;
  currentGroup = groups.find(g => g.group_id === selectedId) || null;
  updateChatHeader();
  clearChatLog();
}

function updateChatHeader() {
  if (currentGroup) {
    document.getElementById('chatHeaderTitle').innerText = currentGroup.group_name;
  }
}

function fillScenario(key) {
  const text = SCENARIOS[key];
  if (text) {
    document.getElementById('messageInput').value = text;
  }
}

function clearChatLog() {
  const container = document.getElementById('chatMessages');
  container.innerHTML = `
    <div class="flex justify-center">
      <span class="text-[11px] bg-slate-800 text-slate-400 px-3 py-1 rounded-full border border-slate-700">
        台北機場專車機器人已加入此群組
      </span>
    </div>
  `;
}

async function sendMessage(e) {
  e.preventDefault();
  if (!currentGroup) return;

  const input = document.getElementById('messageInput');
  const messageText = input.value.trim();
  const senderName = document.getElementById('simSenderName').value.trim() || '貴賓乘客';
  if (!messageText) return;

  appendUserMessage(senderName, messageText);
  input.value = '';

  try {
    const res = await fetch('/api/simulator/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        group_id: currentGroup.group_id,
        group_name: currentGroup.group_name,
        sender_name: senderName,
        message_text: messageText
      })
    });

    if (!res.ok) return;
    const result = await res.json();

    if (result.reply_flex) {
      appendBotFlexMessage(result.reply_flex);
    } else if (result.type === 'ignored') {
      appendSystemNotice('機器人監聽到訊息，但非機場叫車需求（靜默不干擾）');
    }

    // 觸發全域重新整理，調度中心與司機端立即呈現新訂單
    loadAllData();

  } catch (err) {
    console.error(err);
  }
}

function appendUserMessage(sender, text) {
  const container = document.getElementById('chatMessages');
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const bubble = document.createElement('div');
  bubble.className = 'flex flex-col items-end space-y-1';
  bubble.innerHTML = `
    <span class="text-[10px] text-slate-400 font-medium">${escapeHtml(sender)}</span>
    <div class="bg-emerald-600 text-white rounded-2xl rounded-tr-none px-3.5 py-2 text-xs max-w-xs sm:max-w-md shadow whitespace-pre-wrap">
      ${escapeHtml(text)}
    </div>
    <span class="text-[9px] text-slate-500 font-mono">${time}</span>
  `;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendBotFlexMessage(flex) {
  const container = document.getElementById('chatMessages');
  const bubbleObj = flex.contents || {};
  const header = bubbleObj.header || {};
  const body = bubbleObj.body || {};
  const footer = bubbleObj.footer || {};

  const headerBg = header.backgroundColor || '#0284c7';
  const headerTexts = (header.contents || []).flatMap(c => c.contents || [c]);
  const headerHtml = headerTexts.map(t => `<p class="font-bold text-xs" style="color: ${t.color || '#fff'}">${escapeHtml(t.text || '')}</p>`).join('');

  let bodyHtml = '';
  if (body.contents) {
    bodyHtml = body.contents.map(c => {
      if (c.type === 'text') {
        return `<p class="text-xs mb-1 whitespace-pre-wrap text-slate-200">${escapeHtml(c.text || '')}</p>`;
      } else if (c.type === 'separator') {
        return `<hr class="border-slate-700 my-2">`;
      } else if (c.type === 'box') {
        const sub = (c.contents || []).map(row => {
          if (row.type === 'box' && row.contents) {
            const label = row.contents[0]?.text || '';
            const val = row.contents[1]?.text || '';
            const valColor = row.contents[1]?.color || '#ffffff';
            return `
              <div class="flex text-xs py-0.5">
                <span class="w-20 text-slate-400 font-medium">${escapeHtml(label)}</span>
                <span class="flex-1 font-semibold" style="color: ${valColor}">${escapeHtml(val)}</span>
              </div>
            `;
          }
          return '';
        }).join('');
        return sub;
      }
      return '';
    }).join('');
  }

  let footerHtml = '';
  if (footer.contents) {
    footerHtml = footer.contents.map(f => `
      <p class="text-[11px] text-center font-medium mt-1" style="color: ${f.color || '#94a3b8'}">${escapeHtml(f.text || '')}</p>
    `).join('');
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'flex items-start space-x-2 my-2';
  wrapper.innerHTML = `
    <div class="w-8 h-8 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-xs flex-shrink-0 border border-sky-400/30">
      <i class="fa-solid fa-plane"></i>
    </div>
    <div class="max-w-xs sm:max-w-md w-full bg-slate-900 border border-slate-700 rounded-2xl overflow-hidden shadow-xl">
      <div class="px-4 py-2.5" style="background-color: ${headerBg}">
        ${headerHtml}
      </div>
      <div class="p-4 bg-slate-900/90 space-y-1">
        ${bodyHtml}
      </div>
      ${footerHtml ? `<div class="p-2.5 bg-slate-950/70 border-t border-slate-800">${footerHtml}</div>` : ''}
    </div>
  `;

  container.appendChild(wrapper);
  container.scrollTop = container.scrollHeight;
}

function appendSystemNotice(text) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'flex justify-center my-1';
  div.innerHTML = `<span class="text-[10px] text-slate-500 italic bg-slate-900 px-2 py-0.5 rounded">${escapeHtml(text)}</span>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ==========================================
// 6. LINE 機器人金鑰線上啟用
// ==========================================

async function checkLineSettingsStatus() {
  try {
    const res = await fetch('/api/settings/status');
    if (!res.ok) return;
    const data = await res.json();
    const badge = document.getElementById('lineLiveStatusBadge');
    if (!badge) return;

    if (data.is_configured) {
      badge.innerHTML = `<span class="text-emerald-400 font-bold flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>🟢 機器人已成功連線啟用</span>`;
    } else {
      badge.innerHTML = `<span class="text-amber-400 font-medium">⚪ 尚未填入 LINE 金鑰</span>`;
    }
  } catch (err) {
    console.error(err);
  }
}

async function saveLineCredentials(e) {
  e.preventDefault();
  const secret = document.getElementById('cfgChannelSecret').value.trim();
  const token = document.getElementById('cfgChannelToken').value.trim();
  if (!secret || !token) {
    alert('請完整填寫 Channel Secret 與 Channel Access Token！');
    return;
  }

  try {
    const res = await fetch('/api/settings/line-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_secret: secret,
        channel_access_token: token
      })
    });
    if (res.ok) {
      alert('🎉 恭喜！LINE 官方專車機器人金鑰儲存成功，即時調度服務已就緒！');
      checkLineSettingsStatus();
    } else {
      alert('儲存失敗，請檢查格式。');
    }
  } catch (err) {
    alert('網路連線失敗。');
  }
}

// ==========================================
// 7. 通用輔助函式
// ==========================================

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// 頁面載入時檢查金鑰狀態
setTimeout(checkLineSettingsStatus, 500);

// ==========================================
// 8. 顧客線上預約專區 (FB / IG / 社群直客)
// ==========================================

let bookTripType = 'DEPARTURE';

function initBookingDate() {
  const dateInput = document.getElementById('bookDate');
  if (dateInput && !dateInput.value) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    dateInput.value = tomorrow.toISOString().split('T')[0];
  }
}

function setBookTripType(type) {
  bookTripType = type;
  const depBtn = document.getElementById('bookTypeDepBtn');
  const arrBtn = document.getElementById('bookTypeArrBtn');
  const airportLabel = document.getElementById('bookAirportLabel');
  const locLabel = document.getElementById('bookLocationLabel');
  const locInput = document.getElementById('bookLocation');

  if (type === 'DEPARTURE') {
    if (depBtn) depBtn.className = 'py-2.5 px-3 rounded-xl font-bold transition flex items-center justify-center gap-1.5 bg-sky-600 text-white border border-sky-500';
    if (arrBtn) arrBtn.className = 'py-2.5 px-3 rounded-xl font-bold transition flex items-center justify-center gap-1.5 bg-slate-950 text-slate-400 border border-slate-800 hover:text-white';
    if (airportLabel) airportLabel.innerText = '2. 前往目的地機場：';
    if (locLabel) locLabel.innerText = '3. 台北市區接送地址：';
    if (locInput) locInput.placeholder = '例如：台北晶華酒店大門口、信義路五段100號';
  } else {
    if (arrBtn) arrBtn.className = 'py-2.5 px-3 rounded-xl font-bold transition flex items-center justify-center gap-1.5 bg-emerald-600 text-white border border-emerald-500';
    if (depBtn) depBtn.className = 'py-2.5 px-3 rounded-xl font-bold transition flex items-center justify-center gap-1.5 bg-slate-950 text-slate-400 border border-slate-800 hover:text-white';
    if (airportLabel) airportLabel.innerText = '2. 班機降落抵達之機場：';
    if (locLabel) locLabel.innerText = '3. 返台送回目的地市區地址：';
    if (locInput) locInput.placeholder = '例如：信義區君悅酒店、板橋住家地址';
  }
  onBookAirportOrVehicleChanged();
}

function fillBookLocation(loc) {
  const input = document.getElementById('bookLocation');
  if (input) input.value = loc;
}

function adjustLuggageCount(type, delta) {
  const isLarge = (type === 'large');
  const inputId = isLarge ? 'bookLuggageLarge' : 'bookLuggageSmall';
  const displayId = isLarge ? 'largeLuggageCount' : 'smallLuggageCount';
  const input = document.getElementById(inputId);
  const display = document.getElementById(displayId);
  if (!input || !display) return;

  let val = parseInt(input.value) || 0;
  val = Math.max(0, Math.min(8, val + delta));
  input.value = val;
  display.innerText = val;

  onLuggageOrPaxChanged();
}

function toggleLuggageGuideModal() {
  const modal = document.getElementById('luggageGuideModal');
  if (modal) modal.classList.toggle('hidden');
}

function onLuggageOrPaxChanged() {
  const paxEl = document.getElementById('bookPax');
  const pax = paxEl ? (parseInt(paxEl.value) || 1) : 1;
  const largeInput = document.getElementById('bookLuggageLarge');
  const smallInput = document.getElementById('bookLuggageSmall');
  const largeBags = largeInput ? (parseInt(largeInput.value) || 0) : 0;
  const smallBags = smallInput ? (parseInt(smallInput.value) || 0) : 0;
  
  // 取得勾選之特殊行李
  const specialCheckboxes = document.querySelectorAll('input[name="specialLuggage"]:checked');
  const specialItems = Array.from(specialCheckboxes).map(cb => cb.value);
  const specialUnits = specialItems.length * 1.0;

  // 容積指數計算 (大箱 1.0, 登機箱 0.5, 特殊大件 1.0)
  const trunkUnits = (largeBags * 1.0) + (smallBags * 0.5) + specialUnits;
  const totalPieces = largeBags + smallBags + specialItems.length;

  const totalLuggageInput = document.getElementById('bookLuggage');
  if (totalLuggageInput) {
    totalLuggageInput.value = Math.max(1, totalPieces);
  }

  // 依據台灣各大車款後車廂物理極限推薦車款
  let recommendedVehicle = '標準轎車 (4人座)';
  if (pax >= 5 || trunkUnits > 3.5 || largeBags >= 5) {
    recommendedVehicle = '商務九人座 (T6/Alphard)';
  } else if ((pax >= 4 && trunkUnits > 2.0) || trunkUnits > 2.2 || largeBags >= 3 || (largeBags >= 2 && specialItems.length >= 1)) {
    recommendedVehicle = '休旅車 SUV (4-6人座)';
  } else {
    recommendedVehicle = '標準轎車 (4人座)';
  }

  // 取得當前選取的車款
  const vehicleRadios = document.getElementsByName('bookVehicle');
  let currentVehicle = '';
  for (const r of vehicleRadios) {
    if (r.checked) currentVehicle = r.value;
  }

  // 若當前車款容積不足，自動切換至建議車款
  const isOverloadedForSedan = currentVehicle.includes('轎車') && (pax >= 5 || trunkUnits > 2.2 || largeBags >= 3 || (largeBags >= 2 && specialItems.length >= 1));
  const isOverloadedForSuv = currentVehicle.includes('SUV') && (pax >= 5 || trunkUnits > 3.5 || largeBags >= 5);
  const isOverloaded = isOverloadedForSedan || isOverloadedForSuv;

  if (isOverloaded) {
    for (const r of vehicleRadios) {
      if (r.value === recommendedVehicle) {
        r.checked = true;
        currentVehicle = recommendedVehicle;
        break;
      }
    }
  }

  // 更新後車廂安全診斷條
  const alertBox = document.getElementById('trunkFitAlert');
  const alertIcon = document.getElementById('trunkFitIcon');
  const alertText = document.getElementById('trunkFitText');
  const badge = document.getElementById('trunkUnitsBadge');

  if (badge) {
    badge.innerText = `容積指數: ${trunkUnits.toFixed(1)} / 總件數: ${totalPieces} 件`;
  }

  if (alertBox && alertIcon && alertText) {
    if (isOverloaded) {
      alertBox.className = 'p-2.5 rounded-xl text-xs flex items-center justify-between border bg-rose-950/60 border-rose-500/50 text-rose-200';
      alertIcon.className = 'fa-solid fa-triangle-exclamation text-rose-400 text-sm flex-shrink-0';
      alertText.innerText = `⚠️ 行李已超出原車型後車廂極限，系統已自動為您升級推薦【${recommendedVehicle}】，確保出發當天順利裝載！`;
    } else if (trunkUnits >= 2.0 && currentVehicle.includes('轎車')) {
      alertBox.className = 'p-2.5 rounded-xl text-xs flex items-center justify-between border bg-amber-950/40 border-amber-500/40 text-amber-200';
      alertIcon.className = 'fa-solid fa-circle-exclamation text-amber-400 text-sm flex-shrink-0';
      alertText.innerText = `後車廂裝載接近上限：轎車後廂可放 2 件大箱，若有登機箱可能需放置後座空間。`;
    } else {
      alertBox.className = 'p-2.5 rounded-xl text-xs flex items-center justify-between border bg-emerald-950/40 border-emerald-500/30 text-emerald-200';
      alertIcon.className = 'fa-solid fa-circle-check text-emerald-400 text-sm flex-shrink-0';
      alertText.innerText = `後車廂容量安全：【${currentVehicle.split(' ')[0]}】空間充裕，行李與乘客人數均在標準內。`;
    }
  }

  onBookAirportOrVehicleChanged();
}

function onBookPaxChanged() {
  onLuggageOrPaxChanged();
}

function onBookAirportOrVehicleChanged() {
  const airportEl = document.getElementById('bookAirport');
  if (!airportEl) return;
  const airportVal = airportEl.value;
  const isTSA = airportVal.includes('TSA') || airportVal.includes('松山');
  
  const fares = isTSA 
    ? { sedan: 800, suv: 1000, van: 1400 }
    : { sedan: 1100, suv: 1400, van: 1800 };

  const dispSedan = document.getElementById('fareDisplaySedan');
  const dispSuv = document.getElementById('fareDisplaySuv');
  const dispVan = document.getElementById('fareDisplayVan');
  const totalFareEl = document.getElementById('bookTotalFare');

  if (dispSedan) dispSedan.innerText = `NT$ ${fares.sedan.toLocaleString()}`;
  if (dispSuv) dispSuv.innerText = `NT$ ${fares.suv.toLocaleString()}`;
  if (dispVan) dispVan.innerText = `NT$ ${fares.van.toLocaleString()}`;

  let selectedFare = fares.van;
  const vehicleRadios = document.getElementsByName('bookVehicle');
  for (const r of vehicleRadios) {
    if (r.checked) {
      if (r.value.includes('轎車')) selectedFare = fares.sedan;
      else if (r.value.includes('SUV') || r.value.includes('休旅')) selectedFare = fares.suv;
      else selectedFare = fares.van;
      break;
    }
  }

  if (totalFareEl) totalFareEl.innerText = `NT$ ${selectedFare.toLocaleString()}`;
}

async function submitCustomerBooking(e) {
  e.preventDefault();

  const airportVal = document.getElementById('bookAirport').value;
  const locVal = document.getElementById('bookLocation').value.trim();
  const dateVal = document.getElementById('bookDate').value;
  const timeVal = document.getElementById('bookTime').value;
  const paxVal = parseInt(document.getElementById('bookPax').value) || 1;
  const luggageVal = parseInt(document.getElementById('bookLuggage').value) || 1;
  const largeVal = parseInt(document.getElementById('bookLuggageLarge').value) || 0;
  const smallVal = parseInt(document.getElementById('bookLuggageSmall').value) || 0;
  const specialCheckboxes = document.querySelectorAll('input[name="specialLuggage"]:checked');
  const specialItems = Array.from(specialCheckboxes).map(cb => cb.value);
  const specialLuggageStr = specialItems.length > 0 ? specialItems.join(', ') : null;

  const breakdownParts = [];
  if (largeVal > 0) breakdownParts.push(`28~32吋大箱x${largeVal}`);
  if (smallVal > 0) breakdownParts.push(`登機箱x${smallVal}`);
  if (specialItems.length > 0) breakdownParts.push(...specialItems);
  const luggageBreakdownStr = breakdownParts.length > 0 ? breakdownParts.join(', ') : `${luggageVal} 件行李`;

  const flightVal = document.getElementById('bookFlight').value.trim();
  const nameVal = document.getElementById('bookName').value.trim();
  const phoneVal = document.getElementById('bookPhone').value.trim();
  const notesVal = document.getElementById('bookNotes').value.trim();

  let vehicleVal = '標準轎車 (4人座)';
  const vehicleRadios = document.getElementsByName('bookVehicle');
  for (const r of vehicleRadios) {
    if (r.checked) {
      vehicleVal = r.value;
      break;
    }
  }

  const isTSA = airportVal.includes('TSA') || airportVal.includes('松山');
  const fares = isTSA 
    ? { '標準轎車 (4人座)': 800, '休旅車 SUV (4-6人座)': 1000, '商務九人座 (T6/Alphard)': 1400 }
    : { '標準轎車 (4人座)': 1100, '休旅車 SUV (4-6人座)': 1400, '商務九人座 (T6/Alphard)': 1800 };

  const fare = fares[vehicleVal] || 1100;
  const pickupTimeStr = `${dateVal} ${timeVal}`;
  const isArrival = (bookTripType === 'ARRIVAL');

  const payload = {
    line_group_id: 'web-direct-booking',
    line_group_name: '🌐 官網/社群直客預約專區',
    customer_name: nameVal,
    customer_phone: phoneVal,
    trip_type: bookTripType,
    pickup_location: isArrival ? `${airportVal} 入境大廳` : locVal,
    pickup_datetime: pickupTimeStr,
    destination_airport: isArrival ? `${locVal} (返台接機)` : airportVal,
    terminal_flight_no: flightVal || null,
    passengers: paxVal,
    luggage: luggageVal,
    luggage_large: largeVal,
    luggage_small: smallVal,
    special_luggage: specialLuggageStr,
    luggage_breakdown: luggageBreakdownStr,
    vehicle_type: vehicleVal,
    estimated_fare: fare,
    platform_fee: 50.0,
    driver_payout: fare - 50.0,
    status: 'NEW',
    raw_message: `[官網直客] ${nameVal} 預約 ${pickupTimeStr}，路線: ${isArrival ? airportVal : locVal} ➔ ${isArrival ? locVal : airportVal}，需求: ${paxVal}人, ${luggageBreakdownStr} (${vehicleVal})，電話: ${phoneVal}`,
    notes: notesVal ? `備註: ${notesVal}` : '官網線上直約客戶'
  };

  const submitBtn = document.getElementById('bookSubmitBtn');
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>正在排班送出...</span>`;

  try {
    const res = await fetch('/api/trips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const createdTrip = await res.json();
      
      // 顯示成功憑證
      const successBox = document.getElementById('bookingSuccessBox');
      document.getElementById('successTripId').innerText = `#預約單-${createdTrip.id}`;
      document.getElementById('successDateTime').innerText = pickupTimeStr;
      document.getElementById('successRoute').innerText = `${createdTrip.pickup_location} ➔ ${createdTrip.destination_airport}`;
      document.getElementById('successVehicle').innerText = `${createdTrip.vehicle_type} (${paxVal}人 / ${createdTrip.luggage_breakdown || (luggageVal + '箱')})`;
      document.getElementById('successFare').innerText = `NT$ ${Math.round(createdTrip.estimated_fare).toLocaleString()} 元`;
      
      successBox.classList.remove('hidden');
      successBox.scrollIntoView({ behavior: 'smooth' });

      // 觸發全域重新整理
      loadAllData();
    } else {
      alert('預約送出失敗，請檢查資料填寫是否完整。');
    }
  } catch (err) {
    alert('網路連線失敗，請稍後再試。');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> <span>立即確認送出專車預約</span>`;
  }
}

function resetBookingForm() {
  document.getElementById('bookingSuccessBox').classList.add('hidden');
  document.getElementById('customerBookingForm').reset();
  
  // 重設行李步進器與預設值
  const largeInput = document.getElementById('bookLuggageLarge');
  const smallInput = document.getElementById('bookLuggageSmall');
  const largeDisp = document.getElementById('largeLuggageCount');
  const smallDisp = document.getElementById('smallLuggageCount');
  if (largeInput) largeInput.value = 2;
  if (smallInput) smallInput.value = 1;
  if (largeDisp) largeDisp.innerText = '2';
  if (smallDisp) smallDisp.innerText = '1';

  initBookingDate();
  setBookTripType('DEPARTURE');
  onLuggageOrPaxChanged();
}

function copyBookingLink() {
  const input = document.getElementById('publicBookingLinkInput');
  if (input) {
    input.select();
    navigator.clipboard.writeText(input.value);
    alert('📋 直客預約網址已複製！您可以直接貼在 Facebook 社團、Instagram 自介、Threads 或蝦皮聊聊中！');
  }
}

// ==========================================
// 9. Cloudflare 公開隧道管理
// ==========================================

let isTunnelRunning = false;

async function checkTunnelStatus() {
  try {
    const res = await fetch('/api/tunnel/status');
    if (!res.ok) return;
    const data = await res.json();
    
    isTunnelRunning = data.is_running;
    const badge = document.getElementById('tunnelStatusBadge');
    const btnText = document.getElementById('tunnelBtnText');
    const webhookInput = document.getElementById('liveWebhookUrlInput');
    const bookingInput = document.getElementById('publicBookingLinkInput');

    const isNonLocal = !window.location.hostname.includes('127.0.0.1') && !window.location.hostname.includes('localhost');

    if (data.is_vercel || window.location.hostname.includes('vercel.app')) {
      if (badge) badge.innerHTML = `<span class="text-emerald-400 font-bold flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>🟢 Vercel 雲端全域連線中</span>`;
      if (btnText) btnText.innerText = '☁️ Vercel 全球邊緣 CDN 運行中';
      if (webhookInput) webhookInput.value = `${window.location.origin}/api/line/webhook`;
      if (bookingInput) bookingInput.value = `${window.location.origin}/book`;
      return;
    }

    if (data.is_running) {
      if (badge) badge.innerHTML = `<span class="text-emerald-400 font-bold flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>🟢 公開通道運作中</span>`;
      if (btnText) btnText.innerText = '🛑 關閉 Cloudflare 公開通道';
      if (webhookInput && data.webhook_url) webhookInput.value = data.webhook_url;
      if (bookingInput && data.customer_booking_url) bookingInput.value = data.customer_booking_url;
    } else if (data.is_starting) {
      if (badge) badge.innerHTML = `<span class="text-amber-400 font-semibold"><i class="fa-solid fa-spinner fa-spin mr-1"></i>正在建立公開隧道...</span>`;
      if (btnText) btnText.innerText = '正在建立連線...';
    } else {
      if (badge) badge.innerHTML = `<span class="text-slate-400">⚪ 通道未開啟</span>`;
      if (btnText) btnText.innerText = '⚡ 一鍵啟動 Cloudflare 公開通道';
      if (bookingInput) bookingInput.value = isNonLocal ? `${window.location.origin}/book` : 'http://127.0.0.1:8000/book';
      if (webhookInput && isNonLocal) webhookInput.value = `${window.location.origin}/api/line/webhook`;
    }
  } catch (err) {
    console.error(err);
  }
}

async function toggleTunnel() {
  const btnText = document.getElementById('tunnelBtnText');
  if (isTunnelRunning) {
    if (btnText) btnText.innerText = '正在關閉通道...';
    try {
      await fetch('/api/tunnel/stop', { method: 'POST' });
    } catch (e) {}
    setTimeout(checkTunnelStatus, 800);
  } else {
    if (btnText) btnText.innerText = '正在請求 Cloudflare 邊緣節點...';
    try {
      await fetch('/api/tunnel/start', { method: 'POST' });
    } catch (e) {}
    // Poll a few times for URL capture
    setTimeout(checkTunnelStatus, 1500);
    setTimeout(checkTunnelStatus, 3500);
    setTimeout(checkTunnelStatus, 6000);
  }
}

function copyWebhookUrl() {
  const input = document.getElementById('liveWebhookUrlInput');
  if (input) {
    input.select();
    navigator.clipboard.writeText(input.value);
    alert('📋 Webhook 網址已複製！請至 LINE Developers Console 貼上並點擊 Verify。');
  }
}

