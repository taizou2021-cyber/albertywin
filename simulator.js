let groups = [];
let currentGroup = null;

const SCENARIOS = {
  taoyuan: "明天早上 06:30 需要一輛九人座商務車前往桃園機場第二航廈，從台北晶華酒店大廳出發，4位大人、4件大行李，搭長榮 BR87，聯絡電話 0912-345-678",
  songshan: "明天下午 14:00 需要一台轎車去松山機場國際線，從信義區君悅酒店大門出發，2人2件行李，班機 JL098，電話 0933-882-910",
  rejection: "請問明天早上 9 點可以派一輛車送我們去九份老街一日遊嗎？2 個人有行李。",
  template: "上車地點：台北市大安區和平大苑\n前往機場：桃園機場一航\n出發時間：2026-10-06 05:30\n搭乘人數：3位\n行李件數：3箱\n航班編號：JX800\n聯絡電話：0955-771-320",
  help: "/help"
};

document.addEventListener('DOMContentLoaded', async () => {
  await loadGroups();
});

async function loadGroups() {
  try {
    const res = await fetch('/api/groups');
    if (!res.ok) return;
    groups = await res.json();

    const select = document.getElementById('simGroupSelect');
    select.innerHTML = groups.map(g => `
      <option value="${g.group_id}">${escapeHtml(g.group_name)}</option>
    `).join('');

    if (groups.length > 0) {
      currentGroup = groups[0];
      updateChatHeader();
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

  // 1. 繪製用戶訊息泡泡
  appendUserMessage(senderName, messageText);
  input.value = '';

  // 2. 呼叫模擬器 API
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

    // 3. 繪製機器人回覆之 Flex Card
    if (result.reply_flex) {
      appendBotFlexMessage(result.reply_flex);
    } else if (result.type === 'ignored') {
      appendSystemNotice('機器人監聽到訊息，但非機場叫車需求（靜默不干擾）');
    }

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

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}
