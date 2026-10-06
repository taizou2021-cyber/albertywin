# 如何將台北機場專車系統免費部署至 Vercel (取得專屬 *.vercel.app 永久網址)

本專案已完全完成 Vercel 雲端相容架構配置（包括 `vercel.json`、`api/index.py`、`requirements.txt`、`.vercelignore` 以及自動適配 `/tmp` 寫入的 SQLite 資料庫）。

您可以透過以下 **2 種方式**，在 2 分鐘內取得專屬的 `https://<自訂名稱>.vercel.app` 永久網址，立即分享給朋友與社群客戶！

---

## 🚀 方式一：GitHub ＋ Vercel 網頁一鍵部署（最推薦、最簡單）

### 步驟 1：將此專案上傳至您的 GitHub
1. 前往 [github.com/new](https://github.com/new) 建立一個新的儲存庫（例如命名為 `line-airport-dispatch`，設為 Public 或 Private 皆可）。
2. 在您的本機終端機將程式碼推送到 GitHub：
   ```bash
   git init
   git add .
   git commit -m "feat: complete airport dispatch system with vercel support"
   git branch -M main
   git remote add origin https://github.com/<您的GitHub帳號>/line-airport-dispatch.git
   git push -u origin main
   ```
   *(或直接在 GitHub 網頁上點擊「Add file」->「Upload files」把本專案資料夾的所有檔案拖曳上傳)*

### 步驟 2：登入 Vercel 一鍵匯入
1. 前往 [vercel.com/new](https://vercel.com/new)（可使用 GitHub 帳號直接登入）。
2. 在 **Import Git Repository** 列表中，找到剛才建立的 `line-airport-dispatch`，點擊 **Import**。
3. **Project Name**：可自訂為您喜愛的名稱（例如 `taipei-airport-car`），這將決定您的專屬網址：
   👉 **`https://taipei-airport-car.vercel.app`**
4. 點擊 **Deploy** 按鈕！
5. 等候約 45 秒，部署成功！畫面會噴彩帶，並給您正式的 `*.vercel.app` 網址！

---

## ⚡ 方式二：使用 Vercel CLI 命令列部署

如果您電腦有安裝 Node.js，也可以直接在專案目錄執行：
```bash
npm i -g vercel
vercel
```
依照畫面提示連續按下 Enter（預設設定），1 分鐘內即可獲得發布網址！

---

## 📱 部署完成後即可分享給朋友的網址

| 頁面 | 永久 Vercel 網址範例 | 說明 |
| :--- | :--- | :--- |
| 🌐 **顧客直約專區** | `https://<您的專案>.vercel.app/book` | 朋友/直客免加 LINE，在手機直接填表預約！ |
| 🚕 **司機搶單端** | `https://<您的專案>.vercel.app/?tab=driver` | 司機查看明日早鳥、回程不空車雙趟訂單 |
| 💻 **後台調度中心** | `https://<您的專案>.vercel.app/` | 監控全台北車隊調度與即時訂單 |
| 🤖 **LINE Webhook** | `https://<您的專案>.vercel.app/api/line/webhook` | 貼到 LINE Developers 即可串接真實手機群組！ |

---

## 💡 目前即時可用的全球公開網址（現在就能直接傳給朋友！）

如果您現在就要立刻傳給朋友試用，我們剛才已經為您啟動了免費全球公開隧道：
- 👉 **直客極速預約網址**：**`https://stock-salt-screenshot-world.trycloudflare.com/book`**
- 👉 **完整平台網址**：**`https://stock-salt-screenshot-world.trycloudflare.com/`**
- 手機、平板、電腦在任何地方點開都能即刻預約！
